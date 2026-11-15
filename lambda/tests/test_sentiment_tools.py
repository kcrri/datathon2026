"""Tests for the sentiment taxonomy, decay, peer, voting and backtest helpers."""
from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import backtest  # noqa: E402
import sentiment_tools as st  # noqa: E402
from sell_guard import evaluate_trade  # noqa: E402

SIM = ROOT / "data" / "simulated"
UNIVERSE = ROOT / "hackathon_info" / "alphaforge_starter" / "assets_universe.csv"


def rows(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


class TaxonomyTests(unittest.TestCase):
    def test_keyword_categories(self) -> None:
        cases = {
            "Regulator orders pipeline operator to halt a segment pending safety review": "regulatory",
            "Rating agency places pipeline operator on review for possible downgrade": "credit_rating",
            "Pipeline operator reaffirms dividend and steady volumes": "dividend",
            "Chipmaker posts steady data-centre demand in quarterly update": "earnings",
            "Pipeline operator says repairs will take longer than first expected": "operations",
            "Rival launches cheaper product to win market share": "competitor",
        }
        for headline, expected in cases.items():
            with self.subTest(headline=headline):
                self.assertEqual(st.classify_category(headline), expected)

    def test_market_scope_is_always_market(self) -> None:
        self.assertEqual(st.classify_category("Earnings season starts", scope="market"), "market")

    def test_model_category_wins_when_valid(self) -> None:
        row = {"headline": "anything", "scope": "company", "category": "legal"}
        self.assertEqual(st.row_category(row), "legal")
        self.assertEqual(st.row_category({**row, "category": "nonsense"}), "other")


class DecayTests(unittest.TestCase):
    def test_half_life(self) -> None:
        self.assertEqual(st.decay_weight(0, 3), 1.0)
        self.assertAlmostEqual(st.decay_weight(3, 3), 0.5)
        self.assertAlmostEqual(st.decay_weight(6, 3), 0.25)

    def test_recent_headlines_weigh_more(self) -> None:
        news = [
            {"date": "2026-11-10", "sentiment": "-0.8"},
            {"date": "2026-11-19", "sentiment": "0.8"},
        ]
        plain = st.weighted_sentiment(news, "2026-11-19")
        decayed = st.weighted_sentiment(news, "2026-11-19", half_life_days=2)
        self.assertAlmostEqual(plain, 0.0)
        self.assertGreater(decayed, 0.5)

    def test_missing_sentiment_is_none(self) -> None:
        self.assertIsNone(st.weighted_sentiment([{"date": "2026-11-19", "sentiment": ""}], "2026-11-19"))

    def test_invalid_half_life_rejected(self) -> None:
        with self.assertRaises(ValueError):
            st.decay_weight(1, 0)


class PeerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.peers = st.peer_groups(rows(UNIVERSE))
        cls.news = rows(SIM / "current" / "news_scored.csv") + rows(SIM / "marketchange" / "news_scored.csv")

    def test_groups_are_symmetric_and_exclude_self(self) -> None:
        for ticker, related in self.peers.items():
            self.assertNotIn(ticker, related)
            for other in related:
                self.assertIn(ticker, self.peers[other])

    def test_index_funds_are_peers(self) -> None:
        self.assertIn("SPY", self.peers["QQQ"])
        self.assertIn("XIU.TO", self.peers["SPY"])

    def test_peer_sentiment_uses_related_tickers_only(self) -> None:
        result = st.peer_sentiment(self.news, "QQQ", self.peers, "2026-11-13", "2026-11-19")
        self.assertIn("SPY", result["peers_with_news"])
        self.assertNotIn("QQQ", result["peers_with_news"])
        self.assertLess(result["peer_sentiment"], 0)  # the selloff headlines on SPY

    def test_no_peer_news_gives_none(self) -> None:
        result = st.peer_sentiment([], "QQQ", self.peers, "2026-11-13", "2026-11-19")
        self.assertIsNone(result["peer_sentiment"])


class VotingTests(unittest.TestCase):
    def test_median_ignores_one_outlier(self) -> None:
        result = st.aggregate_votes([-0.7, -0.6, 0.9])
        self.assertEqual(result["sentiment"], -0.6)
        self.assertFalse(result["agreement"])

    def test_agreement_when_close(self) -> None:
        result = st.aggregate_votes([0.5, 0.6, 0.7])
        self.assertTrue(result["agreement"])
        self.assertEqual(result["votes"], 3)

    def test_empty_votes(self) -> None:
        self.assertIsNone(st.aggregate_votes([])["sentiment"])

    def test_majority_label_is_stable_on_ties(self) -> None:
        self.assertEqual(st.majority_label(["a", "b", "b", "a"]), "a")
        self.assertEqual(st.majority_label(["market", "company", "company"]), "company")


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.current = rows(SIM / "current" / "prices.csv")
        cls.change = rows(SIM / "marketchange" / "prices.csv")
        cls.news = rows(SIM / "current" / "news_scored.csv") + rows(SIM / "marketchange" / "news_scored.csv")
        cls.peers = st.peer_groups(rows(UNIVERSE))

    def test_peers_and_decay_do_not_change_default_verdicts(self) -> None:
        for ticker in ("NVDA", "ENB.TO", "GLD"):
            plain = evaluate_trade("sell", ticker, self.current, self.change, self.news, "2026-11-19")
            rich = evaluate_trade("sell", ticker, self.current, self.change, self.news, "2026-11-19", peers=self.peers)
            self.assertEqual(plain["verdict"], rich["verdict"])

    def test_evidence_includes_new_signals_and_categories(self) -> None:
        result = evaluate_trade("sell", "ENB.TO", self.current, self.change, self.news, "2026-11-19", peers=self.peers)
        ids = {e["evidence_id"] for e in result["evidence"]}
        self.assertIn("ENB.TO:decayed_sentiment", ids)
        self.assertIn("ENB.TO:peer_sentiment", ids)
        self.assertIn("regulatory", result["headline_categories"])

    def test_decay_option_is_opt_in(self) -> None:
        base = evaluate_trade("sell", "ENB.TO", self.current, self.change, self.news, "2026-11-19")
        decayed = evaluate_trade("sell", "ENB.TO", self.current, self.change, self.news, "2026-11-19", half_life_days=2)
        self.assertEqual(base["verdict"], decayed["verdict"])
        self.assertNotEqual(base["sentiment"], decayed["sentiment"])

    def test_backtest_scores_only_claims_and_is_deterministic(self) -> None:
        a = backtest.backtest(self.current, self.change, self.news, peers=self.peers)
        b = backtest.backtest(self.current, self.change, self.news, peers=self.peers)
        self.assertEqual(a, b)
        self.assertEqual(a["scored"] + a["unscored"], a["evaluations"])
        self.assertTrue(all(r["correct"] is None for r in a["rows"] if not r["scored"]))
        self.assertGreater(a["scored"], 0)


if __name__ == "__main__":
    unittest.main()
