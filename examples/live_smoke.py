"""Explicit live model trial, run manually; uses only the synthetic garden brief."""

import json
import sys
from pathlib import Path

from possibly import Grant, Possibly
from possibly.intelligence import AmplifierIntelligence

root = Path(sys.argv[1]).resolve()
p = Possibly(root, intelligence=AmplifierIntelligence(provider="anthropic", allow_environment=True))
result = p.start(
    "A community garden has twelve volunteers. They need to coordinate weekly watering shifts. "
    "Show meaningful alternatives for volunteers choosing shifts versus providing availability. "
    "Use three representative days and invented names. Do not ask questions for this trial.",
    request_id="live-explore-1",
    grant=Grant(timeout_seconds=300, max_tool_calls=20),
)
print(json.dumps(result, indent=2))

raise SystemExit(0 if result.get("operation", {}).get("state") == "succeeded" else 1)
