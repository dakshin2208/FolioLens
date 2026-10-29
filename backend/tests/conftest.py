import os
import tempfile

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/foliolens_test"
    ),
)
os.environ["RUN_JOBS_INLINE"] = "true"
os.environ["LLM_PROVIDER"] = "none"
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-characters-long"
os.environ["LOCAL_STORAGE_DIR"] = tempfile.mkdtemp(prefix="foliolens-test-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.identity.security import login_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.market_data.demo_seed import seed_demo  # noqa: E402

USER_TABLES = [
    "client_plans",
    "analytics_snapshots",
    "transactions",
    "uploads",
    "consents",
    "portfolios",
    "audit_logs",
    "users",
]


@pytest.fixture(scope="session")
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db(_schema):
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client(_schema):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(USER_TABLES)} CASCADE"))
    login_limiter._attempts.clear()
    return TestClient(app)


def auth_headers(client: TestClient, email: str = "advisor@example.com") -> dict[str, str]:
    pw = "correct-horse-battery"
    client.post("/api/v1/auth/register", json={"email": email, "password": pw})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
