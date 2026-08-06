import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import Branch, ImportBatch, Member, User, Visitor
from app.services.audit import write_audit_log

router = APIRouter()

VALID_IMPORT_TYPES = {"members", "visitors"}
REQUIRED_COLUMNS = {"first_name", "last_name"}
OPTIONAL_COLUMNS = {"phone", "email", "status"}


class ImportPayload(BaseModel):
    import_type: str
    csv_text: str
    file_name: str | None = None


def get_default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create or seed a branch before importing people.",
        )
    return branch


def normalize_import_type(import_type: str) -> str:
    normalized = import_type.strip().lower()
    if normalized not in VALID_IMPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="import_type must be members or visitors.",
        )
    return normalized


def parse_csv(payload: ImportPayload, db: Session) -> list[dict[str, object]]:
    import_type = normalize_import_type(payload.import_type)
    reader = csv.DictReader(io.StringIO(payload.csv_text.strip()))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV must include a header row.")

    headers = {header.strip().lower() for header in reader.fieldnames if header}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CSV is missing required columns: {', '.join(sorted(missing))}.",
        )

    rows: list[dict[str, object]] = []
    for index, raw_row in enumerate(reader, start=2):
        normalized = {
            str(key).strip().lower(): str(value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        row = {key: normalized.get(key) or None for key in REQUIRED_COLUMNS | OPTIONAL_COLUMNS}
        errors: list[str] = []
        if not row["first_name"]:
            errors.append("first_name is required")
        if not row["last_name"]:
            errors.append("last_name is required")
        if row["email"]:
            model = Member if import_type == "members" else Visitor
            email_exists = db.scalar(select(model).where(model.email == row["email"])) is not None
            if email_exists:
                errors.append("email already exists")

        rows.append(
            {
                "row_number": index,
                "status": "valid" if not errors else "error",
                "errors": errors,
                "data": row,
            }
        )
    return rows


def serialize_import(batch: ImportBatch) -> dict[str, object]:
    return {
        "id": str(batch.id),
        "import_type": batch.import_type,
        "file_name": batch.file_name,
        "status": batch.status,
        "total_rows": batch.total_rows,
        "successful_rows": batch.successful_rows,
        "failed_rows": batch.failed_rows,
        "created_at": batch.created_at.isoformat(),
    }


@router.post("/preview")
def preview_import(
    payload: ImportPayload,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("receptionist")),
) -> dict[str, object]:
    rows = parse_csv(payload, db)
    valid_count = sum(1 for row in rows if row["status"] == "valid")
    return {
        "module": "imports",
        "import_type": normalize_import_type(payload.import_type),
        "file_name": payload.file_name,
        "total_rows": len(rows),
        "valid_rows": valid_count,
        "failed_rows": len(rows) - valid_count,
        "rows": rows[:25],
    }


@router.post("/commit", status_code=status.HTTP_201_CREATED)
def commit_import(
    payload: ImportPayload,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("receptionist")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    import_type = normalize_import_type(payload.import_type)
    rows = parse_csv(payload, db)
    valid_rows = [row for row in rows if row["status"] == "valid"]

    batch = ImportBatch(
        branch_id=branch.id,
        import_type=import_type,
        file_name=payload.file_name,
        status="completed" if len(valid_rows) == len(rows) else "completed_with_errors",
        total_rows=len(rows),
        successful_rows=len(valid_rows),
        failed_rows=len(rows) - len(valid_rows),
        created_by=actor.id,
    )
    db.add(batch)
    db.flush()

    for row in valid_rows:
        data = row["data"]
        if import_type == "members":
            db.add(
                Member(
                    branch_id=branch.id,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    phone=data["phone"],
                    email=data["email"],
                    membership_status=data["status"] or "active",
                    joined_at=utc_now(),
                )
            )
        else:
            db.add(
                Visitor(
                    branch_id=branch.id,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    phone=data["phone"],
                    email=data["email"],
                    follow_up_status=data["status"] or "new",
                )
            )

    write_audit_log(
        db,
        actor=actor,
        action="imports.people_imported",
        entity_type="import",
        entity_id=batch.id,
        metadata={
            "import_type": import_type,
            "file_name": payload.file_name,
            "successful_rows": len(valid_rows),
            "failed_rows": len(rows) - len(valid_rows),
        },
    )
    db.commit()
    db.refresh(batch)
    return {
        "module": "imports",
        "import": serialize_import(batch),
        "rows": rows[:25],
    }


@router.get("/{import_id}")
def get_import(
    import_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("receptionist")),
) -> dict[str, object]:
    batch = db.get(ImportBatch, import_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found.")
    return {"module": "imports", "import": serialize_import(batch)}
