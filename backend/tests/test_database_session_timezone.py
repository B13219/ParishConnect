from app.db.session import database_connect_args


def test_postgres_connections_explicitly_request_utc():
    assert database_connect_args("postgresql+psycopg://host/db") == {"options": "-c timezone=UTC"}
    assert database_connect_args("sqlite://") == {"check_same_thread": False}
