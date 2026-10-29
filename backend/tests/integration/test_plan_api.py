from tests.conftest import auth_headers

API = "/api/v1"
PLAN = {
    "risk_answers": {"age": 3, "horizon": 4, "income": 3, "drop": 3, "experience": 2, "cushion": 3},
    "goals": [
        {
            "name": "Retirement",
            "target_amount": 10000000,
            "target_date": "2045-04-01",
            "monthly_sip": 20000,
            "share_of_portfolio": 0.6,
        }
    ],
}


def _portfolio(client, h):
    return client.post(
        f"{API}/portfolios", json={"name": "Core", "client_name": "Plan Client"}, headers=h
    ).json()["id"]


def test_questions_are_public(client):
    r = client.get(f"{API}/risk-questions")
    assert r.status_code == 200 and len(r.json()["questions"]) == 6


def test_save_and_read_plan(client):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    assert client.get(f"{API}/portfolios/{pid}/plan", headers=h).json()["goals"] == []
    r = client.put(f"{API}/portfolios/{pid}/plan", json=PLAN, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["category"] == "Moderately aggressive"
    assert body["goals"][0]["id"]
    again = client.get(f"{API}/portfolios/{pid}/plan", headers=h).json()
    assert again["goals"][0]["name"] == "Retirement"


def test_plan_validation(client):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    too_much = {
        "goals": [
            dict(PLAN["goals"][0], share_of_portfolio=0.7),
            dict(PLAN["goals"][0], share_of_portfolio=0.4),
        ]
    }
    assert client.put(f"{API}/portfolios/{pid}/plan", json=too_much, headers=h).status_code == 422
    assert (
        client.put(f"{API}/portfolios/{pid}/plan", json={"risk_answers": {"age": 7}}, headers=h).status_code
        == 422
    )


def test_other_advisors_plan_is_not_found(client):
    owner = auth_headers(client, "owner@example.com")
    pid = _portfolio(client, owner)
    client.put(f"{API}/portfolios/{pid}/plan", json=PLAN, headers=owner)
    other = auth_headers(client, "other@example.com")
    assert client.get(f"{API}/portfolios/{pid}/plan", headers=other).status_code == 404
    assert client.put(f"{API}/portfolios/{pid}/plan", json=PLAN, headers=other).status_code == 404


def test_deleting_the_client_deletes_the_plan(client, db):
    from app.planning.models import ClientPlan

    h = auth_headers(client)
    pid = _portfolio(client, h)
    client.put(f"{API}/portfolios/{pid}/plan", json=PLAN, headers=h)
    assert client.delete(f"{API}/portfolios/{pid}", headers=h).status_code == 204
    db.expire_all()
    import uuid

    assert db.get(ClientPlan, uuid.UUID(pid)) is None
