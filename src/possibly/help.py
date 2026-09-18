"""Library-owned manifest and generated help; CLI adapters print these exact values."""

import inspect
from pathlib import Path

import yaml

OPERATIONS = {
    "plan_exploration": "deterministic",
    "provider_models": "deterministic",
    "provider_settings": "deterministic",
    "configure_provider": "deterministic",
    "test_provider": "model-backed",
    "provider_login": "deterministic",
    "start": "model-backed",
    "get_exploration": "deterministic",
    "get_operation": "deterministic",
    "wait_operation": "deterministic",
    "read_changes": "deterministic",
    "save_review_state": "deterministic",
    "review_snapshot": "deterministic",
    "get_revision": "deterministic",
    "read_artifact": "deterministic",
    "record_decision": "deterministic",
    "answer": "conditionally model-backed",
    "make_interactive": "model-backed",
    "refine": "model-backed",
    "finalize_operation": "deterministic",
    "operation_diagnostics": "deterministic",
    "run_operation": "model-backed",
    "export": "deterministic",
    "finish": "deterministic",
    "stop": "deterministic",
    "wait_cleanup": "deterministic",
    "reopen": "deterministic",
    "resume_operation": "model-backed",
    "reactivate_operation": "deterministic",
    "manifest": "deterministic",
    "capabilities": "deterministic",
    "skill": "deterministic",
}


def manifest():
    text = Path(__file__).with_name("SMART_TOOL.md").read_text()
    _, frontmatter, body = text.split("---", 2)
    return {**yaml.safe_load(frontmatter), "body": body.strip()}


def capabilities():
    from .lib import Possibly

    return {
        "version": "0.1.0",
        "result_format": "JSON",
        "capabilities": [
            {
                "name": name,
                "command": name.replace("_", "-"),
                "intelligence": kind,
                "signature": str(inspect.signature(getattr(Possibly, name))),
                "description": inspect.getdoc(getattr(Possibly, name)) or name.replace("_", " "),
                "input": "JSON object of method arguments; omit self.",
                "errors": "PossiblyError with code, message, remedy; CLI nonzero exit.",
            }
            for name, kind in OPERATIONS.items()
        ],
    }


def capability_help(name):
    item = next(c for c in capabilities()["capabilities"] if c["name"] == name)
    return json_text(item) + "\nCLI: possibly [host options] " + item["command"] + " --input JSON|@FILE|-\n"


def json_text(value):
    import json

    return json.dumps(value, indent=2)


def summary():
    return (
        "Possibly — choose before you build.\n\n"
        + "\n".join(f"  {name.replace('_', '-')}: {kind}" for name, kind in OPERATIONS.items())
        + "\n\nUse --help for the caller skill.\n"
    )


def skill():
    body = manifest()["body"]
    listings = "\n".join(
        f"- `{name.replace('_', '-')}` [{kind}] — `possibly {name.replace('_', '-')} --help`."
        for name, kind in OPERATIONS.items()
    )
    return f"""<skill_content name="possibly">
Skill directory: {Path(__file__).parent.resolve()}
Repository: https://github.com/robotdad/possibly
Relative paths in this skill are relative to the skill directory.

{body}

## Capabilities

{listings}

<skill_resources>
  <file>SMART_TOOL.md</file>
  <file>lib.py</file>
  <file>models.py</file>
  <file>docs/caller-guide.md</file>
  <file>docs/mcp.md</file>
</skill_resources>
</skill_content>
"""
