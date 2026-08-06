from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import password_hash
from app.db.session import SessionLocal
from app.models import (
    AttendanceRecord,
    Branch,
    Contribution,
    Event,
    Household,
    HouseholdPerson,
    Member,
    Message,
    Ministry,
    Role,
    User,
    UserRole,
    Visitor,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def seed_demo_data() -> dict[str, int]:
    with SessionLocal() as db:
        existing_branch = db.scalar(select(Branch).where(Branch.name == "Grace Community Parish"))
        if existing_branch is not None:
            return {"branches": 0, "members": 0, "visitors": 0, "events": 0}

        branch = Branch(
            name="Grace Community Parish",
            location="Dar es Salaam",
            contact_phone="+255 700 100 200",
        )
        db.add(branch)
        db.flush()

        admin_role = Role(name="Administrator", description="Full system access")
        pastor_role = Role(name="Pastor / Leader", description="Reports and ministry oversight")
        accountant_role = Role(name="Accountant", description="Stewardship and finance records")
        receptionist_role = Role(name="Receptionist", description="Visitor and front-desk records")
        usher_role = Role(name="Usher", description="Attendance check-in access")
        member_role = Role(name="Member", description="Member portal access")
        db.add_all(
            [admin_role, pastor_role, accountant_role, receptionist_role, usher_role, member_role]
        )
        db.flush()

        demo_hash = password_hash("parishconnect")
        admin = User(
            branch_id=branch.id,
            name="Amina Joseph",
            email="admin@graceparish.test",
            phone="+255 700 111 222",
            password_hash=demo_hash,
            status="active",
        )
        pastor = User(
            branch_id=branch.id,
            name="Pastor Daniel Mushi",
            email="pastor@graceparish.test",
            phone="+255 700 333 444",
            password_hash=demo_hash,
            status="active",
        )
        accountant = User(
            branch_id=branch.id,
            name="Grace Treasurer",
            email="accountant@graceparish.test",
            phone="+255 700 444 555",
            password_hash=demo_hash,
            status="active",
        )
        receptionist = User(
            branch_id=branch.id,
            name="Rehema Front Desk",
            email="reception@graceparish.test",
            phone="+255 700 555 666",
            password_hash=demo_hash,
            status="active",
        )
        usher = User(
            branch_id=branch.id,
            name="Jonas Usher",
            email="usher@graceparish.test",
            phone="+255 700 777 888",
            password_hash=demo_hash,
            status="active",
        )
        db.add_all([admin, pastor, accountant, receptionist, usher])
        db.flush()
        db.add_all(
            [
                UserRole(user_id=admin.id, role_id=admin_role.id),
                UserRole(user_id=pastor.id, role_id=pastor_role.id),
                UserRole(user_id=accountant.id, role_id=accountant_role.id),
                UserRole(user_id=receptionist.id, role_id=receptionist_role.id),
                UserRole(user_id=usher.id, role_id=usher_role.id),
            ]
        )

        members = [
            Member(
                branch_id=branch.id,
                first_name="Neema",
                last_name="Kileo",
                phone="+255 711 100 001",
                email="neema.kileo@example.test",
                membership_status="active",
                joined_at=utc_now() - timedelta(days=420),
            ),
            Member(
                branch_id=branch.id,
                first_name="Baraka",
                last_name="Mwita",
                phone="+255 711 100 002",
                email="baraka.mwita@example.test",
                membership_status="active",
                joined_at=utc_now() - timedelta(days=260),
            ),
            Member(
                branch_id=branch.id,
                first_name="Rehema",
                last_name="Sanga",
                phone="+255 711 100 003",
                email="rehema.sanga@example.test",
                membership_status="active",
                joined_at=utc_now() - timedelta(days=120),
            ),
        ]
        db.add_all(members)
        db.flush()

        worship = Ministry(branch_id=branch.id, name="Worship Team", leader_member_id=members[0].id)
        youth = Ministry(branch_id=branch.id, name="Youth Ministry", leader_member_id=members[1].id)
        db.add_all([worship, youth])
        db.flush()

        visitors = [
            Visitor(
                branch_id=branch.id,
                first_name="Joyce",
                last_name="Lema",
                phone="+255 722 200 001",
                email="joyce.lema@example.test",
                follow_up_status="new",
            ),
            Visitor(
                branch_id=branch.id,
                first_name="Emmanuel",
                last_name="Peter",
                phone="+255 722 200 002",
                email="emmanuel.peter@example.test",
                follow_up_status="contacted",
            ),
        ]
        db.add_all(visitors)
        db.flush()

        household = Household(
            branch_id=branch.id,
            name="Kileo Household",
            primary_member_id=members[0].id,
            primary_phone=members[0].phone,
            notes="Demo household with children for assisted check-in.",
        )
        db.add(household)
        db.flush()
        db.add_all(
            [
                HouseholdPerson(
                    household_id=household.id,
                    member_id=members[0].id,
                    person_type="member",
                    relationship="primary",
                    can_self_check_in="yes",
                ),
                HouseholdPerson(
                    household_id=household.id,
                    first_name="Imani",
                    last_name="Kileo",
                    person_type="child",
                    relationship="child",
                    can_self_check_in="no",
                ),
                HouseholdPerson(
                    household_id=household.id,
                    first_name="Amani",
                    last_name="Kileo",
                    person_type="child",
                    relationship="child",
                    can_self_check_in="no",
                ),
            ]
        )

        sunday_service = Event(
            branch_id=branch.id,
            ministry_id=None,
            name="Sunday Main Service",
            event_type="service",
            starts_at=utc_now() + timedelta(days=2),
            ends_at=utc_now() + timedelta(days=2, hours=2),
            location="Main Sanctuary",
        )
        youth_meeting = Event(
            branch_id=branch.id,
            ministry_id=youth.id,
            name="Youth Fellowship",
            event_type="ministry",
            starts_at=utc_now() + timedelta(days=5),
            ends_at=utc_now() + timedelta(days=5, hours=2),
            location="Hall B",
        )
        db.add_all([sunday_service, youth_meeting])
        db.flush()

        db.add_all(
            [
                AttendanceRecord(
                    branch_id=branch.id,
                    event_id=sunday_service.id,
                    person_type="member",
                    member_id=member.id,
                    checked_in_by=admin.id,
                    check_in_method="qr",
                )
                for member in members
            ]
        )
        db.add(
            AttendanceRecord(
                branch_id=branch.id,
                event_id=sunday_service.id,
                person_type="visitor",
                visitor_id=visitors[0].id,
                checked_in_by=admin.id,
                check_in_method="manual",
            )
        )

        db.add_all(
            [
                Message(
                    branch_id=branch.id,
                    sender_user_id=pastor.id,
                    channel="sms",
                    subject="Sunday Service Reminder",
                    body="Reminder: Sunday service starts at 9:00 AM. God bless you.",
                    audience_type="all_members",
                    status="sent",
                    sent_at=utc_now(),
                ),
                Message(
                    branch_id=branch.id,
                    sender_user_id=pastor.id,
                    channel="push",
                    subject="Youth Fellowship",
                    body="Youth fellowship meets this Friday in Hall B.",
                    audience_type="ministry",
                    status="scheduled",
                    scheduled_at=utc_now() + timedelta(days=1),
                ),
            ]
        )

        db.add_all(
            [
                Contribution(
                    branch_id=branch.id,
                    member_id=members[0].id,
                    contribution_type="tithe",
                    amount=Decimal("75000.00"),
                    currency="TZS",
                    payment_method="mobile_money",
                    reference_code="MNO-DEMO-1001",
                    recorded_by=admin.id,
                    notes="Demo tithe record",
                ),
                Contribution(
                    branch_id=branch.id,
                    member_id=members[1].id,
                    contribution_type="offering",
                    amount=Decimal("25000.00"),
                    currency="TZS",
                    payment_method="cash",
                    reference_code="ENV-204",
                    recorded_by=admin.id,
                    notes="Demo offering record",
                ),
            ]
        )

        db.commit()
        return {"branches": 1, "members": len(members), "visitors": len(visitors), "events": 2}


def main() -> None:
    result = seed_demo_data()
    print(f"Seed complete: {result}")


if __name__ == "__main__":
    main()
