import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from playwright.sync_api import expect, sync_playwright
from test_contracts import FakeIntelligence

from possibly import Grant, Possibly, Presentation
from possibly.runner import serve, write_access_token


def test_dashboard_selection_refresh_and_isolation(tmp_path):
    from possibly.intelligence import AmplifierIntelligence

    class DashboardIntelligence(FakeIntelligence, AmplifierIntelligence):
        def __init__(self):
            FakeIntelligence.__init__(self)
            AmplifierIntelligence.__init__(self, allow_environment=True)

        def test_provider(self, provider=None, *args, **kwargs):
            return {"status": "succeeded", "provider": provider, "seconds": 0.01}

        def provider_login(self, provider=None, timeout_seconds=300, on_progress=None):
            on_progress("Device login instructions")
            return {"status": "action_required"}

    p = Possibly(tmp_path, intelligence=DashboardIntelligence(), caller="dashboard")
    result = p.start("Garden", grant=Grant(prototype_after_selection=True), request_id="start")
    eid = result["receipt"]["exploration_id"]
    token = write_access_token(p.store.root, "test-runner")
    with p.store.transaction() as db:
        s = p.store.get(eid, db)
        s["presentation"] = Presentation(mode="builtin", service=True).to_dict()
        s["runner"] = {"id": "test-runner", "state": "starting", "heartbeat": time.time()}
        p.store.put(db, s)
    thread = threading.Thread(target=serve, args=(p, eid), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not (url := p.get_exploration(eid)["runner"].get("url")):
            assert time.monotonic() < deadline
            time.sleep(0.02)
        base = url.split("#")[0]
        with pytest.raises(HTTPError) as err:
            urlopen(base + "state")
        assert err.value.code == 401
        with pytest.raises(HTTPError) as err:
            urlopen(base + "settings")
        assert err.value.code == 401
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            browser_errors = []
            page.on("pageerror", lambda e: browser_errors.append(str(e)))
            page.on("console", lambda m: print("BROWSER:", m.text) if m.type == "error" else None)
            page.set_default_timeout(10000)
            page.goto(url)
            page.get_by_role("button", name="Choose this direction").first.wait_for()
            page.get_by_role("button", name="Provider settings").click()
            page.get_by_label("Provider", exact=True).select_option("anthropic")
            page.get_by_label("Model", exact=True).fill("test-model")
            page.get_by_role("button", name="Apply for this session").click()
            page.get_by_text("Applied for this session.", exact=False).wait_for()
            assert p.intelligence.configuration().model == "test-model"
            page.get_by_label("Provider", exact=True).select_option("gemini")
            page.get_by_role("button", name="Test connection").click()
            page.locator("#provider-result").filter(has_text='"succeeded"').wait_for()
            assert page.get_by_label("Provider", exact=True).input_value() == "gemini"
            page.get_by_role("button", name="Sign in / setup").click()
            page.locator("#provider-result").filter(has_text="Device login instructions").wait_for()
            page.get_by_role("button", name="Close settings").click()
            assert "test-model" not in json.dumps(p.store.get(eid))
            assert page.locator("iframe").count() == 0
            page.emulate_media(color_scheme="dark")
            page.get_by_role("button", name="Open preview", exact=True).first.click()
            frame = page.locator("dialog iframe")
            expect(frame).to_have_count(1)
            assert frame.count() == 1
            assert frame.get_attribute("sandbox") == "allow-scripts"
            child = page.frames[-1]
            child.wait_for_selector("body")
            assert child.evaluate("innerWidth") == 1280
            assert child.evaluate("getComputedStyle(document.documentElement).colorScheme") == "light only"
            assert not p.review_snapshot(eid)["decisions"]
            page.get_by_role("button", name="Back to concepts").click()
            page.get_by_role("button", name="Mark for comparison", exact=True).first.click()
            expect(page.get_by_role("button", name="Remove from comparison", exact=True)).to_have_count(1)
            page.get_by_role("button", name="Mark for comparison", exact=True).first.click()
            assert page.locator("iframe").count() == 0
            page.get_by_role("button", name="Open side-by-side comparison").click()
            expect(page.locator("iframe")).to_have_count(2)
            assert all(f.evaluate("innerWidth") == 1280 for f in page.frames[1:])
            page.keyboard.press("Escape")
            expect(page.locator("iframe")).to_have_count(0)
            page.get_by_text("Feedback on this concept", exact=True).first.click()
            page.get_by_label("Concept feedback").first.fill("Unsent concept note")
            page.get_by_text("Draft saved", exact=True).wait_for()
            snapshot = p.review_snapshot(eid)
            assert any("Unsent concept note" in r["drafts"].values() for r in snapshot["reviews"].values())
            assert not snapshot["decisions"]
            page.get_by_role("button", name="Choose this direction").first.click()
            page.get_by_role("status").filter(has_text="Recorded").wait_for()
            page.reload()
            page.get_by_role("heading", name="Calendar", exact=True).wait_for()
            assert page.get_by_role("tab", name="Calendar").get_attribute("aria-selected") == "true"
            expect(page.locator("iframe")).to_have_count(1)
            assert not page.get_by_text("About this direction").locator("..").get_attribute("open")
            page.get_by_label("Refinement feedback").fill("Include a repair budget")
            page.get_by_role("button", name="Send feedback", exact=True).click()
            page.get_by_text("Include a repair budget", exact=True).wait_for()
            # Latest revision follows the branch while the initial comparison stays unchanged.
            rid = p.get_exploration(eid)["selected_revision"]
            result = p.refine(
                eid, rid, "Include a repair budget", grant=Grant(actions=("refine",)), request_id="refine"
            )
            new_id = result["operation"]["result"]["revision_ids"][0]
            page.get_by_role("button", name="Download HTML", include_hidden=True).wait_for(state="attached")
            expect(page.locator(".version option")).to_have_count(4)
            page.get_by_text("Export this version", exact=True).click()
            with page.expect_download() as download:
                page.get_by_role("button", name="Download HTML").click()
            assert download.value.suggested_filename == "prototype.html"
            assert p.get_exploration(eid)["revisions"][new_id]["kind"] == "interactive"
            page.get_by_role("tab", name="Compare concepts", exact=True).click()
            expect(page.locator(".card")).to_have_count(2)
            page.get_by_role("button", name="Choose this direction").click()
            page.get_by_role("tab", name="Availability", exact=True).wait_for()
            page.get_by_role("tab", name="Calendar", exact=True).click()
            page.get_by_text("Include a repair budget", exact=True).wait_for()
            page.get_by_role("button", name="Appearance: system", exact=True).click()
            page.get_by_role("button", name="Appearance: light", exact=True).click()
            assert page.evaluate("getComputedStyle(document.documentElement).colorScheme") == "dark"
            page.reload()
            assert page.get_by_role("button", name="Appearance: dark", exact=True).is_visible()
            page.get_by_role("button", name="Appearance: dark", exact=True).click()
            page.emulate_media(color_scheme="dark")
            assert (
                page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
                == "#171d1a"
            )
            page.emulate_media(color_scheme="light")
            assert (
                page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
                == "#f5f3eb"
            )
            page.screenshot(path="/private/tmp/possibly-dashboard.png", full_page=True)
            assert not browser_errors
            browser.close()
        state = p.get_exploration(eid)
        assert state["selected_revision"]
        assert len(state["decisions"]) == 3
        assert token not in json.dumps(p.store.get(eid))
        assert token not in json.dumps(p.read_changes(eid))
        assert len([o for o in state["operations"].values() if o["kind"] == "make_interactive"]) == 1
        body = json.dumps(
            {
                "revision_id": state["selected_revision"],
                "action": "reject",
                "request_id": "bad-origin",
                "expected_state_version": state["state_version"],
            }
        ).encode()
        with pytest.raises(HTTPError) as err:
            urlopen(
                Request(
                    base + "decision",
                    data=body,
                    headers={"Authorization": "Bearer " + token, "Origin": "https://untrusted.example"},
                )
            )
        assert err.value.code == 403
    finally:
        assert p.stop(eid, request_id="cleanup")["cleanup"]["status"] == "succeeded"
        thread.join(3)
        assert not thread.is_alive()


def test_owned_subprocess_runner_starts_and_stops_without_model_work(tmp_path):
    from possibly.intelligence import AmplifierIntelligence
    from possibly.runner import launch

    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    result = p.start("Garden", grant=Grant(), request_id="seed")
    eid = result["receipt"]["exploration_id"]
    with p.store.transaction() as db:
        s = p.store.get(eid, db)
        s["presentation"] = Presentation(mode="builtin", service=True).to_dict()
        p.store.put(db, s)
    # Seeded artifacts are already complete. This checks the actual child-process
    # lifetime/presentation path without another provider call.
    p.intelligence = AmplifierIntelligence(allow_environment=True)
    p.execution = "owned_runner"
    try:
        launched = launch(p, eid)
        assert launched["status"] == "available"
        assert p.get_exploration(eid)["runner"]["pid"]
        assert p.get_exploration(eid)["runner"]["url"].startswith("http://127.0.0.1:")
    finally:
        assert p.stop(eid, request_id="stop")["cleanup"]["status"] == "succeeded"


def test_runner_reports_expired_queued_grant(tmp_path):
    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    result = p.start("Garden", grant=Grant(prototype_after_selection=True), request_id="seed")
    eid = result["receipt"]["exploration_id"]
    rid = result["operation"]["result"]["revision_ids"][0]
    selected = p.record_decision(eid, rid, action="select", request_id="choose")
    oid = selected["receipt"]["follow_up"]
    with p.store.transaction() as db:
        state = p.store.get(eid, db)
        state["operations"][oid]["grant"]["expires_at"] = time.time() - 1
        write_access_token(p.store.root, "test-expired")
        state["runner"] = {
            "id": "test-expired",
            "state": "starting",
            "heartbeat": time.time(),
        }
        p.store.put(db, state)
    thread = threading.Thread(target=serve, args=(p, eid), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while p.get_operation(eid, oid)["state"] == "queued":
            assert time.monotonic() < deadline
            time.sleep(0.02)
        op = p.get_operation(eid, oid)
        assert op["state"] == "failed"
        assert op["failure"]["code"] == "invalid_grant"
    finally:
        p.stop(eid, request_id="stop")
        thread.join(3)
