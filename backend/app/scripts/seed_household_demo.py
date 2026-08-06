from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Branch, Household, HouseholdPerson, Member


def seed_household_demo() -> dict[str, int]:
    with SessionLocal() as db:
        existing = db.scalar(select(Household).where(Household.name == "Kileo Household"))
        if existing is not None:
            return {"households": 0, "people": 0}

        branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
        primary = db.scalar(select(Member).order_by(Member.created_at.asc()))
        if branch is None or primary is None:
            return {"households": 0, "people": 0}

        household = Household(
            branch_id=branch.id,
            name="Kileo Household",
            primary_member_id=primary.id,
            primary_phone=primary.phone,
            notes="Demo household with children for assisted check-in.",
        )
        db.add(household)
        db.flush()
        db.add_all(
            [
                HouseholdPerson(
                    household_id=household.id,
                    member_id=primary.id,
                    person_type="member",
                    relationship="primary",
                    can_self_check_in="yes",
                ),
                HouseholdPerson(
                    household_id=household.id,
                    first_name="Imani",
                    last_name=primary.last_name,
                    person_type="child",
                    relationship="child",
                    can_self_check_in="no",
                ),
                HouseholdPerson(
                    household_id=household.id,
                    first_name="Amani",
                    last_name=primary.last_name,
                    person_type="child",
                    relationship="child",
                    can_self_check_in="no",
                ),
            ]
        )
        db.commit()
        return {"households": 1, "people": 3}


def main() -> None:
    print(f"Household seed complete: {seed_household_demo()}")


if __name__ == "__main__":
    main()

