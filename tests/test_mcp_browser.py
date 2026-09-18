"""Actual App SDK + independent AppBridge host; no host-specific route or model call."""

import asyncio
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import Client
from playwright.async_api import async_playwright, expect
from test_contracts import FakeIntelligence, started

from possibly import Possibly
from possibly.mcp import create_server

ROOT = Path(__file__).parents[1]


def test_portable_review_shared_state_and_preview_isolation(tmp_path):
    node_modules = ROOT / "mcp-app" / "node_modules"
    if not node_modules.exists():
        pytest.skip("Run npm ci --prefix mcp-app to build the independent browser host fixture.")
    script = subprocess.run(
        [
            str(node_modules / ".bin" / "esbuild"),
            str(ROOT / "mcp-app" / "test-host.js"),
            "--bundle",
            "--format=iife",
            "--log-level=error",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        eid, first = started(library)
        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 980, "height": 1100})
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            calls = []

            async def host_call(params):
                calls.append(params)
                result = await client.call_tool(params["name"], params.get("arguments", {}))
                return result.model_dump(by_alias=True, exclude_none=True)

            await page.expose_function("hostCall", host_call)
            await page.goto("about:blank")
            await page.add_script_tag(content=script)
            initial = await client.call_tool("possibly_get_exploration", {"exploration_id": eid})
            html = (ROOT / "src" / "possibly" / "mcp_app.html").read_text()
            await page.evaluate(
                "([html,result]) => mountPossibly(html,result)",
                [html, initial.model_dump(by_alias=True, exclude_none=True)],
            )
            frame = page.frame_locator("#app")
            await expect(frame.locator("#intent")).to_contain_text("Coordinate garden watering")
            await expect(frame.locator("#preview")).to_be_visible()
            await frame.get_by_role("button", name="Choose this revision", exact=True).click()
            await expect(frame.locator("#notice")).to_have_text("Choice recorded.")
            assert library.review_snapshot(eid)["selected_revision"] == first
            await frame.locator("#feedback").fill("Keep calendar labels readable")
            await expect(frame.locator("#notice")).to_have_text("Draft saved as context.")
            assert "Keep calendar labels readable" in str(library.review_snapshot(eid)["reviews"])
            # Navigating to another revision must not retarget the first one's draft.
            second = list(library.get_exploration(eid)["revisions"])[1]
            await frame.locator(f'button[data-id="{second}"]').click()
            await expect(frame.locator("#notice")).to_have_text("Review position saved.")
            await expect(frame.locator("#feedback")).to_have_value("")
            await frame.locator(f'button[data-id="{first}"]').click()
            await expect(frame.locator("#feedback")).to_have_value("Keep calendar labels readable")
            # Generated prototypes cannot reach the App bridge by forging a tool call.
            prototype = page.frames[-1]
            count = len([call for call in calls if call["name"] == "possibly_stop"])
            await prototype.evaluate(
                "parent.postMessage({jsonrpc:'2.0',id:999,method:'tools/call',params:{name:'possibly_stop',arguments:{exploration_id:'forged',request_id:'forged'}}},'*')"
            )
            await page.wait_for_timeout(150)
            assert len([call for call in calls if call["name"] == "possibly_stop"]) == count
            assert (
                await prototype.evaluate(
                    "(() => {try{return parent.document.body.innerText}catch{return 'isolated'}})()"
                )
                == "isolated"
            )
            assert len(library.intelligence.calls) == 1
            # Agent-side state changes become visible through the same read-only refresh.
            library.record_decision(eid, second, action="select", request_id="agent-selected")
            await frame.get_by_role("button", name="Refresh", exact=True).click()
            await expect(frame.locator("#review-data")).to_contain_text(second)
            await frame.locator("#grant-settings summary").click()
            await frame.locator("#turns").fill("0")
            await frame.locator("#prototype").click()
            await expect(frame.locator("#notice.error")).to_contain_text("turns must be between")
            assert len(library.intelligence.calls) == 1
            await frame.locator("#turns").fill("2")
            await frame.locator("#prototype").click()
            await expect(frame.locator("#notice")).to_have_text("Prototype work accepted.")
            assert len(library.intelligence.calls) == 2
            interactive = list(library.get_exploration(eid)["revisions"])[-1]
            await frame.locator(f'button[data-id="{interactive}"]').click()
            await frame.locator("#export").click()
            await expect(frame.locator("#export-result a")).to_have_count(2)
            await frame.locator("#stop").click()
            await expect(frame.locator("#notice")).to_have_text("Stop completed.")
            assert library.get_exploration(eid)["lifecycle"] == "stopped"
            assert library.read_artifact(eid, interactive)
            await page.screenshot(path=str(tmp_path / "possibly-mcp-review.png"), full_page=True)
            assert not errors, errors
            await browser.close()

    asyncio.run(run())
