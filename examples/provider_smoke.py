"""Opt-in live provider integration check using an existing tiny mock; one provider per invocation.

Usage: .venv/bin/python examples/provider_smoke.py openai
Exercises actual Agent tools, offline browser assertions, screenshot delivery and submission.
Results are retained under examples/generated/provider-smoke/<provider>.
"""

import json
import sys
import uuid
from pathlib import Path

from possibly import Grant, Possibly
from possibly.intelligence import AmplifierIntelligence


class Seed:
    def preflight(self):
        pass

    def generate(self, *args):
        return {
            "brief": {"intent": "Record a pinball score"},
            "directions": [
                {
                    "name": name,
                    "approach": "Record a score",
                    "tradeoff": "Simple demo",
                    "html": '<html><head><title>Score</title></head><body><h1>Pinball score</h1><button id="score" onclick="this.textContent=42">Record</button></body></html>',
                    "invariants": ["Record score"],
                    "mocked": ["In-memory demonstration"],
                    "assumptions": [],
                }
                for name in ("Score", "Simple score")
            ],
        }


provider = sys.argv[1]
root = Path(__file__).parent / "generated" / "provider-smoke" / provider
client = Possibly(root, intelligence=Seed())
start = client.start("Record a pinball score", grant=Grant(), request_id="seed-" + uuid.uuid4().hex)
eid = start["receipt"]["exploration_id"]
rid = next(iter(client.get_exploration(eid)["revisions"]))
client.intelligence = AmplifierIntelligence(provider=provider, allow_environment=True)
result = client.refine(
    eid,
    rid,
    "Keep the existing HTML unchanged. Use inspect_candidate with click #score then assert_text #score value 42. Review the screenshot, submit the unchanged base immediately. This is a bounded provider integration check, no redesign or questions.",
    grant=Grant(actions=("refine",), timeout_seconds=90, max_model_calls=5, max_tool_calls=8),
    request_id="verify-" + eid,
)
opid = result["receipt"]["operation_id"]
print(json.dumps(client.operation_diagnostics(eid, opid)))
client.stop(eid, request_id="close-" + eid, reason="Provider integration smoke complete")
if result.get("operation", {}).get("state") != "succeeded":
    raise SystemExit(1)
