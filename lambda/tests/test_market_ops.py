"""The deployed path: market data only from S3, calculations and scoring inside the Lambda."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import handler  # noqa: E402
import market_store  # noqa: E402
import news_scoring  # noqa: E402
import ops  # noqa: E402

SIM = ROOT / "data" / "simulated"
UNIVERSE = ROOT / "hackathon_info" / "alphaforge_starter" / "assets_universe.csv"
PRESETS = {
    "persona_id": "robert",
    "persona": {"starting_balance_cad": 150000, "starting_cash_cad": 10000,
                "default_allocations": {"preservation": 0.5, "dividend": 0.3, "growth": 0.15, "momentum": 0.05}},
    "strategy_holdings": {
        "growth": {"QQQ": 0.35, "NVDA": 0.25, "SHOP.TO": 0.20, "SPY": 0.20},
        "dividend": {"XIU.TO": 0.30, "ENB.TO": 0.25, "FTS.TO": 0.25, "PG": 0.20},
        "momentum": {"QQQ": 0.40, "SPY": 0.30, "XIU.TO": 0.30},
        "preservation": {"ZST.TO": 0.40, "XBB.TO": 0.30, "GLD": 0.20, "PG": 0.10},
    },
}


class FakeS3:
    """A dict-backed S3 client: the only place the Lambda is allowed to read market data from."""

    def __init__(self, files: dict[str, bytes]):
        self.files = dict(files)
        self.reads: list[str] = []

    def get_object(self, Bucket, Key):
        self.reads.append(Key)
        if Key not in self.files:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.files[Key]), "VersionId": "v1"}

    def head_object(self, Bucket, Key):
        if Key not in self.files:
            err = Exception("missing")
            err.response = {"Error": {"Code": "404"}}
            raise err
        return {}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.files[Key] = Body


def bucket(scored: bool = True) -> FakeS3:
    files: dict[str, bytes] = {"starter/v1/assets_universe.csv": UNIVERSE.read_bytes()}
    records = []
    for folder in market_store.FOLDERS:
        for name in ("prices.csv", "news.csv"):
            body = (SIM / folder / name).read_bytes()
            files[f"simulated/v1/{folder}/{name}"] = body
            records.append({"name": f"{folder}/{name}", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
        if scored:
            files[f"simulated/v1/{folder}/news_scored.csv"] = (SIM / folder / "news_scored.csv").read_bytes()
    files["simulated/v1/manifest.json"] = json.dumps(
        {"dataset_id": "simulated-market-v1", "s3_prefix": "simulated/v1", "files": records}
    ).encode()
    return FakeS3(files)


def stores(client: FakeS3) -> market_store.MarketStores:
    return market_store.MarketStores(
        market=market_store.S3Store("b", "simulated/v1", client), reference=market_store.S3Store("b", "starter/v1", client)
    )


class FakeBedrock:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def converse(self, **kw):
        self.calls.append(kw["modelId"])
        text = kw["messages"][0]["content"][0]["text"]
        reply = self.answers(kw["modelId"], text)
        return {"output": {"message": {"content": [{"text": json.dumps(reply)}]}}}


class MarketOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        market_store.clear_cache()

    def test_everything_is_read_from_s3(self) -> None:
        client = bucket()
        result = ops.run({"operation": "trade_check", "action": "sell", "ticker": "NVDA", "live": True}, stores(client))
        self.assertEqual(result["trade_check"]["verdict"], "panic_risk")
        self.assertEqual(result["computed_by"], "aws-lambda")
        self.assertTrue(all(src.startswith("s3://") for src in result["data_sources"]))
        self.assertIn("simulated/v1/manifest.json", client.reads)

    def test_a_tampered_file_is_rejected_by_the_manifest(self) -> None:
        client = bucket()
        client.files["simulated/v1/current/prices.csv"] += b"\n2026-11-12,NVDA,1,1,1,1,1,1,USD"
        with self.assertRaisesRegex(ValueError, "checksum|byte count"):
            ops.run({"operation": "market_status", "live": True}, stores(client))

    def test_scored_headlines_are_preferred_and_raw_ones_are_the_fallback(self) -> None:
        scored = ops.run({"operation": "sentiment_summary", "ticker": "ENB.TO", "live": True}, stores(bucket(True)))
        market_store.clear_cache()  # the 60-second cache is keyed by bucket and prefix
        raw = ops.run({"operation": "sentiment_summary", "ticker": "ENB.TO", "live": True}, stores(bucket(False)))
        self.assertLess(scored["mean_sentiment"], -0.3)
        self.assertIsNone(raw["mean_sentiment"])  # raw headlines carry no score

    def test_not_live_means_no_trade_check(self) -> None:
        with self.assertRaisesRegex(ValueError, "refresh the live market"):
            ops.run({"operation": "trade_check", "action": "sell", "ticker": "NVDA", "live": False}, stores(bucket()))

    def test_portfolio_and_position_come_from_the_same_call(self) -> None:
        event = {"operation": "trade_check", "action": "buy", "ticker": "GLD", "live": True, **PRESETS}
        result = ops.run(event, stores(bucket()))
        self.assertTrue(result["position"]["holds"])
        self.assertEqual(result["position"]["sample_amount_cad"], round(result["position"]["sample_qty"] * result["position"]["price"], 2))
        self.assertLessEqual(len(result["headlines"]), 3)
        snap = ops.run({"operation": "portfolio_snapshot", "live": True, **PRESETS}, stores(bucket()))
        self.assertAlmostEqual(snap["total_value_cad"], snap["invested_cad"] + snap["cash_cad"], places=2)

    def test_two_runs_give_identical_answers(self) -> None:
        event = {"operation": "trade_check", "action": "sell", "ticker": "QQQ", "live": True, **PRESETS}
        self.assertEqual(ops.run(event, stores(bucket())), ops.run(event, stores(bucket())))

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ops.run({"operation": "drop_tables"}, stores(bucket()))


class ScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        market_store.clear_cache()

    @staticmethod
    def negative(model_id, text):
        return {"sentiment": -0.6 if "ENB" not in text else -0.9, "scope": "company" if "pipeline" in text.lower() else "market", "category": "operations"}

    def test_scoring_runs_in_the_lambda_and_writes_back_to_s3(self) -> None:
        client = bucket(scored=False)
        bedrock = FakeBedrock(self.negative)
        result = news_scoring.score_market_news(stores(client), bedrock, ["m1", "m2"], names={})
        for folder in market_store.FOLDERS:
            self.assertIn(f"simulated/v1/{folder}/news_scored.csv", client.files)
        written = client.files["simulated/v1/marketchange/news_scored.csv"].decode()
        self.assertIn("model_spread", written.splitlines()[0])
        self.assertEqual(result["scope_agreement"]["total"], len(bedrock.calls) // 2)  # two models per headline
        # the next read sees the new scores
        summary = ops.run({"operation": "sentiment_summary", "ticker": "ENB.TO", "live": True}, stores(client))
        self.assertLess(summary["mean_sentiment"], -0.3)

    def test_models_that_disagree_are_flagged_and_the_median_wins(self) -> None:
        votes = {"a": -0.8, "b": -0.7, "c": 0.9}
        bedrock = FakeBedrock(lambda m, t: {"sentiment": votes[m], "scope": "market", "category": "market"})
        result = news_scoring.score_headline(bedrock, ["a", "b", "c"], "Ticker: X\nHeadline: y")
        self.assertEqual(result["sentiment"], -0.7)
        self.assertFalse(result["agreement"])

    def test_bad_model_output_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            news_scoring.parse('{"sentiment": 5, "scope": "company"}')
        self.assertEqual(news_scoring.parse('{"sentiment": 0.2, "scope": "market", "category": "bogus"}')[2], "other")

    def test_only_known_folders_can_be_scored(self) -> None:
        with self.assertRaises(ValueError):
            news_scoring.score_market_news(stores(bucket()), FakeBedrock(self.negative), ["m"], folders=["../secrets"], names={})


class HandlerTests(unittest.TestCase):
    def test_handler_serves_market_operations_from_s3_only(self) -> None:
        market_store.clear_cache()
        client = bucket()
        env = {"DATA_BUCKET": "b", "MARKET_PREFIX": "simulated/v1", "DATA_PREFIX": "starter/v1"}
        with mock.patch.dict(os.environ, env), mock.patch.object(market_store.S3Store, "client", client):
            out = handler.handler({"operation": "market_status", "live": True}, mock.Mock(aws_request_id="r1"))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["new_price_rows"], 55)
        self.assertEqual(out["aws_request_id"], "r1")

    def test_handler_reports_errors_instead_of_crashing(self) -> None:
        out = handler.handler({"operation": "nope"}, mock.Mock(aws_request_id="r2"))
        self.assertEqual(out["status"], "error")

    def test_handler_requires_the_bucket(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            out = handler.handler({"operation": "market_status", "live": True}, mock.Mock(aws_request_id="r3"))
        self.assertEqual(out["status"], "error")
        self.assertIn("DATA_BUCKET", out["error"])


if __name__ == "__main__":
    unittest.main()


class AgentStepTests(unittest.TestCase):
    """The Market and Classifier agents run as separate Lambda operations and compose to the same verdict."""

    def setUp(self) -> None:
        market_store.clear_cache()

    def test_market_then_classifier_equals_the_combined_check(self) -> None:
        s = stores(bucket())
        market = ops.run({"operation": "market_agent", "ticker": "NVDA", "live": True}, s)["market"]
        classified = ops.run({"operation": "classifier_agent", "action": "sell", "market": market}, s)
        combined = ops.run({"operation": "trade_check", "action": "sell", "ticker": "NVDA", "live": True}, s)
        self.assertEqual(classified["trade_check"], combined["trade_check"])
        self.assertEqual(classified["trade_check"]["driver"], "market")  # a market-wide selloff

    def test_market_agent_reports_what_changed_with_citable_ids(self) -> None:
        market = ops.run({"operation": "market_agent", "ticker": "QQQ", "live": True}, stores(bucket()))["market"]
        ids = [e["evidence_id"] for e in market["evidence"]]
        self.assertEqual(ids, ["QQQ:drop", "QQQ:rise", "QQQ:volume", "QQQ:rebound", "QQQ:breadth", "QQQ:daily_move", "QQQ:drop_size", "QQQ:market_drop"])
        self.assertGreater(market["tickers_falling_together"], 0)
        self.assertGreater(market["tracked_tickers"], market["tickers_falling_together"])

    def test_driver_is_company_for_company_news(self) -> None:
        s = stores(bucket())
        market = ops.run({"operation": "market_agent", "ticker": "ENB.TO", "live": True}, s)["market"]
        self.assertEqual(ops.run({"operation": "classifier_agent", "action": "sell", "market": market}, s)["trade_check"]["driver"], "company")

    def test_classifier_requires_a_valid_action(self) -> None:
        s = stores(bucket())
        market = ops.run({"operation": "market_agent", "ticker": "NVDA", "live": True}, s)["market"]
        with self.assertRaises(ValueError):
            ops.run({"operation": "classifier_agent", "action": "short", "market": market}, s)

    def test_position_is_its_own_operation(self) -> None:
        out = ops.run({"operation": "investor_position", "action": "sell", "ticker": "GLD", "live": True, **PRESETS}, stores(bucket()))
        self.assertTrue(out["position"]["holds"])


class AccountValueTests(unittest.TestCase):
    """One value per account, the same everywhere, and cash is not counted twice."""

    ACCOUNTS = [
        {"account_type": "TFSA", "account": {"share": 0.30, "cash_share": 0.08, "allocations": {"growth": 0.5, "dividend": 0.2, "momentum": 0.2, "preservation": 0.1}}},
        {"account_type": "RRSP", "account": {"share": 0.20, "cash_share": 0.10, "allocations": {"growth": 0.25, "dividend": 0.35, "momentum": 0.10, "preservation": 0.30}}},
    ]
    AMIRA = {**PRESETS, "persona_id": "amira", "persona": {**PRESETS["persona"], "starting_balance_cad": 15000, "starting_cash_cad": 2000}}

    def setUp(self) -> None:
        market_store.clear_cache()

    def values(self, live: bool):
        return ops.run({"operation": "account_values", "live": live, "accounts": self.ACCOUNTS, **self.AMIRA}, stores(bucket()))["values"]

    def test_before_the_refresh_an_account_is_worth_exactly_its_balance(self) -> None:
        values = self.values(False)
        self.assertAlmostEqual(values["TFSA"]["value_cad"], 4500, delta=0.1)  # 30% of 15,000
        self.assertAlmostEqual(values["RRSP"]["value_cad"], 3000, delta=0.1)  # 20% of 15,000
        for v in values.values():
            self.assertAlmostEqual(v["value_cad"], v["invested_cad"] + v["cash_cad"], places=2)
            self.assertAlmostEqual(v["value_cad"], v["starting_balance_cad"], delta=0.1)

    def test_after_the_refresh_the_value_moves_with_the_market(self) -> None:
        before, after = self.values(False), self.values(True)
        self.assertLess(after["TFSA"]["value_cad"], before["TFSA"]["value_cad"])  # the simulated move is a drop
        self.assertEqual(after["TFSA"]["cash_cad"], before["TFSA"]["cash_cad"])  # cash does not move

    def test_the_value_is_exactly_the_holdings_snapshot_total(self) -> None:
        s = stores(bucket())
        for live in (False, True):
            values = self.values(live)
            for item in self.ACCOUNTS:
                snap = ops.run({"operation": "portfolio_snapshot", "live": live, "account_type": item["account_type"], "account": item["account"], **self.AMIRA}, s)
                self.assertEqual(values[item["account_type"]]["value_cad"], snap["total_value_cad"])
