"""Portable adapter contracts; no provider credentials, generation, or network needed."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
import anyio
from mcp import Client
from mcp.client import advertise
from mcp.client.stdio import StdioServerParameters
from mcp.server.apps import APP_MIME_TYPE, EXTENSION_ID
from test_contracts import FakeIntelligence, started

from possibly import Possibly
from possibly.mcp import UI_URI, create_server, public_result
from possibly.store import event

APPS = advertise(EXTENSION_ID, {"mimeTypes": [APP_MIME_TYPE]})


def payload(result):
    assert not result.is_error, result.content
    return result.structured_content


def test_sdk_discovery_resource_and_bounded_grant(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence())
        async with Client(create_server(library), extensions=[APPS]) as client:
            tools = (await client.list_tools()).tools
            start = next(tool for tool in tools if tool.name == "possibly_start")
            finish = next(tool for tool in tools if tool.name == "possibly_finish")
            stop = next(tool for tool in tools if tool.name == "possibly_stop")
            assert start.meta["ui"] == {"resourceUri": UI_URI, "visibility": ["model", "app"]}
            assert not start.annotations.destructive_hint
            assert finish.annotations.destructive_hint
            assert stop.annotations.destructive_hint
            export_chunk = next(tool for tool in tools if tool.name == "possibly_read_export_chunk")
            assert export_chunk.annotations.read_only_hint
            assert export_chunk.input_schema["properties"]["max_bytes"]["maximum"] == 65_536
            grant = start.input_schema["$defs"]["ExecutionGrant"]
            assert grant["properties"]["max_model_calls"]["maximum"] == 100
            assert grant["additionalProperties"] is False
            resources = await client.read_resource(UI_URI)
            html = resources.contents[0]
            assert html.mime_type == APP_MIME_TYPE
            assert "setAttribute('sandbox','allow-scripts')" in html.text
            assert "<script src=" not in html.text
            assert html.meta["ui"]["csp"]["connectDomains"] == []
            rejected = await client.call_tool(
                "possibly_start",
                {
                    "context": "Garden",
                    "request_id": "invalid",
                    "grant": {"actions": ["explore"], "max_turns": 0},
                },
            )
            assert rejected.is_error
            assert not library.intelligence.calls
            result = payload(
                await client.call_tool(
                    "possibly_start",
                    {"context": "Garden", "request_id": "start", "grant": {"actions": ["explore"]}},
                )
            )
            eid = result["exploration_id"]
            assert library.get_exploration(eid)["presentation"] == {
                "mode": "host",
                "service": False,
                "open_viewer": False,
            }
            repeat = payload(
                await client.call_tool(
                    "possibly_start",
                    {"context": "Garden", "request_id": "start", "grant": {"actions": ["explore"]}},
                )
            )
            assert repeat["result"]["status"] == "replayed"
            assert repeat["result"]["receipt"] == result["result"]["receipt"]
            assert len(library.intelligence.calls) == 1

    anyio.run(run)


def test_ui_and_model_share_decisions_drafts_conflicts_and_exports(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        eid, rid = started(library)
        async with Client(create_server(library), extensions=[APPS]) as client:
            state = payload(await client.call_tool("possibly_get_exploration", {"exploration_id": eid}))[
                "result"
            ]
            selected = {
                "exploration_id": eid,
                "revision_id": rid,
                "action": "select",
                "request_id": "select",
                "expected_state_version": state["state_version"],
            }
            receipt = payload(await client.call_tool("possibly_record_decision", selected))
            assert library.review_snapshot(eid)["selected_revision"] == rid
            assert (
                payload(await client.call_tool("possibly_record_decision", selected))["result"]["receipt"]
                == receipt["result"]["receipt"]
            )
            conflict = await client.call_tool(
                "possibly_record_decision", {**selected, "action": "reject", "request_id": "stale"}
            )
            assert conflict.is_error
            assert conflict.structured_content["error"]["code"] == "state_conflict"
            await client.call_tool(
                "possibly_save_review_state",
                {
                    "exploration_id": eid,
                    "revision_id": rid,
                    "draft": "Make buttons clearer",
                    "reviewer_id": "view",
                    "sequence": 2,
                    "request_id": "draft",
                },
            )
            await client.call_tool(
                "possibly_save_review_state",
                {
                    "exploration_id": eid,
                    "revision_id": rid,
                    "draft": "Old draft",
                    "reviewer_id": "view",
                    "sequence": 1,
                    "request_id": "old",
                },
            )
            reviews = payload(await client.call_tool("possibly_review_snapshot", {"exploration_id": eid}))[
                "result"
            ]
            assert reviews["reviews"]["view"]["drafts"][rid] == "Make buttons clearer"
            assert len(library.intelligence.calls) == 1
            generated = payload(
                await client.call_tool(
                    "possibly_make_interactive",
                    {
                        "exploration_id": eid,
                        "revision_id": rid,
                        "grant": {"actions": ["make_interactive"]},
                        "request_id": "prototype",
                    },
                )
            )
            interactive = generated["result"]["operation"]["result"]["revision_ids"][0]
            exported = payload(
                await client.call_tool(
                    "possibly_export",
                    {"exploration_id": eid, "revision_id": interactive, "request_id": "export"},
                )
            )
            assert "html" not in exported["result"]["receipt"]
            assert "handoff" not in exported["result"]["receipt"]
            handoff = payload(
                await client.call_tool(
                    "possibly_read_export_chunk",
                    {
                        "exploration_id": eid,
                        "request_id": "export",
                        "export_kind": "handoff",
                        "offset": 0,
                        "max_bytes": 65_536,
                    },
                )
            )["result"]
            assert handoff["complete"]
            assert json.loads(handoff["data"])["revision_id"] == interactive
            stopped = payload(
                await client.call_tool("possibly_stop", {"exploration_id": eid, "request_id": "stop"})
            )
            assert stopped["result"]["cleanup"]["status"] == "succeeded"
            assert library.read_artifact(eid, interactive)
            assert len(library.intelligence.calls) == 2

    anyio.run(run)


def test_stdio_reconnect_retains_work_and_no_implicit_model_access(tmp_path):
    library = Possibly(tmp_path, intelligence=FakeIntelligence())
    eid, rid = started(library)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "possibly.mcp", "--storage", str(tmp_path)],
        env={"PYTHONPATH": str(Path(__file__).parents[1] / "src")},
    )

    async def run():
        async with Client(params, extensions=[APPS]) as client:
            refused = await client.call_tool(
                "possibly_start",
                {
                    "context": "No implicit credential access",
                    "request_id": "denied",
                    "grant": {"actions": ["explore"]},
                },
            )
            assert refused.is_error
            assert refused.structured_content["error"]["code"] == "model_access_required"
            assert payload(
                await client.call_tool(
                    "possibly_record_decision",
                    {
                        "exploration_id": eid,
                        "revision_id": rid,
                        "action": "select",
                        "request_id": "stdio-select",
                    },
                )
            )
        async with Client(params) as client:
            snapshot = payload(await client.call_tool("possibly_review_snapshot", {"exploration_id": eid}))[
                "result"
            ]
            assert snapshot["selected_revision"] == rid
            assert snapshot["lifecycle"] == "active"

    anyio.run(run)


def test_runner_secrets_not_distributed_and_base_import_stays_optional():
    value = public_result(
        {
            "runner": {"url": "http://localhost/#private"},
            "execution": {"status": "available", "url": "private", "log": "private"},
            "token": "secret",
            "result": {"id": "retained"},
        }
    )
    assert "private" not in json.dumps(value)
    assert "secret" not in json.dumps(value)
    assert value["result"]["id"] == "retained"
    assert (
        public_result({"brief": {"url": "https://example.com/design"}})["brief"]["url"]
        == "https://example.com/design"
    )
    run = subprocess.run(
        [sys.executable, "-c", "import sys; import possibly; assert 'mcp' not in sys.modules"],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert run.returncode == 0, run.stderr


def test_mcp_read_changes_redacts_private_presentation_event_url_in_both_outputs(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence())
        eid, _ = started(library)
        with library.store.transaction() as db:
            state = library.store.get(eid, db)
            event(state, "presentation_available", url="http://127.0.0.1:9999/")
            event(state, "caller_link_available", url="https://example.com/brief")
            library.store.put(db, state)
        async with Client(create_server(library)) as client:
            result = await client.call_tool("possibly_read_changes", {"exploration_id": eid})
        text = result.content[0].text
        structured = result.structured_content
        assert "127.0.0.1:9999" not in text
        assert "127.0.0.1:9999" not in json.dumps(structured)
        events = {entry["kind"]: entry for entry in structured["result"]["events"]}
        assert "url" not in events["presentation_available"]
        assert events["caller_link_available"]["url"] == "https://example.com/brief"

    anyio.run(run)


def test_cleanup_failure_is_visible_with_retained_receipt(tmp_path, monkeypatch):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence())
        eid, _ = started(library)
        monkeypatch.setattr(
            library,
            "wait_cleanup",
            lambda exploration_id, timeout=10: {
                "status": "failed",
                "failed_resources": [{"resource_id": "fixture", "cause": "Unconfirmed"}],
            },
        )
        async with Client(create_server(library)) as client:
            result = await client.call_tool("possibly_stop", {"exploration_id": eid, "request_id": "stop"})
            assert result.is_error
            assert result.structured_content["error"]["code"] == "cleanup_incomplete"
            assert result.structured_content["result"]["receipt"]["exploration_id"] == eid
            assert library.get_exploration(eid)["lifecycle"] == "stopped"

    anyio.run(run)


def test_mcp_artifact_limit_is_checked_before_serialization_and_provider_actions_need_consent(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence())
        eid, rid = started(library)
        with library.store.transaction() as db:
            state = library.store.get(eid, db)
            state["revisions"][rid]["html"] = "å" * 600_000  # 1.2 MB UTF-8, not a character-count bypass.
            library.store.put(db, state)
        async with Client(create_server(library)) as client:
            oversized = await client.call_tool(
                "possibly_read_artifact",
                {"exploration_id": eid, "revision_id": rid, "max_bytes": 1_000_000},
            )
            assert oversized.is_error
            assert oversized.structured_content["error"]["code"] == "artifact_too_large"
            denied = await client.call_tool(
                "possibly_test_provider",
                {"provider": "openai"},
            )
            assert denied.is_error

    anyio.run(run)


def test_review_attachment_persists_exact_pending_intent_and_typed_config_rejection(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        eid, rid = started(library)
        async with Client(create_server(library)) as client:
            opened = payload(
                await client.call_tool(
                    "possibly_open_review", {"exploration_id": eid, "request_id": "open-review"}
                )
            )
            reviewer = opened["result"]["receipt"]["reviewer_id"]
            state = payload(await client.call_tool("possibly_get_exploration", {"exploration_id": eid}))[
                "result"
            ]
            request = {
                "exploration_id": eid,
                "revision_id": rid,
                "action": "feedback",
                "text": "Retain the exact request through transport loss",
                "expected_state_version": state["state_version"],
                "reviewer_id": reviewer,
                "view_id": "compare",
                "request_id": "lost-decision",
            }
            accepted = payload(await client.call_tool("possibly_record_decision", request))
            pending = library.review_snapshot(eid)["reviews"][reviewer]["pending_mutations"]["lost-decision"]
            assert pending["payload"] == request
            replayed = payload(await client.call_tool("possibly_record_decision", request))
            assert replayed["result"]["status"] == "replayed"
            assert replayed["result"]["receipt"] == accepted["result"]["receipt"]
            conflict = await client.call_tool(
                "possibly_record_decision", {**request, "text": "Different text with reused request ID"}
            )
            assert conflict.is_error
            assert conflict.structured_content["error"]["code"] == "request_conflict"
            acknowledged = payload(
                await client.call_tool(
                    "possibly_acknowledge_review_intent",
                    {
                        "exploration_id": eid,
                        "reviewer_id": reviewer,
                        "mutation_request_id": "lost-decision",
                        "request_id": "ack-lost-decision",
                    },
                )
            )
            assert acknowledged["result"]["receipt"]["acknowledged"]
            assert not library.review_snapshot(eid)["reviews"][reviewer]["pending_mutations"]
            invalid = await client.call_tool(
                "possibly_configure_provider",
                {
                    "provider": "openai",
                    "provider_config": {"nested": {"api_key": "not-allowed"}},
                    "authorize_provider_action": True,
                },
            )
            assert invalid.is_error
            assert invalid.structured_content["error"]["code"] == "invalid_settings"

    anyio.run(run)
