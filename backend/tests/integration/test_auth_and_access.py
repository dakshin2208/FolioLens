from tests.conftest import auth_headers

API = "/api/v1"


def test_register_login_me(client):
    r = client.post(f"{API}/auth/register", json={"email": "A@Example.com", "password": "long-enough-pw"})
    assert r.status_code == 201
    assert (
        client.post(
            f"{API}/auth/register", json={"email": "a@example.com", "password": "long-enough-pw"}
        ).status_code
        == 409
    )
    token = client.post(
        f"{API}/auth/login", json={"email": "a@example.com", "password": "long-enough-pw"}
    ).json()
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.json()["email"] == "a@example.com"


def test_short_password_rejected(client):
    r = client.post(f"{API}/auth/register", json={"email": "b@example.com", "password": "short"})
    assert r.status_code == 422


def test_wrong_password_and_rate_limit(client):
    client.post(f"{API}/auth/register", json={"email": "c@example.com", "password": "long-enough-pw"})
    codes = [
        client.post(
            f"{API}/auth/login", json={"email": "c@example.com", "password": "wrong-password"}
        ).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_requires_authentication(client):
    assert client.get(f"{API}/portfolios").status_code == 401
    assert client.get(f"{API}/portfolios", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_users_cannot_see_each_others_portfolios(client):
    alice = auth_headers(client, "alice@example.com")
    bob = auth_headers(client, "bob@example.com")
    pid = client.post(
        f"{API}/portfolios", json={"name": "Core", "client_name": "Client A"}, headers=alice
    ).json()["id"]
    for path in ("", "/uploads", "/transactions", "/report", "/holdings", "/risk"):
        assert client.get(f"{API}/portfolios/{pid}{path}", headers=bob).status_code == 404, path
    assert client.delete(f"{API}/portfolios/{pid}", headers=bob).status_code == 404
    assert client.get(f"{API}/portfolios", headers=bob).json() == []
    assert client.get(f"{API}/portfolios/{pid}", headers=alice).status_code == 200


def test_demo_report_needs_no_login(client):
    r = client.get(f"{API}/demo/report")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["synthetic"] is True
    assert body["findings"] and all(f["explanation"] for f in body["findings"])
