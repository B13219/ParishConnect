#!/usr/bin/env bash
# Run only against the disposable PostgreSQL service provided by backend CI.
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(git rev-parse HEAD)" = "$GITHUB_SHA"
ARTIFACTS="${RUNNER_TEMP}/vinyrd-container-validation"
mkdir -p "$ARTIFACTS"
IMAGE="vinyrd-validation:${GITHUB_SHA}"
BOOT="vinyrd-validation-bootstrap"
API="vinyrd-validation-api"
export PGPASSWORD=parishconnect
export VINYRD_PILOT_BASE_URL=http://127.0.0.1:8004
export VINYRD_SMOKE_DISPOSABLE_DATABASE=1
OWNER_URL=postgresql+psycopg://parishconnect:parishconnect@127.0.0.1:5432/vinyrd_container_validation
RUNTIME_URL=postgresql+psycopg://vinyrd_container_runtime:container-runtime-validation-only@127.0.0.1:5432/vinyrd_container_validation

cleanup() {
  docker logs "$BOOT" > "$ARTIFACTS/bootstrap.log" 2>&1 || true
  docker logs "$API" > "$ARTIFACTS/runtime.log" 2>&1 || true
  docker rm -f "$BOOT" "$API" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build --label "org.opencontainers.image.revision=$GITHUB_SHA" -f Dockerfile -t "$IMAGE" . 2>&1 | tee "$ARTIFACTS/build.log"
createdb -h 127.0.0.1 -U parishconnect vinyrd_container_validation
test "$(psql -h 127.0.0.1 -U parishconnect -d vinyrd_container_validation -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")" = 0
psql -h 127.0.0.1 -U parishconnect -d postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE vinyrd_container_validation SET timezone TO 'UTC'"

psql -h 127.0.0.1 -U parishconnect -d postgres -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE vinyrd_container_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD 'container-runtime-validation-only';
CREATE ROLE vinyrd_container_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD 'container-backup-validation-only';
CREATE ROLE vinyrd_container_restore LOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD 'container-restore-validation-only';
SQL
BACKUP_URL=postgresql+psycopg://vinyrd_container_backup:container-backup-validation-only@127.0.0.1:5432/vinyrd_container_validation
RESTORE_URL=postgresql+psycopg://vinyrd_container_restore:container-restore-validation-only@127.0.0.1:5432/postgres
export PARISHCONNECT_DATABASE_URL="$RUNTIME_URL"
export PARISHCONNECT_MIGRATION_DATABASE_URL="$OWNER_URL"
export PORT=8004
export PGTZ=UTC
python - "$ARTIFACTS/owner.env" <<'PY'
import os, sys
from pathlib import Path
values = {k: v for k, v in os.environ.items() if k.startswith(("PARISHCONNECT_", "VINYRD_")) or k in ("PORT", "PGTZ")}
Path(sys.argv[1]).write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
PY

wait_for_health() {
  for attempt in {1..60}; do
    if curl --fail --silent "$VINYRD_PILOT_BASE_URL/health" > "$ARTIFACTS/health.json"; then return 0; fi
    sleep 1
  done
  return 1
}

# Exercise the production CMD on the empty database: migrate, bootstrap, serve.
docker run -d --name "$BOOT" --network host --env-file "$ARTIFACTS/owner.env" "$IMAGE"
wait_for_health
docker exec "$BOOT" python -c "import subprocess; versions=[subprocess.check_output([tool,'--version'],text=True).strip() for tool in ('pg_dump','pg_restore')]; print('\n'.join(versions)); assert all(version.split()[2].startswith('16.') for version in versions)" | tee "$ARTIFACTS/postgres-client-versions.log"
docker exec "$BOOT" python -m alembic current | tee "$ARTIFACTS/migration-current.log"
docker exec "$BOOT" python -c "from app.db.session import engine; from sqlalchemy import text; c=engine.connect(); assert c.scalar(text('SELECT version_num FROM alembic_version')) == '20260930_0021'; assert c.scalar(text('SHOW timezone')) == 'UTC'; assert c.scalar(text('SELECT count(*) FROM organization_units')) == 0"
docker exec "$BOOT" python -m app.scripts.check_deployment_readiness --strict --allow-local-database --check-database
docker logs "$BOOT" > "$ARTIFACTS/bootstrap.log" 2>&1
docker stop --time 10 "$BOOT"

# Subsequent HTTP starts require only runtime credentials.
docker run --rm --network host --env-file "$ARTIFACTS/owner.env" "$IMAGE" python -m app.scripts.provision_database_access --runtime-role vinyrd_container_runtime --backup-role vinyrd_container_backup
# BOOT was stopped after collecting evidence; use an isolated one-off operator process.
docker run -d --name "$API" --network host --env-file "$ARTIFACTS/owner.env" \
  -e PARISHCONNECT_MIGRATION_DATABASE_URL= -e PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD= \
  "$IMAGE"
wait_for_health
docker exec "$API" python -c "from app.db.session import engine; from sqlalchemy import text; c=engine.connect(); assert c.scalar(text('SHOW timezone')) == 'UTC'; assert c.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one() == (False,False)"
curl --fail --silent "$VINYRD_PILOT_BASE_URL/staff/organization-admin.js" > /dev/null
docker exec -e "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD=$PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD" "$API" python -m app.scripts.pilot_smoke | tee "$ARTIFACTS/pilot-before.log"
docker exec -e "PARISHCONNECT_DATABASE_URL=$OWNER_URL" -e "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD=$PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD" "$API" python -m app.scripts.organization_smoke | tee "$ARTIFACTS/organization-smoke.log"
docker exec -e "PARISHCONNECT_DATABASE_URL=$OWNER_URL" "$API" python -m app.scripts.authority_bootstrap_smoke | tee "$ARTIFACTS/authority-bootstrap.log"
docker exec -e "PARISHCONNECT_DATABASE_URL=$OWNER_URL" "$API" python -m app.scripts.organization_access_smoke | tee "$ARTIFACTS/organization-access-smoke.log"
docker exec -e "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD=$PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD" "$API" python -m app.scripts.pilot_smoke | tee "$ARTIFACTS/pilot-after.log"
docker exec -e "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD=$PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD" "$API" python -m app.scripts.template_governance_smoke | tee "$ARTIFACTS/template-governance-smoke.log"
docker exec -e "PARISHCONNECT_BACKUP_DATABASE_URL=$BACKUP_URL" -e "PARISHCONNECT_RESTORE_DATABASE_URL=$RESTORE_URL" -e "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD=$PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD" "$API" python -m app.scripts.verify_backup_restore --acceptance-smoke --backup-path /tmp/vinyrd-container.dump | tee "$ARTIFACTS/backup-restore.log"
docker restart --time 10 "$API"
wait_for_health
docker exec "$API" python -m app.scripts.check_deployment_readiness --strict --allow-local-database --check-database
printf 'Validated commit: %s\nDocker build, clean migration, startup, health, readiness, pilot, organization smoke, tenant isolation, backup and runtime restart passed.\n' "$GITHUB_SHA" | tee "$ARTIFACTS/result.txt"
# Do not upload environment files or the database dump.
rm "$ARTIFACTS/owner.env"
