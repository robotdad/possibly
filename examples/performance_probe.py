"""Offline Amplifier integration probe: scripted provider, real loop/browser, no model request.

Uses the locally prepared Amplifier bundle; first preparation may download runtime modules.
Run: .venv/bin/python examples/performance_probe.py
"""

import asyncio
import copy
import tempfile
from pathlib import Path
from unittest.mock import patch

from amplifier_agent_lib import __version__
from amplifier_agent_lib.bundle.cache import load_and_prepare_cached
from amplifier_core import ProviderInfo
from amplifier_core.message_models import ChatResponse, ToolCall, ToolCallBlock

from possibly.intelligence import AmplifierIntelligence
from possibly.models import Grant


class Provider:
    name = "offline-test"
    default_model = "offline-test"

    def get_info(self):
        return ProviderInfo(id=self.name, display_name="Offline test")

    def get_supported_tools(self):
        return []

    def parse_tool_calls(self, response):
        return response.tool_calls or []

    async def list_models(self):
        return []

    calls = 0

    async def complete(self, request, **kwargs):
        self.calls += 1
        if self.calls == 1:
            call = ToolCall(
                id="inspect",
                name="inspect_candidate",
                arguments={
                    "name": "base",
                    "steps": [
                        {"action": "click", "selector": "#score"},
                        {"action": "assert_text", "selector": "#score", "value": "42"},
                    ],
                },
            )
        else:
            assert self.calls == 2, "No extra prose or visual review execution should occur"
            assert request.messages[-1].content[-1].type == "image"
            call = ToolCall(
                id="submit",
                name="submit_result",
                arguments={
                    "brief": {"intent": "Record a score"},
                    "directions": [
                        {
                            "name": "Score",
                            "approach": "Record",
                            "tradeoff": "Mock",
                            "candidate": "base",
                            "invariants": ["Record score"],
                            "mocked": ["Memory only"],
                            "assumptions": [],
                        }
                    ],
                },
            )
        return ChatResponse(
            content=[ToolCallBlock(id=call.id, name=call.name, input=call.arguments)], tool_calls=[call]
        )


async def main():
    prepared = copy.copy(await load_and_prepare_cached(aaa_version=__version__))
    prepared.mount_plan = copy.deepcopy(prepared.mount_plan)
    prepared.mount_plan.update(providers=[], tools=[], hooks=[], agents={})
    original = prepared.create_session

    async def create(**kwargs):
        prepared.mount_plan["providers"] = []
        session = await original(**kwargs)
        await session.coordinator.mount("providers", Provider(), name="offline-test")
        return session

    prepared.create_session = create

    async def load(**kwargs):
        return prepared

    adapter = AmplifierIntelligence()
    adapter._provider = "offline-test"
    with (
        tempfile.TemporaryDirectory() as root,
        patch("amplifier_agent_lib.bundle.cache.load_and_prepare_cached", load),
        patch(
            "possibly.providers.ProviderConfig.entry",
            lambda *a, **k: {"module": "unused", "source": "unused", "config": {}},
        ),
    ):
        result = await adapter._bounded(
            {
                "kind": "refine",
                "operation_id": "offline-runtime-probe",
                "turn": 1,
                "base": {
                    "html": '<!doctype html><html><head><title>Score</title></head><body><button id="score" onclick="this.textContent=42">Record</button></body></html>'
                },
            },
            root,
            Grant(timeout_seconds=30).to_dict(),
            lambda: False,
        )
        assert result["directions"][0]["review"]["assertions_passed"] == 1
        print(
            "PASS: existing artifact, visible score assertion, screenshot in next call, immediate submission"
        )
        print((Path(root) / "diagnostics.json").read_text())


asyncio.run(main())
