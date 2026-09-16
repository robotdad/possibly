"""Manual live compatibility probe; no caller context is read."""

import tempfile

from possibly import Grant
from possibly.intelligence import AmplifierIntelligence

with tempfile.TemporaryDirectory() as root:
    print(
        AmplifierIntelligence(provider="anthropic", allow_environment=True).generate(
            {
                "operation_id": "probe",
                "kind": "explore",
                "turn": 1,
                "context": "Ask one identified question about an unspecified app idea. Do not create artifacts.",
            },
            root,
            Grant(timeout_seconds=60).to_dict(),
        )
    )
