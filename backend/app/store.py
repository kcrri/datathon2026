"""In-memory store for the demo. Replace with a database later."""
import uuid
from typing import Any, Dict, List

ACCOUNTS: Dict[str, List[Dict[str, Any]]] = {}
PENDING: Dict[str, Dict[str, Any]] = {}


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def accounts(user_id: str) -> List[Dict[str, Any]]:
    existing = ACCOUNTS.setdefault(user_id, [])
    if user_id == "demo" and not existing:
        from app.domain.presets import ACCOUNT_PRESETS, PERSONAS

        for persona_id, persona in PERSONAS.items():
            for account_type, preset in ACCOUNT_PRESETS.items():
                balance = round(float(persona["starting_balance_cad"]) * float(preset["share"]), 2)
                existing.append(
                    {
                        "id": f"{persona_id}-{account_type.lower().replace(' ', '-')}",
                        "name": account_type,
                        "type": account_type,
                        "persona_id": persona_id,
                        "horizon": persona["horizon_years"],
                        "risk": persona["risk"],
                        "risk_label": persona["risk"],
                        "persona": persona["name"],
                        "horizon_agent": f"{persona['horizon_years']} horizon",
                        "strategies": list(preset["allocations"]),
                        "balance": balance,
                        "cash": round(balance * float(preset["cash_share"]), 2),
                        "allocations": preset["allocations"],
                    }
                )
    return existing


def delete_account(user_id: str, account_id: str) -> bool:
    user_accounts = accounts(user_id)
    remaining = [a for a in user_accounts if a["id"] != account_id]
    removed = len(remaining) != len(user_accounts)
    user_accounts[:] = remaining
    return removed
