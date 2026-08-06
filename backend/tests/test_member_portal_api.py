from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, Contribution, Event, Household, HouseholdPerson, Member, Message


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
        member = Member(
            branch_id=branch.id,
            first_name="Ada",
            last_name="Member",
            membership_status="active",
        )
        db.add(member)
        db.flush()
        household = Household(
            branch_id=branch.id,
            name="Ada Household",
            primary_member_id=member.id,
        )
        db.add(household)
        db.flush()
        db.add_all(
            [
                HouseholdPerson(
                    household_id=household.id,
                    member_id=member.id,
                    person_type="member",
                    relationship="primary",
                ),
                HouseholdPerson(
                    household_id=household.id,
                    first_name="Chris",
                    last_name="Child",
                    person_type="child",
                    relationship="child",
                    can_self_check_in="no",
                ),
                Event(
                    branch_id=branch.id,
                    name="Sunday Service",
                    event_type="service",
                    starts_at=datetime.now(UTC),
                    location="Main Hall",
                ),
                Message(
                    branch_id=branch.id,
                    channel="sms",
                    subject="Welcome",
                    body="Service starts at 9.",
                    audience_type="all_members",
                    status="sent",
                ),
                Contribution(
                    branch_id=branch.id,
                    member_id=member.id,
                    contribution_type="tithe",
                    amount=Decimal("10000.00"),
                    currency="TZS",
                    payment_method="cash",
                    reference_code="ENV-1",
                    received_at=datetime.now(UTC),
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


def test_member_portal_demo_profile() -> None:
    client = build_client()

    response = client.get("/api/v1/member-portal/me")

    assert response.status_code == 200
    data = response.json()
    assert data["profile"]["name"] == "Ada Member"
    assert data["household"]["people"][0]["name"] == "Chris Child"
    assert data["events"][0]["name"] == "Sunday Service"
    assert data["messages"][0]["subject"] == "Welcome"
    assert data["giving"]["total_amount"] == "10000.00"
    assert data["giving"]["latest"][0]["reference_code"] == "ENV-1"


def test_member_portal_create_giving() -> None:
    client = build_client()

    response = client.post(
        "/api/v1/member-portal/giving",
        json={
            "contribution_type": "offering",
            "amount": "5000.00",
            "currency": "TZS",
            "payment_method": "mobile_money",
            "reference_code": "MM-777",
            "notes": "Member portal giving",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["reference_code"] == "MM-777"
    assert created["payment_method"] == "mobile_money"

    portal = client.get("/api/v1/member-portal/me").json()
    assert portal["giving"]["total_amount"] == "15000.00"
    assert portal["giving"]["latest"][0]["reference_code"] == "MM-777"


def test_member_portal_rejects_invalid_giving_amount() -> None:
    client = build_client()

    response = client.post(
        "/api/v1/member-portal/giving",
        json={"contribution_type": "tithe", "amount": "0.00"},
    )

    assert response.status_code == 422
