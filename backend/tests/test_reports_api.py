from collections.abc import Generator
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, utc_now
from app.db.session import get_db
from app.main import create_app
from app.models import (
    AttendanceRecord,
    Branch,
    Contribution,
    Event,
    Household,
    HouseholdPerson,
    Member,
    Message,
    Visitor,
)
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
        now = utc_now()
        branch = Branch(name="Test Parish", location="Test City")
        db.add(branch)
        db.flush()
        add_test_user(db, branch, "Pastor / Leader")
        add_test_user(db, branch, "Accountant")
        add_test_user(db, branch, "Usher")

        member = Member(
            branch_id=branch.id,
            first_name="Ada",
            last_name="Member",
            membership_status="active",
        )
        inactive_member = Member(
            branch_id=branch.id,
            first_name="Ben",
            last_name="Transfer",
            membership_status="transferred",
        )
        visitor = Visitor(
            branch_id=branch.id,
            first_name="Vera",
            last_name="Visitor",
            follow_up_status="new",
        )
        db.add_all([member, inactive_member, visitor])
        db.flush()

        household = Household(
            branch_id=branch.id,
            name="Ada Household",
            primary_member_id=member.id,
        )
        db.add(household)
        db.flush()
        dependent = HouseholdPerson(
            household_id=household.id,
            first_name="Child",
            last_name="Member",
            person_type="child",
            relationship="child",
            can_self_check_in="no",
        )
        db.add(dependent)
        db.flush()

        event = Event(
            branch_id=branch.id,
            name="Sunday Service",
            starts_at=now,
            ends_at=None,
            qr_opens_at=None,
            qr_closes_at=None,
        )
        db.add(event)
        db.flush()
        db.add_all(
            [
                AttendanceRecord(
                    branch_id=branch.id,
                    event_id=event.id,
                    person_type="member",
                    member_id=member.id,
                    check_in_method="qr",
                    checked_in_at=now,
                ),
                AttendanceRecord(
                    branch_id=branch.id,
                    event_id=event.id,
                    person_type="visitor",
                    visitor_id=visitor.id,
                    check_in_method="manual",
                    checked_in_at=now,
                ),
                AttendanceRecord(
                    branch_id=branch.id,
                    event_id=event.id,
                    person_type="household_person",
                    household_person_id=dependent.id,
                    check_in_method="household",
                    checked_in_at=now,
                ),
                Contribution(
                    branch_id=branch.id,
                    member_id=member.id,
                    contribution_type="tithe",
                    amount=Decimal("5000.00"),
                    currency="TZS",
                    payment_method="mobile_money",
                    received_at=now,
                ),
                Message(
                    branch_id=branch.id,
                    channel="sms",
                    subject="Reminder",
                    body="Sunday reminder",
                    audience_type="all_members",
                    status="sent",
                    sent_at=now,
                ),
                Message(
                    branch_id=branch.id,
                    channel="in_app",
                    subject="Meeting",
                    body="Leadership meeting",
                    audience_type="ministry",
                    status="scheduled",
                    scheduled_at=now,
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


def test_weekly_report_rolls_up_core_operational_data() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.get("/api/v1/reports/weekly", headers=headers)

    assert response.status_code == 200
    report = response.json()
    assert report["module"] == "reports"
    assert report["attendance"]["total"] == 3
    assert report["attendance"]["members"] == 1
    assert report["attendance"]["visitors"] == 1
    assert report["attendance"]["household_dependents"] == 1
    assert report["attendance"]["by_event"][0]["event_name"] == "Sunday Service"
    assert report["stewardship"]["total_amount"] == "5000.00"
    assert report["stewardship"]["by_type"][0]["type"] == "tithe"
    assert report["stewardship"]["by_payment_method"][0]["method"] == "mobile_money"
    assert report["communication"]["total_messages"] == 2
    assert report["communication"]["sent"] == 1
    assert report["communication"]["scheduled"] == 1
    assert report["people"]["new_visitors"] == 1
    assert report["people"]["inactive_members"] == 1
    assert report["observations"]


def test_weekly_report_briefing_is_shareable_plain_text() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.get("/api/v1/reports/weekly/briefing", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "ParishConnect Weekly Leadership Briefing" in response.text
    assert "Total check-ins: 3" in response.text
    assert "Total giving: 5000.00 TZS" in response.text


def test_weekly_report_csv_export_is_spreadsheet_friendly() -> None:
    client = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.get("/api/v1/reports/weekly.csv", headers=headers)

    assert response.status_code == 200
    assert "section,metric,value,detail" in response.text
    assert "stewardship,total_giving,5000.00,TZS" in response.text


def test_accountant_can_access_weekly_report_for_stewardship_review() -> None:
    client = build_client()
    headers = auth_headers(client, "Accountant")

    response = client.get("/api/v1/reports/weekly", headers=headers)

    assert response.status_code == 200
    assert response.json()["stewardship"]["total_amount"] == "5000.00"
