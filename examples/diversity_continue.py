"""Opt-in live continuation of round3; select, make interactive, refine, export."""

import json
import sys
from pathlib import Path

from possibly import Grant, Possibly
from possibly.intelligence import AmplifierIntelligence

name, stage = sys.argv[1:3]
root = Path(__file__).parent / "generated" / "diversity" / "round3" / name
p = Possibly(root, intelligence=AmplifierIntelligence(allow_environment=True), execution="owned_runner")
eid = json.loads((root / "start.json").read_text())["receipt"]["exploration_id"]
s = p.get_exploration(eid)
if stage == "interactive":
    provider = "gemini" if name == "repairs" else "openai"
    rid = next(
        r["id"]
        for r in s["revisions"].values()
        if r["provenance"]["provider"] == provider and not r["parent"]
    )
    p.record_decision(
        eid, rid, action="select", request_id="select-trial", expected_state_version=s["state_version"]
    )
    result = p.make_interactive(
        eid,
        rid,
        request_id="interactive-trial",
        grant=Grant(actions=("make_interactive",), timeout_seconds=150, max_model_calls=6, max_tool_calls=12),
    )
elif stage == "refine":
    op = p.get_operation(eid, json.loads((root / "interactive.json").read_text())["receipt"]["operation_id"])
    rid = op["result"]["revision_ids"][0]
    instructions = {
        "repairs": "Refine this into a clearer household decision aid. Preserve current asserted flows. Any shared-cause link must say hypothesis to discuss, not proven diagnosis. Add a compact handoff readiness checklist in the existing detail screen: evidence recorded, access arranged, owner assigned; a ready-to-share state is enabled only when all three are checked. Keep it explicitly a local simulated handoff, send nothing. Show ready count and verify the state change. Use small exact patches and existing layout; no full rewrite. Preserve task_model metadata.",
        "pinball": "Refine with a Stern-inspired arcade treatment: bold condensed system typography, charcoal panels, red and warm white accents, strong cabinet identity, while preserving system light/dark with readable contrast. Keep the task organization and all current asserted flows, mock Pinside search/add, venue and confirmed scores. Fix target progress labels to derive mathematically from the current best and target rather than hard-coded percentages; verify the gap updates when a higher confirmed score is saved. Avoid copying logos or remote assets. Remove any irrelevant diagnosis disclaimer from this pinball UI. Use concise CSS and JS patches, no full rewrite. Preserve task_model metadata.",
    }
    p.record_decision(eid, rid, action="feedback", text=instructions[name], request_id="critique-trial")
    result = p.refine(
        eid,
        rid,
        instructions[name],
        request_id="refine-trial",
        grant=Grant(actions=("refine",), timeout_seconds=180, max_model_calls=8, max_tool_calls=14),
    )
else:
    raise SystemExit("Use interactive or refine")
(root / (stage + ".json")).write_text(json.dumps(result, indent=2))
print(json.dumps(result))
