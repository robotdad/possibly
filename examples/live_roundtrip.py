"""Continue a synthetic live trial through prototype, refinement and handoff.

This script records a test selection, not a human design approval.
Usage: python examples/live_roundtrip.py STORE EXPLORATION_ID OUTPUT_DIRECTORY
"""

import json
import sys
from pathlib import Path

from possibly import Grant, Possibly
from possibly.intelligence import AmplifierIntelligence

store, eid, output = sys.argv[1:]
p = Possibly(
    store,
    intelligence=AmplifierIntelligence(provider="anthropic", allow_environment=True),
    caller="synthetic-validation",
)
root = Path(output)
root.mkdir(parents=True, exist_ok=True)
snapshot = p.get_exploration(eid)
rid = next(r for r, v in snapshot["revisions"].items() if v["kind"] == "storyboard")
p.record_decision(
    eid,
    rid,
    action="select",
    text="Automated synthetic test selection; not human approval.",
    request_id="test-select",
)
for name, revision in snapshot["revisions"].items():
    (root / (name + ".html")).write_text(p.read_artifact(eid, name))
made = p.make_interactive(
    eid, rid, grant=Grant(actions=("make_interactive",), timeout_seconds=300), request_id="test-prototype"
)
(root / "prototype-operation.json").write_text(json.dumps(made, indent=2))
op = made.get("operation") or p.get_operation(eid, made["receipt"]["operation_id"])
print(json.dumps({"phase": "prototype", "state": op["state"], "failure": op.get("failure")}), flush=True)
if op["state"] != "succeeded":
    raise SystemExit(1)
r2 = op["result"]["revision_ids"][0]
(root / "before-refinement.html").write_text(p.read_artifact(eid, r2))
refined = p.refine(
    eid,
    r2,
    "Keep the shift-claiming interaction and layout. Make the action labels shorter and clearer, "
    "and ensure the confirmation explicitly identifies the day and volunteer. Preserve the chosen visual style.",
    grant=Grant(actions=("refine",), timeout_seconds=300),
    request_id="test-refine",
)
(root / "refinement-operation.json").write_text(json.dumps(refined, indent=2))
op = refined.get("operation") or p.get_operation(eid, refined["receipt"]["operation_id"])
print(json.dumps({"phase": "refine", "state": op["state"], "failure": op.get("failure")}), flush=True)
if op["state"] != "succeeded":
    raise SystemExit(1)
r3 = op["result"]["revision_ids"][0]
exported = p.export(eid, r3, request_id="test-export")["receipt"]
(root / "prototype.html").write_text(exported["html"])
(root / "handoff.json").write_text(json.dumps(exported["handoff"], indent=2))
finished = p.finish(
    eid, r3, request_id="test-finish", expected_state_version=p.get_exploration(eid)["state_version"]
)
print(json.dumps({"phase": "finish", "cleanup": finished["cleanup"], "output": str(root)}), flush=True)
