"""Account Creation Agent: creates a simulated account after user approval."""
from typing import Any, Dict

from app import store
from app.profiles import PROFILES


def create(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    p = PROFILES[payload["risk"]]
    n = sum(1 for a in store.accounts(user_id) if a["type"] == payload["account_type"]) + 1
    account = {
        "id": store.new_id(),
        "name": f"{payload['account_type']} #{n}",
        "type": payload["account_type"],
        "horizon": payload["horizon"],
        "risk": payload["risk"],
        "risk_label": p["label"],
        "persona": p["persona"],
        "horizon_agent": p["horizon_agent"],
        "strategies": p["strategies"],
        "balance": 0.0,  # new accounts start empty until funded
    }
    store.accounts(user_id).append(account)
    return account
