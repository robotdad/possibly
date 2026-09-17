"""Thin JSON adapter; all operation semantics and help live in the library."""

import argparse
import json
import sys
from pathlib import Path

from .help import OPERATIONS, capabilities, capability_help, manifest, skill, summary
from .models import PossiblyError


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise PossiblyError("invalid_invocation", message, "Run possibly --help.")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--help"] or not args:
        print(skill())
        return 0
    if args == ["-h"]:
        print(summary())
        return 0
    parser = Parser(add_help=False)
    parser.add_argument(
        "--store", help="Explicit retained-state directory (required for exploration operations)."
    )
    parser.add_argument("--model-env", action="store_true", help="Opt into environment model credentials.")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--execution", choices=["in_process", "owned_runner"], default="in_process")
    parser.add_argument("--caller", default="local")
    parser.add_argument("command", choices=[name.replace("_", "-") for name in OPERATIONS])
    parser.add_argument(
        "--input", default="{}", help="JSON, @file, or - for stdin; method keyword arguments."
    )
    parser.add_argument(
        "--output-dir", help="For export, write HTML and handoff here (existing files are refused)."
    )
    parser.add_argument("--help", "-h", action="store_true", dest="help")
    try:
        parsed = parser.parse_args(args)
        method = parsed.command.replace("-", "_")
        if parsed.help:
            print(capability_help(method))
            return 0
        raw = parsed.input
        if raw == "-":
            raw = sys.stdin.read()
        elif raw.startswith("@"):
            raw = Path(raw[1:]).read_text()
        inputs = json.loads(raw)
        if not isinstance(inputs, dict):
            raise PossiblyError("invalid_input", "Input must be a JSON object.")
        if method in {"manifest", "capabilities", "skill"}:
            result = {"manifest": manifest, "capabilities": capabilities, "skill": skill}[method]()
        elif method == "review_catalog":
            from .presentation import review_catalog

            result = review_catalog()
        elif method in {
            "provider_models",
            "provider_settings",
            "configure_provider",
            "test_provider",
            "provider_login",
            "plan_exploration",
        }:
            from .intelligence import AmplifierIntelligence

            adapter = AmplifierIntelligence(
                provider=parsed.provider,
                model=parsed.model,
                effort=parsed.reasoning_effort,
                allow_environment=parsed.model_env,
            )
            if method == "plan_exploration":
                from .fanout import plan_exploration

                result = plan_exploration(**inputs)
            else:
                result = getattr(adapter, method)(**inputs)
            if method == "configure_provider":
                result["notice"] = (
                    "CLI overrides expire when this command exits. Use environment variables for subsequent commands."
                )
        else:
            if not parsed.store:
                raise PossiblyError("store_required", "Choose an explicit durable store with --store PATH.")
            from .lib import Possibly

            intelligence = None
            if parsed.model_env:
                from .intelligence import AmplifierIntelligence

                intelligence = AmplifierIntelligence(
                    provider=parsed.provider,
                    model=parsed.model,
                    effort=parsed.reasoning_effort,
                    allow_environment=True,
                )
            client = Possibly(
                parsed.store, intelligence=intelligence, caller=parsed.caller, execution=parsed.execution
            )
            result = getattr(client, method)(**inputs)
        if parsed.output_dir:
            if method != "export":
                raise PossiblyError("invalid_output", "--output-dir is only supported for export.")
            root = Path(parsed.output_dir).expanduser().resolve()
            root.mkdir(parents=True, exist_ok=True)
            receipt = result["receipt"]
            html_path, handoff_path = root / "prototype.html", root / "handoff.json"
            if html_path.exists() or handoff_path.exists():
                raise PossiblyError(
                    "output_exists", "Output files already exist; choose a new output directory."
                )
            html_path.write_text(receipt["html"])
            handoff_path.write_text(json.dumps(receipt["handoff"], indent=2))
            result = {**result, "files": [str(html_path), str(handoff_path)]}
            result["receipt"] = {k: v for k, v in receipt.items() if k not in {"html", "handoff"}}
        print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
        if isinstance(result, dict):
            op = result.get("operation", result if "state" in result else {})
            if (
                op.get("state") in {"failed", "cancelled"}
                or result.get("cleanup", {}).get("status") == "failed"
            ):
                return 1
        return 0
    except PossiblyError as exc:
        print(json.dumps(exc.to_dict()))
        return 1
    except (ValueError, TypeError, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "error": {
                        "code": "invalid_input",
                        "message": str(exc),
                        "remedy": "Read capability help and check supplied files.",
                    },
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
