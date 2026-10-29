def test_ticker_returns_real_day_on_day_changes(client):
    r = client.get("/api/v1/market/ticker")
    assert r.status_code == 200
    items = r.json()
    assert items, "demo universe should produce ticker rows"
    for it in items:
        assert it["prev_close"] > 0
        assert abs(it["change"] - (it["close"] / it["prev_close"] - 1)) < 1e-9
        assert it["symbol"]


def test_ticker_needs_no_login_and_exposes_no_user_data(client):
    r = client.get("/api/v1/market/ticker")
    assert r.status_code == 200
    assert all(
        set(it) == {"symbol", "name", "type", "date", "close", "prev_close", "change", "source"}
        for it in r.json()
    )
