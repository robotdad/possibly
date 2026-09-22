"""Optional MCP / MCP Apps adapter over the public library, with no host-specific API.

The stdio transport is scoped to a trusted host process and one explicit store. The
host owns access control. Closing the transport does not cancel an owned runner.
"""

import argparse
import inspect
import json
import sys
from pathlib import Path
from typing import Annotated, Literal

from .lib import Possibly
from .models import PossiblyError, Presentation

UI_URI = "ui://possibly/review"


def public_result(value, path=()):
    """Do not distribute private runner access URLs or provider secrets to a presenter."""
    if isinstance(value, dict):
        return {
            key: public_result(item, (*path, key))
            for key, item in value.items()
            if key.lower()
            not in {"runner", "token", "api_key", "access_token", "refresh_token", "password", "secret"}
            and not (path == ("execution",) and key in {"url", "log"})
            and not (value.get("kind") == "presentation_available" and key == "url")
        }
    if isinstance(value, (list, tuple)):
        return [public_result(item, path) for item in value]
    return value


def create_server(client):
    """Build a server for an explicitly bound public-library client; imports are optional."""
    import anyio
    from mcp.server import MCPServer
    from mcp.server.apps import Apps, ResourceCsp
    from mcp.types import CallToolResult, TextContent, ToolAnnotations
    from pydantic import BaseModel, ConfigDict, Field

    class ExecutionGrant(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        actions: list[Literal["explore", "make_interactive", "refine"]] = Field(min_length=1)
        max_turns: int = Field(default=4, ge=1, le=20)
        timeout_seconds: int = Field(default=300, ge=1, le=3600)
        max_tool_calls: int = Field(
            default=20,
            ge=1,
            le=100,
            description="Admitted tool executions per submission, including submit_result; three concepts need at least seven calls.",
        )
        max_model_calls: int = Field(default=12, ge=1, le=100)
        prototype_after_selection: bool = False
        expires_at: float | None = None

    identifier = Annotated[str, Field(min_length=1, max_length=200, strict=True)]
    text = Annotated[str, Field(max_length=20000, strict=True)]
    version = Annotated[int, Field(ge=0, strict=True)]
    byte_limit = Annotated[int, Field(ge=1, le=1_000_000, strict=True)]
    snapshot_limit = Annotated[int, Field(ge=1, le=1_000_000, strict=True)]
    provider = Annotated[str, Field(min_length=1, max_length=80, strict=True)]
    setting = Annotated[str, Field(max_length=200, strict=True)]
    provider_config = Annotated[dict[str, object], Field(max_length=32)]
    types = {
        "context": text,
        "exploration_id": identifier,
        "operation_id": identifier,
        "revision_id": identifier,
        "view_revision_id": identifier,
        "question_id": identifier,
        "request_id": identifier,
        "reviewer_id": identifier,
        "view_id": identifier,
        "grant": ExecutionGrant,
        "action": Literal["select", "reject", "feedback", "brief_correction"],
        "text": text,
        "draft": text,
        "instruction": text,
        "reason": text,
        "sequence": version,
        "confirm_relevance": Annotated[bool, Field(strict=True)],
        "cursor": version,
        "limit": Annotated[int, Field(ge=1, le=1000, strict=True)],
        "timeout": Annotated[float, Field(ge=0, le=60)],
        "timeout_seconds": Annotated[int, Field(ge=1, le=300, strict=True)],
        "expected_state_version": version,
        "max_bytes": byte_limit,
        "max_embedded_bytes": snapshot_limit,
        "provider": provider,
        "model": setting,
        "reasoning_effort": setting,
        "provider_config": provider_config,
        "authorize_provider_action": Annotated[bool, Field(strict=True)],
        "appearance": Literal["system", "light", "dark"],
        "mutation_request_id": identifier,
        "kind": Literal["test", "models", "login"],
        "export_kind": Literal["html", "handoff"],
        "offset": Annotated[int, Field(ge=0, strict=True)],
    }
    # Explicit allowlist: exposing a new library method requires an adapter review.
    operations = (
        "start",
        "get_exploration",
        "get_operation",
        "wait_operation",
        "read_changes",
        "save_review_state",
        "open_review",
        "acknowledge_review_intent",
        "review_snapshot",
        "get_revision",
        "read_artifact",
        "record_decision",
        "make_interactive",
        "refine",
        "answer",
        "finalize_operation",
        "operation_diagnostics",
        "export",
        "read_export_chunk",
        "finish",
        "stop",
        "wait_cleanup",
        "reopen",
        "resume_operation",
        "reactivate_operation",
        "provider_settings",
        "configure_provider",
        "provider_models",
        "test_provider",
        "provider_login",
        "start_provider_job",
        "provider_job",
    )
    readonly = {
        "get_exploration",
        "get_operation",
        "wait_operation",
        "read_changes",
        "review_snapshot",
        "get_revision",
        "read_artifact",
        "operation_diagnostics",
        "read_export_chunk",
        "provider_settings",
        "provider_job",
    }
    apps = Apps()

    def register(name):
        method = getattr(client, name)
        signature = inspect.signature(method)
        parameters = []
        for param in signature.parameters.values():
            # This transport never opens a loopback web service or browser, and only
            # accepts caller-supplied text. References require a separate scoped resolver.
            if name == "start" and param.name in {"presentation", "materials", "exploration_plan"}:
                continue
            if name == "provider_login" and param.name == "on_progress":
                continue
            annotation = types[param.name]
            if name == "read_export_chunk" and param.name == "max_bytes":
                annotation = Annotated[int, Field(ge=1, le=65_536, strict=True)]
            if param.default is None or (name == "record_decision" and param.name == "revision_id"):
                annotation = annotation | None
            parameters.append(param.replace(annotation=annotation))
        if name in {
            "configure_provider",
            "provider_models",
            "test_provider",
            "provider_login",
            "start_provider_job",
        }:
            parameters.append(
                inspect.Parameter(
                    "authorize_provider_action",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=types["authorize_provider_action"],
                    default=False,
                )
            )

        async def invoke(**arguments):
            try:
                if isinstance(arguments.get("grant"), ExecutionGrant):
                    arguments["grant"] = arguments["grant"].model_dump()
                if name == "start":
                    arguments["presentation"] = Presentation(mode="host", service=False, open_viewer=False)
                if name in {
                    "configure_provider",
                    "provider_models",
                    "test_provider",
                    "provider_login",
                    "start_provider_job",
                }:
                    if arguments.pop("authorize_provider_action", False) is not True:
                        raise PossiblyError(
                            "provider_action_authorization_required",
                            "Provider configuration, discovery, test, and login require an explicit action authorization.",
                        )
                    config = arguments.get("provider_config")
                    if config is not None:
                        from .providers import checked_config

                        arguments["provider_config"] = checked_config(config)
                result = await anyio.to_thread.run_sync(lambda: method(**arguments))
                if name == "export" and isinstance(result, dict) and isinstance(result.get("receipt"), dict):
                    # Export bytes are retrievable through bounded public chunks.
                    # Do not serialize a potentially multi-megabyte HTML/handoff
                    # receipt into one MCP response.
                    result = {
                        **result,
                        "receipt": {
                            key: value
                            for key, value in result["receipt"].items()
                            if key not in {"html", "handoff"}
                        },
                    }
                result = public_result(result)
                eid = arguments.get("exploration_id")
                if isinstance(result, dict):
                    eid = eid or result.get("receipt", {}).get("exploration_id") or result.get("id")
                payload = {"operation": name, "exploration_id": eid, "result": result}
                cleanup_failed = name in {"stop", "finish", "wait_cleanup"} and (
                    result.get("cleanup", result).get("status") == "failed"
                )
                if cleanup_failed:
                    payload["error"] = {
                        "code": "cleanup_incomplete",
                        "message": "Cleanup is not confirmed. Retained work is safe; use possibly_wait_cleanup.",
                    }
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
                    structuredContent=payload,
                    isError=cleanup_failed,
                )
            except PossiblyError as error:
                payload = public_result(error.to_dict())
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(payload))],
                    structuredContent=payload,
                    isError=True,
                )

        invoke.__name__ = "possibly_" + name
        invoke.__signature__ = signature.replace(parameters=parameters, return_annotation=CallToolResult)
        description = inspect.getdoc(method) or name.replace("_", " ")
        if name == "start":
            description += " Host presentation only; requires explicit model access and a bounded grant."
        if name in {"make_interactive", "refine", "resume_operation"}:
            description += " May spend model tokens; requires an explicit bounded grant."
        apps.tool(
            resource_uri=UI_URI,
            visibility=["model", "app"]
            if name
            not in {
                "configure_provider",
                "provider_models",
                "test_provider",
                "provider_login",
                "start_provider_job",
            }
            else ["app"],
            description=description,
            annotations=ToolAnnotations(
                readOnlyHint=name in readonly, destructiveHint=name in {"finish", "stop"}
            ),
        )(invoke)

    for name in operations:
        register(name)

    apps.add_html_resource(
        UI_URI,
        Path(__file__).with_name("mcp_app.html").read_text(),
        title="Possibly · Review experiences",
        description="Compare exact revisions, record decisions, and refine with an explicit grant.",
        csp=ResourceCsp(connectDomains=[], resourceDomains=[], frameDomains=["blob:"]),
        prefers_border=True,
    )
    server = MCPServer(
        "Possibly",
        version="0.1.0",
        extensions=[apps],
        instructions=(
            "Possibly explores app experiences. Retain exploration/operation/revision IDs. "
            "Start/refine require explicit grants and model access; deterministic reads/decisions do not. "
            "Read review_snapshot before continuing: saved drafts are context, not permission to generate. "
            "Ask the person to choose a revision unless they already delegated that choice. "
            "Tool UI and model calls use the same public library and durable receipts. "
            "Never resubmit start to check progress; poll get_operation/read_changes. "
            "Use expected_state_version when making decisions. Closing the app is not stopping work. "
            "The current adapter uses native durable operations, not negotiated MCP Tasks or sampling."
        ),
    )

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def possibly_status() -> dict:
        """Provider-free setup status; does not load a model, test credentials, or start work."""
        return {
            "model_access": client.intelligence is not None,
            "execution": client.execution,
            "presentation": "host",
            "ui_resource": UI_URI,
            "setup": "Restart with --model-env to explicitly allow provider credentials for generation.",
            "limits": ["No MCP sampling or Tasks", "Closing the view does not cancel owned work"],
        }

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Serve Possibly over stdio MCP with an optional MCP Apps UI."
    )
    parser.add_argument("--storage", required=True, help="Explicit directory retaining exploration state.")
    parser.add_argument("--model-env", action="store_true", help="Explicitly allow model environment access.")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    args = parser.parse_args(argv)
    try:
        import mcp  # noqa: F401
    except ImportError:
        parser.exit(2, "MCP support is optional. Install Possibly with the [mcp] extra.\n")
    intelligence = None
    if args.model_env:
        from .intelligence import AmplifierIntelligence

        intelligence = AmplifierIntelligence(
            provider=args.provider, model=args.model, effort=args.reasoning_effort, allow_environment=True
        )
    client = Possibly(
        Path(args.storage).expanduser(), intelligence=intelligence, caller="mcp", execution="owned_runner"
    )
    create_server(client).run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
