from app.scripts.seed_demo import seed_demo_data


class DemoSession:
    committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def scalar(self, statement):
        return None

    def add(self, item):
        item.id = getattr(item, "id", None) or "demo-id"

    def add_all(self, items):
        for item in items:
            item.id = getattr(item, "id", None) or "demo-id"

    def flush(self):
        return None

    def commit(self):
        self.committed = True


def test_demo_seed_is_repeatable_when_branch_exists(monkeypatch) -> None:
    class ExistingBranchSession(DemoSession):
        def scalar(self, statement):
            return object()

    monkeypatch.setattr("app.scripts.seed_demo.SessionLocal", ExistingBranchSession)

    assert seed_demo_data() == {"branches": 0, "members": 0, "visitors": 0, "events": 0}


def test_demo_seed_creates_safe_fake_counts(monkeypatch) -> None:
    monkeypatch.setattr("app.scripts.seed_demo.SessionLocal", DemoSession)

    assert seed_demo_data() == {"branches": 1, "members": 3, "visitors": 2, "events": 2}

