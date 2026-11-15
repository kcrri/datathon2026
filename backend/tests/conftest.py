"""Tests run the Lambda's and the agents' own code in-process; deployed, the same code runs in AWS.

The language-model parts (the Orchestrator's routing and the Explainer) are off by default so the
tests stay deterministic; their own tests turn them on with a scripted fake model.
"""
import os

os.environ["DATA_BUCKET"] = ""  # tests never touch S3, even if a developer .env sets a bucket
os.environ["ENGINE"] = "local"
os.environ["AGENTS"] = "local"
os.environ["LLM_ROUTING"] = "off"
os.environ["EXPLAINER"] = "rules"


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_investor_store():
    """The saved investor is state; every test starts with nobody chosen."""
    from app.services import investor_store

    investor_store._MEMORY.clear()
    yield
    investor_store._MEMORY.clear()
