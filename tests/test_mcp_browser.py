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
            review = next(iter(library.review_snapshot(eid)["reviews"].values()))
            assert review["revision_id"] == second
            assert review["view_id"] == library.get_revision(eid, second)["direction_id"]
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


def test_portable_review_drains_drafts_typed_during_delayed_adoption(tmp_path):
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
        first_exploration, first_revision = started(library)
        second = library.start(
            "A second garden watering app", request_id="second-start", grant={"actions": ["explore"]}
        )
        second_exploration = second["receipt"]["exploration_id"]
        second_revision = second["operation"]["result"]["revision_ids"][0]
        save_started = asyncio.Event()
        release_save = asyncio.Event()
        delayed = True

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 980, "height": 1100})

            async def host_call(params):
                nonlocal delayed
                if params["name"] == "possibly_save_review_state" and delayed:
                    delayed = False
                    save_started.set()
                    await release_save.wait()
                result = await client.call_tool(params["name"], params.get("arguments", {}))
                return result.model_dump(by_alias=True, exclude_none=True)

            await page.expose_function("hostCall", host_call)
            await page.goto("about:blank")
            await page.add_script_tag(content=script)
            initial = await client.call_tool(
                "possibly_get_exploration", {"exploration_id": first_exploration}
            )
            html = (ROOT / "src" / "possibly" / "mcp_app.html").read_text()
            await page.evaluate(
                "([html,result]) => mountPossibly(html,result)",
                [html, initial.model_dump(by_alias=True, exclude_none=True)],
            )
            frame = page.frame_locator("#app")
            await expect(frame.locator("#identity")).to_have_text(first_exploration)

            await frame.locator("#feedback").fill("First A draft")
            await page.evaluate(
                """eid => {
                    window.pendingAdoption = window.possiblyBridge.sendToolResult({
                        structuredContent:{exploration_id:eid},
                        content:[{type:'text',text:JSON.stringify({exploration_id:eid})}],
                    });
                }""",
                second_exploration,
            )
            await asyncio.wait_for(save_started.wait(), timeout=5)
            await frame.locator("#feedback").fill("Latest A draft")
            release_save.set()
            await page.evaluate("() => window.pendingAdoption")
            await expect(frame.locator("#identity")).to_have_text(second_exploration)

            # New-target typing must schedule an independent save, not cancel the final A save.
            await frame.locator("#feedback").fill("B draft")
            await expect(frame.locator("#notice")).to_have_text("Draft saved as context.")
            first_review = next(iter(library.review_snapshot(first_exploration)["reviews"].values()))
            second_review = next(iter(library.review_snapshot(second_exploration)["reviews"].values()))
            assert first_review["revision_id"] == first_revision
            assert first_review["drafts"][first_revision] == "Latest A draft"
            assert second_review["revision_id"] == second_revision
            assert second_review["drafts"][second_revision] == "B draft"
            await browser.close()

    asyncio.run(run())


def test_portable_review_retries_uncertain_generation_and_preserves_drafts_across_navigation(tmp_path):
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
        other_exploration = started(library)[0]
        losses = {"possibly_start": 1, "possibly_make_interactive": 1, "possibly_refine": 1}
        fail_saves = 0
        calls = []

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 980, "height": 1100})

            async def host_call(params):
                nonlocal fail_saves
                calls.append(params)
                if params["name"] == "possibly_save_review_state" and fail_saves:
                    fail_saves -= 1
                    raise RuntimeError("draft transport failed")
                result = await client.call_tool(params["name"], params.get("arguments", {}))
                if losses.get(params["name"], 0):
                    losses[params["name"]] -= 1
                    raise RuntimeError("tool response was lost")
                return result.model_dump(by_alias=True, exclude_none=True)

            await page.expose_function("hostCall", host_call)
            await page.goto("about:blank")
            await page.add_script_tag(content=script)
            html = (ROOT / "src" / "possibly" / "mcp_app.html").read_text()
            await page.evaluate("html => mountPossibly(html,null)", html)
            frame = page.frame_locator("#app")

            await frame.locator("#context").fill("Original garden request")
            await frame.get_by_role("button", name="Explore with the grant below").click()
            await expect(frame.locator("#notice.error")).to_contain_text("tool response was lost")
            assert len(library.intelligence.calls) == 2
            start_calls = [call for call in calls if call["name"] == "possibly_start"]
            await frame.locator("#context").fill("Edited garden request")
            await frame.get_by_role("button", name="Explore with the grant below").click()
            await expect(frame.locator("#notice.error")).to_contain_text(
                "previous start request may have been accepted"
            )
            assert len([call for call in calls if call["name"] == "possibly_start"]) == len(start_calls)
            await frame.locator("#context").fill("Original garden request")
            await frame.get_by_role("button", name="Explore with the grant below").click()
            await expect(frame.locator("#notice")).to_have_text(
                "Exploration accepted. Progress appears here; you can keep chatting."
            )
            assert len(library.intelligence.calls) == 2
            started_exploration = await frame.locator("#identity").text_content()
            assert [call for call in calls if call["name"] == "possibly_start"][0]["arguments"] == [
                call for call in calls if call["name"] == "possibly_start"
            ][1]["arguments"]

            await page.evaluate(
                "eid => window.possiblyBridge.sendToolResult({structuredContent:{exploration_id:eid},content:[{type:'text',text:JSON.stringify({exploration_id:eid})}]})",
                other_exploration,
            )
            await expect(frame.locator("#identity")).to_have_text(other_exploration)
            await frame.locator("#feedback").fill("Draft for the second exploration")
            await page.evaluate(
                "eid => window.possiblyBridge.sendToolResult({structuredContent:{exploration_id:eid},content:[{type:'text',text:JSON.stringify({exploration_id:eid})}]})",
                started_exploration,
            )
            await expect(frame.locator("#identity")).to_have_text(started_exploration)
            assert library.review_snapshot(other_exploration)["reviews"]
            assert "Draft for the second exploration" in str(
                library.review_snapshot(other_exploration)["reviews"]
            )
            assert "Draft for the second exploration" not in str(
                library.review_snapshot(started_exploration)["reviews"]
            )
            await page.evaluate(
                "eid => window.possiblyBridge.sendToolResult({structuredContent:{exploration_id:eid},content:[{type:'text',text:JSON.stringify({exploration_id:eid})}]})",
                other_exploration,
            )
            await expect(frame.locator("#feedback")).to_have_value("Draft for the second exploration")

            await frame.locator("#feedback").fill("Save must fail before moving")
            fail_saves = 1
            await page.evaluate(
                "eid => window.possiblyBridge.sendToolResult({structuredContent:{exploration_id:eid},content:[{type:'text',text:JSON.stringify({exploration_id:eid})}]})",
                started_exploration,
            )
            await expect(frame.locator("#notice.error")).to_contain_text("draft transport failed")
            await expect(frame.locator("#identity")).to_have_text(other_exploration)
            await expect(frame.locator("#feedback")).to_have_value("Save must fail before moving")
            failed_save = [call for call in calls if call["name"] == "possibly_save_review_state"][-1]
            await page.evaluate(
                "eid => window.possiblyBridge.sendToolResult({structuredContent:{exploration_id:eid},content:[{type:'text',text:JSON.stringify({exploration_id:eid})}]})",
                started_exploration,
            )
            await expect(frame.locator("#identity")).to_have_text(started_exploration)
            retried_save = [call for call in calls if call["name"] == "possibly_save_review_state"][-1]
            assert retried_save["arguments"] == failed_save["arguments"]
            assert "Save must fail before moving" in str(
                library.review_snapshot(other_exploration)["reviews"]
            )

            await frame.get_by_role("button", name="Make interactive with grant").click()
            await expect(frame.locator("#notice.error")).to_contain_text("tool response was lost")
            assert len(library.intelligence.calls) == 3
            prototype_calls = [call for call in calls if call["name"] == "possibly_make_interactive"]
            await frame.locator("#grant-settings summary").click()
            await frame.locator("#models").fill("11")
            await frame.get_by_role("button", name="Make interactive with grant").click()
            await expect(frame.locator("#notice.error")).to_contain_text(
                "previous make interactive request may have been accepted"
            )
            assert len([call for call in calls if call["name"] == "possibly_make_interactive"]) == len(
                prototype_calls
            )
            await frame.locator("#models").fill("12")
            await frame.get_by_role("button", name="Make interactive with grant").click()
            await expect(frame.locator("#notice")).to_have_text("Prototype work accepted.")
            assert len(library.intelligence.calls) == 3
            assert [call for call in calls if call["name"] == "possibly_make_interactive"][0][
                "arguments"
            ] == [call for call in calls if call["name"] == "possibly_make_interactive"][1]["arguments"]

            await frame.locator("#feedback").fill("Original refinement")
            await frame.get_by_role("button", name="Refine with grant").click()
            await expect(frame.locator("#notice.error")).to_contain_text("tool response was lost")
            assert len(library.intelligence.calls) == 4
            refine_calls = [call for call in calls if call["name"] == "possibly_refine"]
            await frame.locator("#feedback").fill("Edited refinement")
            await frame.get_by_role("button", name="Refine with grant").click()
            await expect(frame.locator("#notice.error")).to_contain_text(
                "previous refine request may have been accepted"
            )
            assert len([call for call in calls if call["name"] == "possibly_refine"]) == len(refine_calls)
            await frame.locator("#feedback").fill("Original refinement")
            await frame.get_by_role("button", name="Refine with grant").click()
            await expect(frame.locator("#notice")).to_have_text("Refinement accepted.")
            assert len(library.intelligence.calls) == 4
            assert [call for call in calls if call["name"] == "possibly_refine"][0]["arguments"] == [
                call for call in calls if call["name"] == "possibly_refine"
            ][1]["arguments"]
            await browser.close()

    asyncio.run(run())
