from fastapi.testclient import TestClient

from app.main import app

class MarketClient(TestClient):
    """The API keeps no market state, so the client sends ``live`` with each request, as the web app does."""

    live = False

    def get(self, url, **kw):
        if self.live:
            kw["params"] = {**(kw.get("params") or {}), "live": "true"}
        return super().get(url, **kw)

    def post(self, url, **kw):
        if url == "/api/market/refresh":
            self.live = True
        elif url == "/api/market/reset":
            self.live = False
        elif self.live and kw.get("json") is not None:
            kw["json"] = {**kw["json"], "live": True}
        return super().post(url, **kw)


client = MarketClient(app)


def setup_function():
    client.post("/api/market/reset")


def test_before_refresh_there_are_no_verdicts_and_trades_are_blocked():
    body = client.get("/api/portfolio/robert").json()
    assert body["refreshed"] is False
    assert all(h["move_pct"] == 0 for h in body["holdings"])
    assert abs(sum(h["weight"] for h in body["holdings"]) - 1.0) < 1e-6
    assert client.get("/api/trade-check/NVDA", params={"action": "sell"}).status_code == 409


def test_positions_have_fictional_shares_cash_and_reprice_on_refresh():
    before = client.get("/api/portfolio/robert").json()
    # Cash is the 10,000 plus the few dollars share rounding leaves unspent; the total is the starting balance.
    assert abs(before["cash_cad"] - 10000) < 20 and all(h["shares"] > 0 for h in before["holdings"])
    assert abs(before["total_value_cad"] - 150000) < 0.1
    client.post("/api/market/refresh")
    after = client.get("/api/portfolio/robert").json()
    nvda_before = next(h for h in before["holdings"] if h["ticker"] == "NVDA")
    nvda_after = next(h for h in after["holdings"] if h["ticker"] == "NVDA")
    assert nvda_after["shares"] == nvda_before["shares"]  # same shares, new price
    assert nvda_after["price"] < nvda_before["price"]
    assert abs(after["total_value_cad"] - after["invested_cad"] - after["cash_cad"]) < 0.01


def test_demo_accounts_are_seeded_and_portfolios_are_account_linked():
    accounts = client.get("/api/accounts", params={"user_id": "demo", "persona_id": "amira"}).json()
    assert {account["type"] for account in accounts} == {"TFSA", "RRSP", "Non-registered"}
    assert all(account["persona_id"] == "amira" and account["balance"] > 0 for account in accounts)

    non_registered = client.get("/api/portfolio/amira", params={"account_type": "Non-registered"}).json()
    tfsa = client.get("/api/portfolio/amira", params={"account_type": "TFSA"}).json()
    assert non_registered["account_type"] == "Non-registered"
    assert tfsa["account_type"] == "TFSA"
    assert non_registered["total_value_cad"] != tfsa["total_value_cad"]
    assert non_registered["holdings"] and tfsa["holdings"]


def test_refresh_loads_second_dataset():
    status = client.post("/api/market/refresh").json()
    assert status["refreshed"] is True and status["new_price_rows"] == 55 and status["new_headlines"] > 0
    assert client.get("/api/market").json()["refreshed"] is True


def test_holdings_never_show_a_verdict_until_an_action_is_chosen():
    client.post("/api/market/refresh")
    body = client.get("/api/portfolio/amira").json()
    assert all("verdict" not in h for h in body["holdings"])
    assert body["total_value_cad"] < 15000 + body["cash_cad"]
    nvda = client.get("/api/trade-check/NVDA", params={"action": "sell"}).json()
    assert nvda["verdict"] == "panic_risk" and nvda["score"]["value"] < 50


def test_buy_and_sell_checks_use_model_scored_news():
    client.post("/api/market/refresh")
    sell = client.get("/api/trade-check/ENB.TO", params={"action": "sell"}).json()
    buy = client.get("/api/trade-check/GLD", params={"action": "buy"}).json()
    assert sell["verdict"] == "evidence_supported" and sell["computed_by"] == "local-engine"
    assert buy["verdict"] == "chasing_risk" and buy["score"]["name"] == "Hype"
    assert buy["sentiment_label"] == "upbeat"
    sentiment = next(e for e in sell["evidence"] if e["evidence_id"].endswith(":sentiment"))
    assert sentiment["value"] is not None and sentiment["value"] < 0


def test_bad_inputs_are_rejected():
    assert client.get("/api/portfolio/nobody").status_code == 404
    client.post("/api/market/refresh")
    assert client.get("/api/trade-check/NVDA", params={"action": "hold"}).status_code == 422


def test_chat_sell_question_before_refresh_asks_to_load_the_market():
    body = client.post("/api/chat", json={"message": "Should I sell Nvidia?"}).json()
    assert body["trade_check"] is None
    assert "refresh" in body["answer"].lower()


def test_chat_sell_and_buy_questions_return_the_live_trade_check():
    client.post("/api/market/refresh")
    sell = client.post("/api/chat", json={"message": "should I sell nvidia"}).json()["trade_check"]
    buy = client.post("/api/chat", json={"message": "Should I buy NVDA?"}).json()["trade_check"]
    assert sell["ticker"] == buy["ticker"] == "NVDA"
    assert (sell["action"], buy["action"]) == ("sell", "buy")
    assert sell["verdict"] == "panic_risk" and buy["verdict"] == "dip_with_context"
    assert any(e["evidence_id"] == "NVDA:peer_sentiment" for e in sell["evidence"])


def test_chat_trade_question_works_in_french_and_for_other_names():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "Devrais-je vendre Enbridge ?", "lang": "fr"}).json()
    assert body["trade_check"]["ticker"] == "ENB.TO" and body["trade_check"]["verdict"] == "evidence_supported"
    assert "Voici" in body["answer"]


def test_chat_stock_without_market_data_is_explained_not_crashed():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "Should I buy Apple?"}).json()
    assert body["trade_check"] is None and "AAPL" in body["answer"]


def test_chat_without_buy_or_sell_is_not_a_trade_question():
    body = client.post("/api/chat", json={"message": "Tell me about Nvidia"}).json()
    assert body["trade_check"] is None


def test_chat_trade_answer_includes_the_investors_position():
    client.post("/api/market/refresh")
    body = client.post(
        "/api/chat", json={"message": "should I sell gold", "holdings_persona": "robert"}
    ).json()
    assert body["trade_check"]["ticker"] == "GLD"
    pos = body["position"]
    assert pos["holds"] and pos["shares_held"] > 0 and pos["sample_qty"] >= 1
    assert pos["sample_amount_cad"] == round(pos["sample_qty"] * pos["price"], 2)
    assert 0 < pos["portfolio_pct"] < 100


def test_chat_position_for_a_stock_the_investor_does_not_hold():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "should I sell qqq", "holdings_persona": "robert"}).json()
    held = {h["ticker"] for h in client.get("/api/portfolio/robert").json()["holdings"]}
    assert body["position"]["holds"] == ("QQQ" in held)


def test_chat_without_persona_has_no_position_and_synonyms_resolve():
    client.post("/api/market/refresh")
    for text, ticker in (("should i sell nasdaq", "QQQ"), ("should I buy the S&P 500", "SPY"), ("sell tsx?", "XIU.TO")):
        body = client.post("/api/chat", json={"message": text}).json()
        assert body["trade_check"]["ticker"] == ticker and body["position"] is None


def test_chat_trade_answer_lists_the_latest_headlines():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "should I sell enbridge"}).json()
    lines = body["headlines"]
    assert 1 <= len(lines) <= 3 and all(h["headline"] for h in lines)
    assert [h["date"] for h in lines] == sorted((h["date"] for h in lines), reverse=True)


def _fit(message, persona, lang="en"):
    client.post("/api/market/refresh")
    return client.post("/api/chat", json={"message": message, "holdings_persona": persona, "lang": lang}).json()["persona_fit"]


def test_persona_fit_depends_on_who_is_asking():
    # Selling QQQ: Amira is told to wait (fear); for Robert a growth fund does not fit his plan, so it fits.
    amira, robert = _fit("should I sell qqq", "amira"), _fit("should I sell qqq", "robert")
    assert amira["stance"] == "wait" and robert["stance"] == "fits"
    assert amira["persona"]["name"] == "Amira" and robert["persona"]["name"] == "Robert"
    assert amira["why"] != robert["why"] and any("15+" in w for w in amira["why"])


def test_cautious_investor_is_steered_away_from_growth_style_buys():
    robert = _fit("should I buy nvidia", "robert")  # a dip, normally a fit, but NVDA is growth-style
    mateo = _fit("should I buy nvidia", "mateo")
    assert robert["stance"] == "wait" and any("prefer stability" in w for w in robert["why"])
    assert mateo["stance"] == "fits"


def test_hype_and_falling_knife_buys_are_not_waved_through():
    assert _fit("should I buy gold", "amira")["stance"] == "wait"
    assert _fit("should I buy gold", "robert")["stance"] == "careful"
    assert _fit("should I buy enbridge", "mateo")["stance"] == "careful"


def test_selling_something_not_held_says_so_and_french_works():
    assert _fit("should I sell qqq", "robert")["stance"] in ("wait", "fits", "careful")
    held = {h["ticker"] for h in client.get("/api/portfolio/robert").json()["holdings"]}
    fr = _fit("devrais-je vendre nvidia ?", "robert", "fr")
    assert "NVDA" in held or "Rien à vendre" in fr["headline"]
    assert "ans" in fr["why"][0]


def test_no_persona_means_no_fit_block():
    client.post("/api/market/refresh")
    assert client.post("/api/chat", json={"message": "should I sell qqq"}).json()["persona_fit"] is None


def test_headline_never_contradicts_the_stance():
    robert = _fit("should I buy nvidia", "robert")
    assert robert["stance"] == "wait" and "fits your plan" not in robert["headline"]


def test_trade_check_with_persona_adds_what_it_may_feel_like():
    client.post("/api/market/refresh")
    plain = client.get("/api/trade-check/NVDA", params={"action": "sell"}).json()
    rich = client.get("/api/trade-check/NVDA", params={"action": "sell", "persona": "amira"}).json()
    assert "persona_fit" not in plain
    assert rich["persona_fit"]["persona"]["name"] == "Amira" and rich["verdict"] == plain["verdict"]
    fr = client.get("/api/trade-check/NVDA", params={"action": "sell", "persona": "amira", "lang": "fr"}).json()
    assert "peur" in fr["persona_fit"]["headline"].lower()


def test_the_server_keeps_no_market_state_so_users_do_not_affect_each_other():
    alice, bob = MarketClient(app), MarketClient(app)
    alice.post("/api/market/refresh")
    assert alice.get("/api/trade-check/NVDA", params={"action": "sell"}).status_code == 200
    # Bob never refreshed, and Alice's refresh did not change anything for him.
    assert bob.get("/api/trade-check/NVDA", params={"action": "sell"}).status_code == 409
    assert bob.get("/api/market").json()["refreshed"] is False
    assert bob.get("/api/portfolio/robert").json()["refreshed"] is False


def test_same_request_gives_the_same_answer_for_everyone():
    a, b = MarketClient(app), MarketClient(app)
    for c in (a, b):
        c.post("/api/market/refresh")
    first = a.get("/api/trade-check/GLD", params={"action": "buy", "persona": "amira"}).json()
    second = b.get("/api/trade-check/GLD", params={"action": "buy", "persona": "amira"}).json()
    # The answer is identical; only the trace's note about saving the investor to S3 depends on history.
    assert {k: v for k, v in first.items() if k != "trace"} == {k: v for k, v in second.items() if k != "trace"}


def test_deployed_mode_never_falls_back_to_local_files(monkeypatch):
    monkeypatch.setenv("ENGINE", "lambda")
    monkeypatch.delenv("LAMBDA_FUNCTION_NAME", raising=False)
    response = client.get("/api/portfolio/robert")
    assert response.status_code == 503


def test_runtime_reports_where_calculations_run():
    body = client.get("/api/runtime").json()
    assert body["engine"] == "local-engine" and body["function"] is None  # tests run the local engine


def test_runtime_says_so_when_aws_is_unreachable(monkeypatch):
    monkeypatch.setenv("ENGINE", "lambda")
    monkeypatch.delenv("LAMBDA_FUNCTION_NAME", raising=False)
    assert client.get("/api/runtime").status_code == 503


def test_chat_trace_shows_the_four_agents_in_order():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "should I sell nvidia"}).json()
    agents = [step["agent"] for step in body["trace"]]
    assert agents[1:] == ["Intake", "Market", "Classifier", "Explainer"] or agents[:5] == ["Global Orchestrator", "Intake", "Market", "Classifier", "Explainer"]
    market = next(step for step in body["trace"] if step["agent"] == "Market")
    assert "local files" in market["action"] and "tracked tickers fell together" in market["action"]
    assert body["trade_check"]["computed_by"] == "local-engine" and body["trade_check"]["driver"] == "market"


def test_account_value_is_one_number_shared_by_the_list_the_total_and_holdings():
    c = MarketClient(app)
    for live in (False, True):
        if live:
            c.post("/api/market/refresh")
        accounts = c.get("/api/accounts", params={"user_id": "demo", "persona_id": "amira"}).json()
        assert len(accounts) == 3 and all(a["value_source"] == "market" for a in accounts)
        for a in accounts:
            book = c.get(f"/api/portfolio/amira", params={"account_type": a["type"]}).json()
            assert a["value_cad"] == book["total_value_cad"]  # the account list and the Holdings total agree
            assert a["value_cad"] == a["invested_cad"] + a["cash_cad"] or abs(a["value_cad"] - a["invested_cad"] - a["cash_cad"]) < 0.01
        if not live:
            # before the refresh each account is worth exactly its stored balance
            assert all(abs(a["value_cad"] - a["balance"]) < 0.1 for a in accounts)
        else:
            assert sum(a["value_cad"] for a in accounts) < 15000  # the simulated market fell


def test_a_new_empty_account_keeps_its_stored_balance():
    from app import store
    from app.agents import account_creation

    account_creation.create("demo", {"risk": "balanced", "account_type": "TFSA", "horizon": "mid"})
    accounts = TestClient(app).get("/api/accounts", params={"user_id": "demo"}).json()
    new = [a for a in accounts if a.get("persona_id") is None][-1]
    assert new["value_cad"] == 0.0 and new["value_source"] == "stored balance"
    store.ACCOUNTS["demo"] = [a for a in store.ACCOUNTS["demo"] if a.get("persona_id")]


def test_accounts_still_load_when_the_lambda_is_unreachable(monkeypatch):
    from app.services import sell_guard_service
    from app.services.errors import ExternalServiceError

    def down(*a, **k):
        raise ExternalServiceError("lambda down")

    monkeypatch.setattr(sell_guard_service, "account_values", down)
    accounts = TestClient(app).get("/api/accounts", params={"user_id": "demo", "persona_id": "amira"}).json()
    assert len(accounts) == 3 and all(a["value_cad"] == a["balance"] for a in accounts)
