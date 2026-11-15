"""Macro Signal Agent: rates, yield curve, unemployment from the starter dataset."""
import csv
import io
import math
from typing import Any, Dict, List

from app import i18n
from app.services import reference_data
REQUIRED_SERIES = {
    "DGS10",
    "DGS2",
    "BD.CDN.10YR.DQ.YLD",
    "BD.CDN.2YR.DQ.YLD",
    "UNRATE",
}


def _series() -> Dict[str, List[tuple]]:
    out: Dict[str, List[tuple]] = {}
    seen = set()
    # rows come from S3 when deployed, from the starter folder only for tests
    for row in csv.DictReader(io.StringIO(reference_data.read_text("macro_rates.csv"))):
        series_id = row.get("series_id", "")
        date = row.get("date", "")
        value = float(row.get("value", ""))
        if not series_id or not date or not math.isfinite(value):
            raise ValueError("macro dataset contains an invalid observation")
        key = (series_id, date)
        if key in seen:
            raise ValueError(f"macro dataset contains duplicate observation: {series_id} {date}")
        seen.add(key)
        out.setdefault(series_id, []).append((date, value))
    for v in out.values():
        v.sort()
    missing = REQUIRED_SERIES.difference(out)
    if missing:
        raise ValueError(f"macro dataset is missing required series: {', '.join(sorted(missing))}")
    if len(out["UNRATE"]) < 13:
        raise ValueError("macro dataset needs at least 13 unemployment observations")
    return out


def recession_signals(lang: str = "en") -> Dict[str, Any]:
    fr = i18n.normalize(lang) == "fr"
    try:
        s = _series()
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        return {
            "metrics": {},
            "sources": [],
            "warnings": [
                f"Les indicateurs macroéconomiques historiques sont indisponibles : {exc}"
                if fr
                else f"Historical macro indicators are unavailable: {exc}"
            ],
        }

    us10, us2 = s["DGS10"][-1], s["DGS2"][-1]
    ca10, ca2 = s["BD.CDN.10YR.DQ.YLD"][-1], s["BD.CDN.2YR.DQ.YLD"][-1]
    unrate = s["UNRATE"]
    un_now = unrate[-1]
    un_low_12m = min(v for _, v in unrate[-13:-1])

    us_spread = round(us10[1] - us2[1], 2)
    ca_spread = round(ca10[1] - ca2[1], 2)
    un_change = round(un_now[1] - un_low_12m, 2)

    notes = []
    if fr:
        notes.append(
            f"La courbe des taux américaine (10 ans − 2 ans) est de {us_spread:+.2f} pt le {us10[0]} : "
            + ("inversée, un signal d'alerte historique." if us_spread < 0 else "non inversée.")
        )
        notes.append(
            f"La courbe des taux canadienne (10 ans − 2 ans) est de {ca_spread:+.2f} pt le {ca10[0]} : "
            + ("inversée." if ca_spread < 0 else "non inversée.")
        )
        notes.append(
            f"Le chômage américain est de {un_now[1]} % ({un_now[0]}), {un_change:+.2f} pt par rapport à son creux sur 12 mois"
            + (" : une forte hausse, souvent observée près des récessions." if un_change >= 0.5 else " : pas de forte hausse.")
        )
    else:
        notes.append(
            f"U.S. yield curve (10y − 2y) is {us_spread:+.2f} pts on {us10[0]}: "
            + ("inverted, a historical warning sign." if us_spread < 0 else "not inverted.")
        )
        notes.append(
            f"Canada yield curve (10y − 2y) is {ca_spread:+.2f} pts on {ca10[0]}: "
            + ("inverted." if ca_spread < 0 else "not inverted.")
        )
        notes.append(
            f"U.S. unemployment is {un_now[1]}% ({un_now[0]}), {un_change:+.2f} pts vs. its 12-month low"
            + (": a sharp rise, often seen near recessions." if un_change >= 0.5 else ": no sharp rise.")
        )
    return {
        "metrics": {
            ("É.-U. 10a−2a" if fr else "US 10y−2y"): f"{us_spread:+.2f}",
            ("Can. 10a−2a" if fr else "CA 10y−2y"): f"{ca_spread:+.2f}",
            ("Chômage É.-U." if fr else "US unemployment"): f"{un_now[1]}%",
            ("Chôm. vs creux 12 m" if fr else "Unemp. vs 12m low"): f"{un_change:+.2f}",
        },
        "notes": notes,
        "sources": [
            "FRED : DGS10, DGS2, UNRATE (macro_rates.csv)" if fr else "FRED: DGS10, DGS2, UNRATE (macro_rates.csv)",
            "Banque du Canada : BD.CDN.10YR.DQ.YLD, BD.CDN.2YR.DQ.YLD (macro_rates.csv)"
            if fr
            else "Bank of Canada: BD.CDN.10YR.DQ.YLD, BD.CDN.2YR.DQ.YLD (macro_rates.csv)",
        ],
        "warnings": [
            "Les indicateurs sont des données de référence historiques seulement ; ils sont exclus des tests rétrospectifs du portefeuille et ne prédisent pas une récession."
            if fr
            else "Indicators are historical reference data only; they are excluded from portfolio backtests and do not predict a recession."
        ],
    }
