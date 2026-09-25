"""Run actual mobile TypeScript services against a disposable local FastAPI fixture.

Run from the repo root with backend dev dependencies installed. Never reads a
production database URL or asks for production credentials.
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from sqlalchemy import create_engine

MOBILE = Path(__file__).resolve().parents[1]
REPO = MOBILE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
from tests.test_global_identity import identity


def main():
    with tempfile.TemporaryDirectory(prefix="vinyrd-mobile-contract-") as temp:
        compiled = Path(temp).resolve()
        subprocess.run(
            [
                "node",
                str(MOBILE / "node_modules/typescript/bin/tsc"),
                "--ignoreConfig",
                "--skipLibCheck",
                "--target",
                "es2022",
                "--module",
                "node16",
                "--moduleResolution",
                "node16",
                "--outDir",
                str(compiled),
                "services/api.ts",
                "services/session.ts",
                "services/networkState.ts",
                "services/endpoints.ts",
            ],
            cwd=MOBILE,
            check=True,
        )
        fixture = identity.__wrapped__()
        client, sessions, ids = next(fixture)
        database_path = compiled / "contract.sqlite"
        with (
            sessions.kw["bind"].connect() as source,
            sqlite3.connect(database_path) as target,
        ):
            source.connection.driver_connection.backup(target)
        target.close()
        database = create_engine(
            "sqlite:///" + database_path.as_posix(),
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        sessions.configure(bind=database)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(client.app, host="127.0.0.1", port=port, log_level="error")
        )
        worker = threading.Thread(target=server.run, daemon=True)
        worker.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("Disposable test server did not start")
            env = {
                **os.environ,
                "VINYRD_COMPILED_SERVICES": str(compiled),
                "VINYRD_LOCAL_TEST_API": f"http://127.0.0.1:{port}/api/v1",
                "VINYRD_TEST_IDS": json.dumps(ids),
            }
            subprocess.run(
                ["node", "scripts/live-contract.cjs"], cwd=MOBILE, env=env, check=True
            )
        finally:
            server.should_exit = True
            worker.join(timeout=10)
            fixture.close()
            database.dispose()


if __name__ == "__main__":
    main()
