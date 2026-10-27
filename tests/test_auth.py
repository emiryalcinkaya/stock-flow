from app.core.security import create_access_token
from app.db.models.user import User


def test_login_success_and_me(client, admin_headers):
    response = client.get("/api/v1/auth/me", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_login_wrong_password(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_login_unknown_user_same_error(client):
    response = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "nope"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_rate_limited_after_repeated_failures(client):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})

    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})

    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_protected_endpoints_require_token(client):
    for path in ["/api/v1/products/", "/api/v1/sales/", "/api/v1/dashboard/summary", "/api/v1/auth/me"]:
        assert client.get(path).status_code == 401, path


def test_invalid_token_rejected(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_inactive_user_token_rejected(client, db, cashier_headers):
    user = db.query(User).filter(User.username == "cashier").first()
    user.is_active = False
    db.commit()

    response = client.get("/api/v1/auth/me", headers=cashier_headers)
    assert response.status_code == 401


def test_token_for_deleted_user_rejected(client):
    token = create_access_token("9999")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
