from app.db.base import Base
from app.models import (
    AttendanceRecord,
    AuditLog,
    Branch,
    Contribution,
    Event,
    ImportBatch,
    Member,
    Message,
    MessageRecipient,
    Ministry,
    Role,
    User,
    UserRole,
    Visitor,
)


def test_initial_database_tables_are_registered() -> None:
    expected_tables = {
        "attendance_records",
        "audit_logs",
        "branches",
        "contributions",
        "events",
        "imports",
        "members",
        "messages",
        "message_recipients",
        "ministries",
        "roles",
        "user_roles",
        "users",
        "visitors",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_models_import_for_migration_discovery() -> None:
    assert all(
        [
            AttendanceRecord,
            AuditLog,
            Branch,
            Contribution,
            Event,
            ImportBatch,
            Member,
            Message,
            MessageRecipient,
            Ministry,
            Role,
            User,
            UserRole,
            Visitor,
        ]
    )
