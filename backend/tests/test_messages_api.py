from collections.abc import Generator
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, utc_now
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, Member, Message, MessageRecipient, Visitor
from tests.auth_helpers import add_test_user, auth_headers


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with TestingSessionLocal() as db:
        branch = Branch(name="Test Parish", location="Test City")
        db.add(branch)
        db.flush()
        add_test_user(db, branch, "Pastor / Leader")
        db.add_all(
            [
                Member(
                    branch_id=branch.id,
                    first_name="Neema",
                    last_name="Kileo",
                    phone="+255 711 100 001",
                    email="neema@test.local",
                    membership_status="active",
                    joined_at=utc_now(),
                ),
                Member(
                    branch_id=branch.id,
                    first_name="Inactive",
                    last_name="Member",
                    phone="+255 711 100 002",
                    email="inactive@test.local",
                    membership_status="transferred",
                    joined_at=utc_now(),
                ),
                Visitor(
                    branch_id=branch.id,
                    first_name="Joyce",
                    last_name="Lema",
                    phone="+255 722 100 001",
                    email="joyce@test.local",
                    follow_up_status="new",
                ),
            ]
        )
        db.commit()

    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_create_send_now_message() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.post(
        "/api/v1/messages/",
        json={
            "channel": "sms",
            "subject": "Sunday Reminder",
            "body": "Service starts at 9.",
            "audience_type": "all_members",
            "status": "send_now",
        },
        headers=headers,
    )

    assert response.status_code == 201
    message = response.json()
    assert message["status"] == "sent"
    assert message["sent_at"] is not None
    assert message["recipient_count"] == 1
    assert message["delivery_counts"] == {"queued": 1}

    messages = client.get("/api/v1/messages/", headers=headers).json()["messages"]
    assert messages[0]["body"] == "Service starts at 9."

    recipients = client.get(
        f"/api/v1/messages/{message['id']}/recipients",
        headers=headers,
    )
    assert recipients.status_code == 200
    assert recipients.json()["recipients"][0]["name"] == "Neema Kileo"


def test_create_draft_message() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.post(
        "/api/v1/messages/",
        json={
            "channel": "in_app",
            "subject": "Draft",
            "body": "Draft body",
            "status": "draft",
        },
        headers=headers,
    )

    assert response.status_code == 201
    message = response.json()
    assert message["status"] == "draft"
    assert message["sent_at"] is None
    assert message["delivery_counts"] == {"draft": 1}

    dispatch = client.post(f"/api/v1/messages/{message['id']}/dispatch", headers=headers)
    assert dispatch.status_code == 200
    assert dispatch.json()["status"] == "sent"
    assert dispatch.json()["delivery_counts"] == {"delivered": 1}


def test_visitor_audience_creates_visitor_recipients() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.post(
        "/api/v1/messages/",
        json={
            "channel": "sms",
            "subject": "Welcome",
            "body": "Thank you for visiting.",
            "audience_type": "visitors",
            "status": "send_now",
        },
        headers=headers,
    )

    assert response.status_code == 201
    message = response.json()
    recipients = client.get(f"/api/v1/messages/{message['id']}/recipients", headers=headers)
    assert recipients.json()["recipients"][0]["person_type"] == "visitor"


def test_recipient_view_backfills_existing_message_without_delivery_rows() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.post(
        "/api/v1/messages/",
        json={
            "channel": "push",
            "subject": "Backfill",
            "body": "Backfill body",
            "audience_type": "all_members",
            "status": "draft",
        },
        headers=headers,
    )
    message_id = response.json()["id"]

    # Simulate a pre-delivery-tracking message record.
    db_generator = client.app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        message = db.get(Message, UUID(message_id))
        assert message is not None
        db.query(MessageRecipient).filter(MessageRecipient.message_id == message.id).delete()
        db.commit()
    finally:
        db.close()
        db_generator.close()

    recipients = client.get(f"/api/v1/messages/{message_id}/recipients", headers=headers)

    assert recipients.status_code == 200
    assert recipients.json()["recipients"]

def test_sms_provider_status_and_delivery_callback() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    provider = client.get("/api/v1/messages/sms/provider", headers=headers)
    assert provider.status_code == 200
    assert provider.json()["provider"] == "africas_talking"
    assert provider.json()["mode"] == "simulate"
    assert provider.json()["external_sending"] is False

    response = client.post(
        "/api/v1/messages/",
        json={
            "channel": "sms",
            "subject": "Delivery test",
            "body": "Vinyrd delivery test.",
            "audience_type": "all_members",
            "status": "send_now",
        },
        headers=headers,
    )
    assert response.status_code == 201

    message_id = response.json()["id"]
    recipients = client.get(
        f"/api/v1/messages/{message_id}/recipients",
        headers=headers,
    ).json()["recipients"]
    assert recipients[0]["delivery_status"] == "queued"
    provider_reference = recipients[0]["provider_reference"]
    assert provider_reference

    callback = client.post(
        "/api/v1/messages/sms/delivery-report",
        data={
            "id": provider_reference,
            "status": "Success",
            "phoneNumber": recipients[0]["phone"],
        },
    )
    assert callback.status_code == 200
    assert callback.json()["delivery_status"] == "delivered"

    refreshed = client.get(
        f"/api/v1/messages/{message_id}/recipients",
        headers=headers,
    ).json()["recipients"]
    assert refreshed[0]["delivery_status"] == "delivered"

