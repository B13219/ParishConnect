from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, Member
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
        add_test_user(db, branch, "Administrator")
        add_test_user(db, branch, "Pastor / Leader")
        add_test_user(db, branch, "Accountant")
        add_test_user(db, branch, "Receptionist")
        db.add(Member(branch_id=branch.id, first_name="Ada", last_name="Member"))
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


def test_record_contribution_and_summary_breakdown() -> None:
    client = build_client()
    accountant_headers = auth_headers(client, "Accountant")
    pastor_headers = auth_headers(client, "Pastor / Leader")
    receptionist_headers = auth_headers(client, "Receptionist")
    member_id = client.get("/api/v1/members/", headers=receptionist_headers).json()["members"][0]["id"]

    response = client.post(
        "/api/v1/stewardship/contributions",
        json={
            "member_id": member_id,
            "contribution_type": "tithe",
            "amount": "125000.00",
            "currency": "tzs",
            "payment_method": "mobile_money",
            "reference_code": "MNO-12345",
            "notes": "Sunday envelope",
        },
        headers=accountant_headers,
    )

    assert response.status_code == 201
    contribution = response.json()
    assert contribution["member_name"] == "Ada Member"
    assert contribution["currency"] == "TZS"
    assert contribution["payment_method"] == "mobile_money"
    assert contribution["reference_code"] == "MNO-12345"

    summary = client.get("/api/v1/stewardship/", headers=pastor_headers).json()
    assert summary["total_amount"] == "125000.00"
    assert summary["contribution_count"] == 1
    assert summary["by_type"][0]["type"] == "tithe"
    assert summary["latest"][0]["notes"] == "Sunday envelope"
    assert summary["latest"][0]["reference_code"] == "MNO-12345"


def test_reject_negative_contribution() -> None:
    client = build_client()
    accountant_headers = auth_headers(client, "Accountant")

    response = client.post(
        "/api/v1/stewardship/contributions",
        json={"contribution_type": "offering", "amount": "-5.00"},
        headers=accountant_headers,
    )

    assert response.status_code == 422


def test_accountant_can_view_stewardship_and_receptionist_cannot() -> None:
    client = build_client()
    accountant_headers = auth_headers(client, "Accountant")
    receptionist_headers = auth_headers(client, "Receptionist")

    accountant_response = client.get("/api/v1/stewardship/", headers=accountant_headers)
    receptionist_response = client.get("/api/v1/stewardship/", headers=receptionist_headers)

    assert accountant_response.status_code == 200
    assert receptionist_response.status_code == 403
