"""One process per candidate; private workspace, inherited native credentials, bounded Agent execution."""

import json
import sys
from pathlib import Path

from .intelligence import AmplifierIntelligence
from .models import PossiblyError


def main():
    root = Path(sys.argv[1])
    data = json.loads((root / "input.json").read_text())
    row = data["config"]
    adapter = AmplifierIntelligence(
        provider=row["provider"],
        model=row["model"],
        effort=row["reasoning_effort"],
        provider_config={},
        allow_environment=True,
    )
    try:
        result = adapter.generate(data["request"], root, data["grant"])
        if "question" in result or len(result.get("directions", [])) != 1:
            raise PossiblyError(
                "invalid_candidate",
                "An exploration worker must return one completed concept, not a question.",
            )
        from .lib import Possibly

        Possibly._validate_output(None, result, "refine")
        result["directions"][0]["provenance"]["lens"] = row["lens"]
    except Exception as exc:
        result = {
            "error": exc.to_dict()["error"]
            if isinstance(exc, PossiblyError)
            else {"code": "worker_failed", "message": type(exc).__name__}
        }
    if "error" in result and (root / "diagnostics.json").exists():
        diagnostics = json.loads((root / "diagnostics.json").read_text())
        failed = [c for c in diagnostics.get("provider_calls", []) if c.get("error_type")]
        if failed:
            result["error"]["provider_error_type"] = failed[-1]["error_type"]
    temp = root / "result.tmp"
    temp.write_text(json.dumps(result))
    temp.chmod(0o600)
    temp.replace(root / "result.json")


if __name__ == "__main__":
    main()
