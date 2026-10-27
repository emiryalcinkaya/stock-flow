import os

# Must be set before the app (and its settings) are imported.
os.environ["database_url"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://stockflow_user:stockflow_password@localhost:5432/stockflow_test",
)
os.environ.setdefault("secret_key", "test-secret-key-that-is-long-enough")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.api.v1.endpoints.auth import login_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.seed import seed_all  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

PASSWORDS = {"admin": "admin123", "cashier": "cashier123"}


@pytest.fixture(scope="session", autouse=True)
def database_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_database():
    table_names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))

    seed_all()
    login_limiter.reset()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client: TestClient, username: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORDS[username]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return auth_headers(client, "admin")


@pytest.fixture
def cashier_headers(client):
    return auth_headers(client, "cashier")


@pytest.fixture
def make_product(client, admin_headers):
    counter = {"n": 0}

    def _make(name="Widget", price=10.0, stock=10, barcode=None, **extra):
        counter["n"] += 1
        response = client.post(
            "/api/v1/products/",
            json={
                "name": name,
                "barcode": barcode or f"BC-{counter['n']:04d}",
                "price": price,
                "stock_quantity": stock,
                **extra,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make
