"""Official AppBridge tests for the native Possibly dashboard MCP transport."""

import asyncio
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import Client
from playwright.async_api import async_playwright, expect
from test_contracts import FakeIntelligence, design, started

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
    page,
    client,
    exploration_id,
    *,
    theme="dark",
    width="1280px",
    lose_response=None,
    reviewer_id=None,
    initial_tool="possibly_open_review",
    revision_id=None,
    before_call=None,
    after_call=None,
):
    calls = []

    async def host_call(params):
        calls.append(params)
        if before_call:
            await before_call(params)
        result = await client.call_tool(params["name"], params.get("arguments", {}))
        if after_call:
            await after_call(params)
        if lose_response and lose_response(params):
            raise RuntimeError("simulated host response loss")
        return result.model_dump(by_alias=True, exclude_none=True)

    if not getattr(page, "_possibly_host_call", False):
        await page.expose_function("hostCall", host_call)
        page._possibly_host_call = True
    await page.goto("about:blank")
    await page.add_script_tag(content=host_script())
    initial_arguments = {"exploration_id": exploration_id}
    if initial_tool == "possibly_open_review":
        initial_arguments.update(
            {
                "reviewer_id": reviewer_id,
                "request_id": f"open-{reviewer_id or 'new'}",
            }
        )
    if revision_id:
        initial_arguments["revision_id"] = revision_id
    initial = await client.call_tool(initial_tool, initial_arguments)
    await page.evaluate(
        "([html,result,options]) => mountPossibly(html,result,options)",
        [
            (ROOT / "src" / "possibly" / "mcp_app.html").read_text(),
            initial.model_dump(by_alias=True, exclude_none=True),
            {"theme": theme, "width": width, "height": "900px"},
        ],
    )
    return page.frame_locator("#app"), calls


def retained_child_without_selection(tmp_path):
    refined = design(1)
    refined["directions"][0]["html"] = refined["directions"][0]["html"].replace(
        "Claim shift", "Try refined child"
    )
    library = Possibly(tmp_path, intelligence=FakeIntelligence([design(), refined]), caller="mcp")
    eid, root = started(library)
    child = library.make_interactive(
        eid, root, grant=Grant(actions=("make_interactive",)), request_id="child"
    )["operation"]["result"]["revision_ids"][0]
    # Returned-live-trial shape: failed partial roots, one completed child, no
    # selections. Previewing the retained child must not require a select decision.
    with library.store.transaction() as db:
        state = library.store.get(eid, db)
        for revision in state["revisions"].values():
            if not revision["parent"]:
                revision.update(kind="partial", superseded=True)
        library.store.put(db, state)
    return library, eid, child


@pytest.mark.parametrize(
    "initial_tool", ["possibly_get_revision", "possibly_open_review", "possibly_get_exploration"]
)
def test_completed_child_preview_without_select_or_generation(tmp_path, initial_tool):
    async def run():
        library, eid, child = retained_child_without_selection(tmp_path)
        before = library.store.get(eid)
        model_calls = len(library.intelligence.calls)
        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            frame, calls = await mount(
                page,
                client,
                eid,
                initial_tool=initial_tool,
                revision_id=child if initial_tool == "possibly_get_revision" else None,
            )
            if initial_tool != "possibly_get_revision":
                await frame.get_by_role("button", name="Review versions", exact=True).click()
            await expect(frame.get_by_text("Preview · not selected", exact=True)).to_be_visible()
            if initial_tool == "possibly_get_revision":
                await expect(frame.get_by_label("Version history")).to_have_value(child)
            prototype = frame.frame_locator('iframe[title="Calendar preview"]')
            await expect(prototype.get_by_role("button", name="Try refined child")).to_be_visible()
            await prototype.get_by_role("button", name="Try refined child").click()
            await expect(prototype.get_by_role("button", name="Claimed")).to_be_visible()
            await expect(frame.locator('iframe[title="Calendar preview"]')).to_have_attribute(
                "sandbox", "allow-scripts"
            )

            if initial_tool == "possibly_get_revision":
                # Repeated host delivery must not create another review identity
                # or disturb a view/draft the person has since navigated to.
                await frame.get_by_label("Refinement feedback").fill("Retain my preview draft")
                await expect(frame.locator("#save-status")).to_have_text("Draft saved")
                initial = await client.call_tool(
                    "possibly_get_revision", {"exploration_id": eid, "revision_id": child}
                )
                for _ in range(2):
                    await page.evaluate(
                        "result => window.possiblyBridge.sendToolResult(result)",
                        initial.model_dump(by_alias=True, exclude_none=True),
                    )
                # The bridge handles messages asynchronously; a state read is a
                # deterministic round trip before checking the retained identity.
                await page.frames[1].evaluate("refresh(true)")
                await expect(frame.get_by_label("Refinement feedback")).to_have_value(
                    "Retain my preview draft"
                )
                assert len(library.review_snapshot(eid)["reviews"]) == 1
                assert sum(c["name"] == "possibly_open_review" for c in calls) == 1

                first_reviewer = next(iter(library.review_snapshot(eid)["reviews"]))
                root = before["revisions"][child]["parent"]
                # New host navigation A -> B -> A is not a duplicate of the
                # original A delivery. Each independent view keeps its drafts.
                for target in (root, child):
                    result = await client.call_tool(
                        "possibly_get_revision", {"exploration_id": eid, "revision_id": target}
                    )
                    await page.evaluate(
                        "result => window.possiblyBridge.sendToolResult(result)",
                        result.model_dump(by_alias=True, exclude_none=True),
                    )
                    await expect(frame.get_by_label("Version history")).to_have_value(target)
                reviews = library.review_snapshot(eid)["reviews"]
                assert len(reviews) == 3
                assert reviews[first_reviewer]["drafts"][child] == "Retain my preview draft"

            await page.screenshot(path=str(tmp_path / f"{initial_tool}-preview.png"))
            after = library.store.get(eid)
            assert after["selected_revision"] == before["selected_revision"] is None
            assert after["decisions"] == before["decisions"] == []
            assert after["revisions"] == before["revisions"]
            assert after["operations"] == before["operations"]
            assert after["lifecycle"] == before["lifecycle"]
            assert after["active_period_id"] == before["active_period_id"]
            assert len(library.intelligence.calls) == model_calls
            assert not any(
                c["name"] in {"possibly_record_decision", "possibly_refine", "possibly_reopen"} for c in calls
            )
            await browser.close()

    asyncio.run(run())


@pytest.mark.parametrize("lost_tool", ["possibly_open_review", "possibly_save_review_state"])
def test_initial_revision_attachment_retries_exact_accepted_request(tmp_path, lost_tool):
    async def run():
        library, eid, child = retained_child_without_selection(tmp_path)
        model_calls = len(library.intelligence.calls)
        lost = False

        def lose_once(params):
            nonlocal lost
            if params["name"] == lost_tool and not lost:
                lost = True
                return True
            return False

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            frame, calls = await mount(
                page,
                client,
                eid,
                initial_tool="possibly_get_revision",
                revision_id=child,
                lose_response=lose_once,
            )
            await expect(frame.locator("#notice")).to_contain_text("Review unavailable.")
            assert len(library.review_snapshot(eid)["reviews"]) == 1
            result = await client.call_tool(
                "possibly_get_revision", {"exploration_id": eid, "revision_id": child}
            )
            await page.evaluate(
                "result => window.possiblyBridge.sendToolResult(result)",
                result.model_dump(by_alias=True, exclude_none=True),
            )
            await expect(frame.get_by_label("Version history")).to_have_value(child)
            await expect(
                frame.frame_locator('iframe[title="Calendar preview"]').get_by_role(
                    "button", name="Try refined child"
                )
            ).to_be_visible()
            retried = [c["arguments"] for c in calls if c["name"] == lost_tool]
            assert len(retried) == 2
            assert retried[0] == retried[1]
            assert len(library.review_snapshot(eid)["reviews"]) == 1
            assert library.review_snapshot(eid)["selected_revision"] is None
            assert library.review_snapshot(eid)["decisions"] == []
            assert len(library.intelligence.calls) == model_calls
            await browser.close()

    asyncio.run(run())


def test_late_draft_save_cannot_clear_new_reviewers_unsaved_draft(tmp_path):
    async def run():
        library, eid, child = retained_child_without_selection(tmp_path)
        a_saved = asyncio.Event()
        release_a = asyncio.Event()

        async def delay_a(params):
            if (
                params["name"] == "possibly_save_review_state"
                and params["arguments"].get("draft") == "A draft"
            ):
                a_saved.set()
                await release_a.wait()

        async def reject_b(params):
            if (
                params["name"] == "possibly_save_review_state"
                and params["arguments"].get("draft") == "B draft"
            ):
                raise RuntimeError("B save unavailable")

        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            frame, _ = await mount(
                page,
                client,
                eid,
                initial_tool="possibly_get_revision",
                revision_id=child,
                before_call=reject_b,
                after_call=delay_a,
            )
            await frame.get_by_label("Refinement feedback").fill("A draft")
            await asyncio.wait_for(a_saved.wait(), 5)
            a_reviewer = next(iter(library.review_snapshot(eid)["reviews"]))
            b_opened = await client.call_tool(
                "possibly_open_review", {"exploration_id": eid, "request_id": "open-B"}
            )
            b_reviewer = b_opened.structured_content["result"]["receipt"]["reviewer_id"]
            await client.call_tool(
                "possibly_save_review_state",
                {
                    "exploration_id": eid,
                    "reviewer_id": b_reviewer,
                    "view_id": library.get_revision(eid, child)["direction_id"],
                    "view_revision_id": child,
                    "revision_id": child,
                    "sequence": 0,
                    "request_id": "view-B",
                },
            )
            try:
                await page.evaluate(
                    "result => window.possiblyBridge.sendToolResult(result)",
                    b_opened.model_dump(by_alias=True, exclude_none=True),
                )
                await expect(frame.get_by_label("Refinement feedback")).to_have_value("")
                await frame.get_by_label("Refinement feedback").fill("B draft")
            finally:
                release_a.set()
            await expect(frame.locator("#save-status")).to_contain_text("Draft not saved:")
            await expect(frame.get_by_label("Refinement feedback")).to_have_value("B draft")
            recovered = await page.frames[1].evaluate("key => recoveryDrafts[recoveryKey(key)]", child)
            assert recovered == "B draft"
            reviews = library.review_snapshot(eid)["reviews"]
            assert reviews[a_reviewer]["drafts"][child] == "A draft"
            assert reviews[b_reviewer]["drafts"].get(child, "") == ""
            assert library.review_snapshot(eid)["decisions"] == []
            await browser.close()

    asyncio.run(run())


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
