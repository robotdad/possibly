"""Opt-in live task-diversity trial; retained results, no automatic credential login."""

import json
import sys
from pathlib import Path

from possibly import Grant, Possibly, Presentation
from possibly.intelligence import AmplifierIntelligence

BRIEFS = {
    "repairs": "Design a household repairs planning app. Capture an issue and its room or home system, symptoms, urgency, estimated effort and cost, DIY versus professional help, dependencies and progress/history. Help a household decide what to do next within a realistic time and budget. Explore genuinely different task representations, not cosmetic layouts of the same list. Use realistic simulated data; demonstrate two connected screens and a meaningful state change. Do not offer professional safety advice. Use system light/dark styling and fully embedded assets.",
    "pinball": "Design Flip Log, one integrated app to track pinball machines played and personal high scores. Include a machine collection/detail, chronological plays, quick score logging, and venue per play. Mock Pinside search/add with machine metadata and an embedded illustrative machine image (label it illustrative). Photo capture of score/cabinet is simulated and requires explicit score confirmation. Explore a distinctive task representation: session diary, mastery/progression, or venue/discovery, while keeping the same central machine and score recording scope. Demonstrate two connected screens and score recording with realistic data. System light/dark; all assets embedded; no network or actual photo recognition.",
}
name = sys.argv[1]
round_name = sys.argv[2] if len(sys.argv) > 2 else "round1"
root = Path(__file__).parent / "generated" / "diversity" / round_name / name
p = Possibly(root, intelligence=AmplifierIntelligence(allow_environment=True), execution="owned_runner")
plan = "auto"
if len(sys.argv) > 3:
    plan = json.loads(Path(sys.argv[3]).read_text())
result = p.start(
    BRIEFS[name],
    request_id="start",
    exploration_plan=plan,
    grant=Grant(timeout_seconds=240, max_model_calls=18, max_tool_calls=30),
    presentation=Presentation(mode="builtin", service=True, open_viewer=False),
)
(root / "start.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result))
