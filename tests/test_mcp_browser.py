"""Official AppBridge tests for the native Possibly dashboard MCP transport."""

import asyncio
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import Client
from playwright.async_api import async_playwright, expect
from test_contracts import FakeIntelligence, started

from possibly import Grant, Possibly
from possibly.mcp import create_server

ROOT = Path(__file__).parents[1]
THUMBNAIL = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzMjAiIGhlaWdodD0iMjAwIj4"
    "8cmVjdCB3aWR0aD0iMzIwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzI5NGYzZCIvPjx0ZXh0IHg9IjI0IiB5PSIxMDAi"
    "IGZpbGw9IndoaXRlIiBmb250LXNpemU9IjI4Ij5GaXh0dXJlIHByZXZpZXc8L3RleHQ+PC9zdmc+"
)


class ProviderIntelligence(FakeIntelligence):
    """Scripted public provider surface; browser tests never discover/login remotely."""

    def __init__(self):
        super().__init__()
        self.model = ""

    def provider_settings(self):
        return {
            "providers": [
                {"name": "openai", "configured": True, "source": "fixture", "setup": "Scripted"},
                {"name": "anthropic", "configured": False, "source": "none", "setup": "Scripted"},
            ],
            "effective": {
                "provider": "openai",
                "model": self.model,
                "reasoning_effort": "",
                "configured_fields": [],
            },
        }

    def configure_provider(self, provider, model=None, reasoning_effort=None, provider_config=None):
        self.model = model or ""
        return self.provider_settings()

    def provider_models(self, provider=None, timeout_seconds=30):
        return {"models": [{"id": "fixture-model"}], "default_model": "fixture-model"}

    def test_provider(self, provider=None, *args, **kwargs):
        return {"status": "succeeded", "provider": provider or "openai", "seconds": 0.01}

    def provider_login(self, provider=None, timeout_seconds=300, on_progress=None):
        if on_progress:
            on_progress("Fixture login guidance")
        return {"status": "action_required"}


def host_script():
    node_modules = ROOT / "mcp-app" / "node_modules"
    if not node_modules.exists():
        pytest.skip("Run npm ci --prefix mcp-app to build the independent browser host fixture.")
    return subprocess.run(
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


async def mount(
    page, client, exploration_id, *, theme="dark", width="1280px", lose_response=None, reviewer_id=None
):
    calls = []

    async def host_call(params):
        calls.append(params)
        result = await client.call_tool(params["name"], params.get("arguments", {}))
        if lose_response and lose_response(params):
            raise RuntimeError("simulated host response loss")
        return result.model_dump(by_alias=True, exclude_none=True)

    if not getattr(page, "_possibly_host_call", False):
        await page.expose_function("hostCall", host_call)
        page._possibly_host_call = True
    await page.goto("about:blank")
    await page.add_script_tag(content=host_script())
    initial = await client.call_tool(
        "possibly_open_review",
        {
            "exploration_id": exploration_id,
            "reviewer_id": reviewer_id,
            "request_id": f"open-{reviewer_id or 'new'}",
        },
    )
    await page.evaluate(
        "([html,result,options]) => mountPossibly(html,result,options)",
        [
            (ROOT / "src" / "possibly" / "mcp_app.html").read_text(),
            initial.model_dump(by_alias=True, exclude_none=True),
            {"theme": theme, "width": width, "height": "900px"},
        ],
    )
    return page.frame_locator("#app"), calls


def add_fixture_thumbnails(library, exploration_id):
    with library.store.transaction() as db:
        state = library.store.get(exploration_id, db)
        for revision in state["revisions"].values():
            revision["thumbnail"] = THUMBNAIL
        library.store.put(db, state)


def test_portable_review_reuses_native_dashboard_and_public_tools(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=ProviderIntelligence(), caller="mcp")
        exploration_id, first = started(library)
        add_fixture_thumbnails(library, exploration_id)
        interactive = library.make_interactive(
            exploration_id,
            first,
            grant=Grant(actions=("make_interactive",)),
            request_id="scripted-interactive",
        )["operation"]["result"]["revision_ids"][0]

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            frame, calls = await mount(page, client, exploration_id)

            await expect(frame.get_by_role("heading", name="Compare concepts")).to_be_visible()
            await expect(frame.locator(".card")).to_have_count(2)
            await expect(frame.locator(".thumbnail")).to_have_count(2)
            await expect(frame.get_by_role("button", name="Provider settings")).to_be_visible()
            await expect(frame.get_by_role("button", name="Open side-by-side comparison")).to_be_visible()
            await expect(frame.get_by_role("button", name="Make interactive with grant")).to_have_count(0)
            await frame.get_by_role("button", name="Provider settings").click()
            await expect(frame.locator("#provider-status")).to_contain_text("Configured")
            await frame.get_by_label("Model", exact=True).fill("fixture-model")
            await frame.get_by_role("button", name="Apply for this session").click()
            await expect(frame.get_by_text("Applied for this session.", exact=False)).to_be_visible()
            await frame.get_by_role("button", name="Test connection").click()
            await expect(frame.locator("#provider-result")).to_contain_text("succeeded")
            await frame.get_by_role("button", name="Close settings").click()
            assert library.intelligence.model == "fixture-model"

            await frame.get_by_role("button", name="Mark for comparison", exact=True).first.click()
            await frame.get_by_role("button", name="Mark for comparison", exact=True).first.click()
            await frame.get_by_role("button", name="Open side-by-side comparison").click()
            await expect(frame.locator("#preview-dialog iframe")).to_have_count(2)
            assert all([(await child.evaluate("innerWidth")) == 1280 for child in page.frames[-2:]])
            await page.keyboard.press("Escape")

            await frame.get_by_role("button", name="Choose this direction", exact=True).first.click()
            await expect(frame.get_by_role("tab", name="Calendar", exact=True)).to_be_visible()
            await expect(frame.get_by_label("Version history")).to_be_visible()
            await expect(frame.get_by_role("button", name="Focus prototype")).to_be_visible()
            await expect(frame.get_by_role("button", name="Correct brief")).to_be_visible()
            prototype = page.frames[-1]
            assert (
                await prototype.evaluate(
                    "(() => {try{return parent.document.body.innerText}catch{return 'isolated'}})()"
                )
                == "isolated"
            )
            await frame.get_by_label("Refinement feedback").fill("Keep calendar labels readable")
            await expect(frame.get_by_text("Draft saved", exact=True)).to_be_visible()

            await page.wait_for_timeout(2100)
            await frame.get_by_label("Version history").select_option(interactive)
            await frame.get_by_text("Export this version", exact=True).click()
            async with page.expect_download() as download:
                await frame.get_by_role("button", name="Download HTML").click()
            assert (await download.value).suggested_filename == "prototype.html"
            assert (
                library.export(exploration_id, interactive, request_id="exact-export")["receipt"]["handoff"][
                    "revision_id"
                ]
                == interactive
            )

            assert all(call["name"].startswith("possibly_") for call in calls)
            assert not errors, errors
            await page.screenshot(path=str(tmp_path / "possibly-native-mcp-desktop.png"), full_page=True)
            await browser.close()

    asyncio.run(run())


def test_portable_review_attachment_restores_workspace_history_appearance_and_draft(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        exploration_id, first = started(library)
        add_fixture_thumbnails(library, exploration_id)
        interactive = library.make_interactive(
            exploration_id,
            first,
            grant=Grant(actions=("make_interactive",)),
            request_id="attached-interactive",
        )["operation"]["result"]["revision_ids"][0]

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            frame, _ = await mount(page, client, exploration_id)
            await frame.get_by_role("button", name="Choose this direction", exact=True).first.click()
            await expect(frame.get_by_role("tab", name="Calendar", exact=True)).to_be_visible()
            await frame.get_by_label("Version history").select_option(interactive)
            await frame.get_by_label("Refinement feedback").fill("Keep this exact earlier workspace draft")
            await expect(frame.locator("#save-status")).to_have_text("Draft saved")
            await frame.get_by_role("button", name="Appearance: system", exact=True).click()
            await expect(frame.locator("#save-status")).to_have_text("Draft saved")
            reviewer = await page.frames[1].evaluate("reviewer")

            reopened, _ = await mount(page, client, exploration_id, reviewer_id=reviewer)
            await expect(reopened.get_by_role("tab", name="Calendar", exact=True)).to_have_attribute(
                "aria-selected", "true"
            )
            await expect(reopened.get_by_label("Version history")).to_have_value(interactive)
            await expect(reopened.get_by_label("Refinement feedback")).to_have_value(
                "Keep this exact earlier workspace draft"
            )
            await expect(reopened.get_by_role("button", name="Appearance: light", exact=True)).to_be_visible()
            assert await page.frames[1].evaluate("reviewer") == reviewer
            await browser.close()

    asyncio.run(run())


def test_partial_host_context_preserves_native_draft_and_appearance_override(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        exploration_id, _ = started(library)

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 700, "height": 900})
            frame, _ = await mount(page, client, exploration_id, width="700px")
            await expect(frame.get_by_role("heading", name="Compare concepts")).to_be_visible()
            assert (
                await frame.locator("html").evaluate(
                    "node => getComputedStyle(node).getPropertyValue('--bg').trim()"
                )
                == "#171d1a"
            )

            await frame.get_by_text("Feedback on this concept", exact=True).first.click()
            await frame.get_by_label("Concept feedback").first.fill("Preserve this outgoing draft")
            await expect(frame.get_by_text("Draft saved", exact=True)).to_be_visible()
            await page.evaluate("() => sendPossiblyHostContext({displayMode:'fullscreen'})")
            await expect(frame.get_by_label("Concept feedback").first).to_have_value(
                "Preserve this outgoing draft"
            )

            await frame.get_by_role("button", name="Appearance: system", exact=True).click()
            await page.evaluate("() => sendPossiblyHostContext({theme:'dark'})")
            assert (
                await frame.locator("html").evaluate(
                    "node => getComputedStyle(node).getPropertyValue('--bg').trim()"
                )
                == "#f5f3eb"
            )
            await frame.get_by_role("button", name="Appearance: light", exact=True).click()
            await frame.get_by_role("button", name="Appearance: dark", exact=True).click()
            await page.evaluate("() => sendPossiblyHostContext({theme:'light'})")
            assert (
                await frame.locator("html").evaluate(
                    "node => getComputedStyle(node).getPropertyValue('--bg').trim()"
                )
                == "#f5f3eb"
            )
            await page.screenshot(path=str(tmp_path / "possibly-native-mcp-narrow.png"), full_page=True)
            await browser.close()

    asyncio.run(run())


def test_portable_decision_retry_reuses_an_accepted_request_after_response_loss(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        exploration_id, first = started(library)
        losses = {"decision": 1}

        def lose_response(params):
            if params["name"] == "possibly_record_decision" and losses["decision"]:
                losses["decision"] -= 1
                return True
            return False

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            frame, calls = await mount(page, client, exploration_id, lose_response=lose_response)
            await expect(frame.get_by_role("heading", name="Compare concepts")).to_be_visible()
            choose = frame.get_by_role("button", name="Choose this direction", exact=True).first
            await choose.click()
            await expect(frame.get_by_role("tab", name="Calendar", exact=True)).to_have_count(0)
            await page.wait_for_timeout(100)
            await frame.get_by_role("button", name="Retry selection", exact=True).click()
            await expect(frame.get_by_role("tab", name="Calendar", exact=True)).to_be_visible()
            selections = [
                call
                for call in calls
                if call["name"] == "possibly_record_decision" and call["arguments"]["action"] == "select"
            ]
            assert len(selections) == 2
            assert selections[0]["arguments"] == selections[1]["arguments"]
            assert library.review_snapshot(exploration_id)["selected_revision"] == first
            assert len(library.review_snapshot(exploration_id)["decisions"]) == 1
            await browser.close()

    asyncio.run(run())
