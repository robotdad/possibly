import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from playwright.sync_api import expect, sync_playwright
from referencing import Registry, Resource
from test_contracts import FakeIntelligence, design, started

from possibly import Grant, Possibly, PossiblyError
from possibly.presentation import CATALOG, PROTOCOL


def action(surface, name, **context):
    return {
        "name": name,
        "surfaceId": surface["surface_id"],
        "sourceComponentId": "test",
        "timestamp": "2026-09-17T00:00:00Z",
        "context": context,
    }


def test_surface_contract_and_decision_semantics(tmp_path):
    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    eid, rid = started(p)
    surface = p.review_surface(eid)
    serialized = json.dumps(surface)
    for forbidden in ('"html"', '"runner"', '"grant"', '"thumbnail"', '"provider_config"'):
        assert forbidden not in serialized
    assert surface["protocol"] == PROTOCOL and surface["catalog_id"] == CATALOG
    assert len(p.intelligence.calls) == 1
    select = action(surface, "select", revision_id=rid, expected_state_version=surface["state_version"])
    first = p.review_action(eid, select, request_id="choose")
    assert p.review_action(eid, select, request_id="choose")["receipt"] == first["receipt"]
    assert len(p.review_snapshot(eid)["decisions"]) == 1
    with pytest.raises(PossiblyError):
        p.review_action(eid, select, request_id="stale")
    p.review_action(
        eid,
        action(surface, "draft", revision_id=rid, view_id="compare", text="Unsubmitted"),
        reviewer_id="alice",
        sequence=3,
        request_id="draft",
    )
    p.review_action(
        eid,
        action(surface, "draft", revision_id=rid, view_id="compare", text="Older"),
        reviewer_id="alice",
        sequence=2,
        request_id="older",
    )
    assert p.review_snapshot(eid)["reviews"]["alice"]["drafts"][rid] == "Unsubmitted"
    assert len(p.intelligence.calls) == 1
    assert p.review_surface(eid, reviewer_id="bob")["messages"][1]["updateDataModel"]["value"]["drafts"] == {}
    with pytest.raises(PossiblyError, match="Unsupported"):
        p.review_action(eid, action(surface, "refine", revision_id=rid), request_id="no-grant")
    p.stop(eid, request_id="stop")
    p.reopen(eid, rid, request_id="reopen")
    with pytest.raises(PossiblyError, match="active period"):
        p.review_action(eid, select, request_id="old-surface")


@pytest.mark.parametrize(
    "view", [[], "", {"preview": ["same", "same"]}, {"revision_id": "missing"}, {"focused": "yes"}]
)
def test_invalid_views_are_rejected(tmp_path, view):
    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    eid, _ = started(p)
    with pytest.raises(PossiblyError):
        p.review_surface(eid, view=view)


def validate_surface(surface):
    root = Path(__file__).parent / "fixtures" / "a2ui"
    common = json.loads((root / "common_types.json").read_text())
    server = json.loads((root / "server_to_client.json").read_text())
    inline = Possibly.review_catalog()[PROTOCOL]["inlineCatalogs"][0]
    # Inline catalogs map component names to their schemas. The envelope references anyComponent.
    catalog = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {
            "anyComponent": {"oneOf": list(inline["components"].values())},
            "theme": {"type": "object"},
        },
    }
    registry = Registry().with_resources(
        [
            ("https://a2ui.org/specification/v0_9/common_types.json", Resource.from_contents(common)),
            ("https://a2ui.org/specification/v0_9/catalog.json", Resource.from_contents(catalog)),
        ]
    )
    validator = Draft202012Validator(server, registry=registry)
    for message in surface["messages"]:
        validator.validate(message)
    components = surface["messages"][2]["updateComponents"]["components"]
    ids = {c["id"] for c in components}
    assert len(ids) == len(components)
    for component in components:
        for child in component.get("children", []):
            assert child in ids
        if "child" in component:
            assert component["child"] in ids


def test_all_projected_views_validate_against_upstream_protocol(tmp_path):
    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    eid, rid = started(p)
    initial = p.review_surface(eid)
    validate_surface(initial)
    ids = list(p.get_exploration(eid)["revisions"])
    validate_surface(p.review_surface(eid, view={"comparing": ids, "preview": ids}))
    selected = p.review_action(
        eid,
        action(initial, "select", revision_id=rid, expected_state_version=initial["state_version"]),
        request_id="choose",
    )
    view = selected["view"]
    p.record_decision(eid, rid, action="feedback", text="Make room for cost", request_id="feedback")
    validate_surface(p.review_surface(eid, view=view))
    p.refine(eid, rid, "Keep claiming", request_id="refine", grant=Grant(actions=("refine",)))
    validate_surface(p.review_surface(eid, view={**view, "revision_id": rid, "focused": True}))
    with pytest.raises(PossiblyError):
        p.review_surface(eid, view={"preview": ["unknown"]})
    with pytest.raises(PossiblyError):
        p.review_surface(eid, view={"direction_id": []})
    p.record_decision(eid, rid, action="brief_correction", text="Use individual plots", request_id="correct")
    validate_surface(p.review_surface(eid, view=view))


HOST = """<!doctype html><html><head><meta charset="utf-8"><style>
body{font:16px system-ui;margin:0;background:#f5f3eb;color:#24322d}header{padding:20px;background:#20394a;color:white}
main{padding:20px;max-width:1300px;margin:auto}#status{padding:8px}#saved{display:block}
</style></head><body><header><h1>Example host application</h1></header>
<div id="status" role="status"></div><small id="saved"></small><main id="review"></main>
<script type="module">
import {mountReview} from '/review.js';
window.review=mountReview(document.querySelector('#review'),{
 reviewerId:'embedded-reviewer',pollInterval:60000,
 loadSurface:async view=>{if(window.delaySurface)await new Promise(r=>setTimeout(r,window.delaySurface));return bridge('surface',{view,reviewer_id:'embedded-reviewer'})},
 sendAction:data=>bridge('action',data),
 loadArtifact:revision_id=>bridge('artifact',{revision_id}),
 loadThumbnail:revision_id=>bridge('thumbnail',{revision_id}),
 onNotice:text=>document.querySelector('#status').textContent=text,
 onSaveStatus:text=>document.querySelector('#saved').textContent=text,
 onExport:result=>{window.exported=result}
});
</script></body></html>"""


def mount_host(page, p, eid):
    """Second host: direct library bridge, no runner, dashboard HTML, token, or HTTP API."""

    def bridge(kind, data):
        if kind == "surface":
            return p.review_surface(eid, **data)
        if kind == "action":
            return p.review_action(eid, **data)
        if kind == "artifact":
            return {"html": p.read_artifact(eid, data["revision_id"])}
        return {"thumbnail": p.get_revision(eid, data["revision_id"]).get("thumbnail")}

    page.expose_function("bridge", bridge)
    bundle = Path(__file__).parents[1] / "src" / "possibly" / "static" / "review.js"
    page.route(
        "https://embedded.test/**",
        lambda route: route.fulfill(
            body=bundle.read_text() if route.request.url.endswith("/review.js") else HOST,
            content_type="text/javascript" if route.request.url.endswith("/review.js") else "text/html",
        ),
    )
    page.goto("https://embedded.test/")


def test_embedded_host_preserves_preview_and_draft_and_exports_exact_revision(tmp_path):
    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    eid, rid = started(p)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        mount_host(page, p, eid)
        page.get_by_role("button", name="Choose this direction").first.click()
        page.get_by_label("Refinement feedback").fill("Keep my draft")
        expect(page.locator("#saved")).to_have_text("Draft saved")
        expect(page.locator("iframe")).to_have_count(1)
        frame = page.frames[-1]
        frame.get_by_role("button", name="Claim shift").click()
        p.record_decision(eid, rid, action="feedback", text="External decision", request_id="external")
        page.evaluate("review.refresh()")
        expect(page.get_by_label("Refinement feedback")).to_have_value("Keep my draft")
        expect(frame.get_by_role("button", name="Claimed")).to_be_visible()
        assert frame.evaluate("innerWidth") == 1280
        page.get_by_role("button", name="Focus prototype").click()
        expect(page.get_by_role("button", name="Show refinement panel")).to_be_visible()
        expect(frame.get_by_role("button", name="Claimed")).to_be_visible()
        page.get_by_role("button", name="Show refinement panel").click()
        page.get_by_role("button", name="Send feedback", exact=True).click()
        expect(page.get_by_label("Refinement feedback")).to_have_value("")
        assert any(d.get("text") == "Keep my draft" for d in p.review_snapshot(eid)["decisions"])
        # An external authorized refinement follows the same branch, without changing old revisions.
        result = p.refine(
            eid, rid, "Preserve claiming", request_id="refine", grant=Grant(actions=("refine",))
        )
        newer = result["operation"]["result"]["revision_ids"][0]
        page.evaluate("review.refresh()")
        page.get_by_text("Export this version", exact=True).click()
        page.get_by_role("button", name="Download HTML").click()
        page.wait_for_function("window.exported")
        assert page.evaluate("exported.revisionId") == newer
        assert page.evaluate("exported.body") == p.read_artifact(eid, newer)
        page.get_by_label("Version history").select_option(rid)
        expect(page.get_by_text("Earlier version", exact=True)).to_be_visible()
        page.get_by_label("Refinement feedback").fill("Feedback on the original")
        page.get_by_role("button", name="Send feedback", exact=True).click()
        expect(page.get_by_label("Refinement feedback")).to_have_value("")
        assert p.review_snapshot(eid)["decisions"][-1]["revision_id"] == rid
        # A stale form must keep the unsent text, show rejection, and refresh before retry.
        page.get_by_label("Refinement feedback").fill("A stale form draft")
        p.record_decision(
            eid, newer, action="feedback", text="Another reviewer acted", request_id="concurrent"
        )
        before = len(p.review_snapshot(eid)["decisions"])
        page.get_by_role("button", name="Send feedback", exact=True).click()
        expect(page.locator("#status")).to_contain_text("Not accepted")
        expect(page.get_by_label("Refinement feedback")).to_have_value("A stale form draft")
        assert len(p.review_snapshot(eid)["decisions"]) == before
        page.get_by_role("button", name="Send feedback", exact=True).click()
        expect(page.get_by_label("Refinement feedback")).to_have_value("")
        assert len(p.review_snapshot(eid)["decisions"]) == before + 1
        # A view change during an existing poll waits for the new projection before saving context.
        page.evaluate("window.delaySurface=150; void review.refresh()")
        page.get_by_role("tab", name="Compare concepts", exact=True).click()
        expect(page.locator(".card")).to_have_count(2)
        page.wait_for_function("document.querySelector('#saved').textContent==='Draft saved'")
        # Flush any pending view save through a second explicit observation.
        page.evaluate("review.refresh()")
        review = p.review_snapshot(eid)["reviews"]["embedded-reviewer"]
        assert review["view_id"] == "compare" and review["revision_id"] is None
        # Disposal unmounts the UI; it does not stop or erase the exploration.
        page.evaluate("review.dispose()")
        assert page.locator("iframe").count() == 0
        assert p.get_exploration(eid)["lifecycle"] == "active"
        assert not errors
        browser.close()


def test_question_answer_and_brief_correction_in_embedded_host(tmp_path):
    p = Possibly(
        tmp_path,
        intelligence=FakeIntelligence(
            [{"question": {"prompt": "Who claims shifts?", "why_needed": "Task ownership"}}, design()]
        ),
    )
    result = p.start("Garden", request_id="start", grant=Grant())
    eid = result["receipt"]["exploration_id"]
    validate_surface(p.review_surface(eid))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        mount_host(page, p, eid)
        page.get_by_label("Who claims shifts?").fill("Volunteers")
        page.get_by_role("button", name="Answer", exact=True).click()
        page.get_by_role("button", name="Choose this direction").first.click()
        page.get_by_label("Refinement feedback").fill("Individual gardens, not a shared garden")
        page.get_by_role("button", name="Correct brief").click()
        expect(page.get_by_label("Refinement feedback")).to_have_value("")
        assert all(r["superseded"] for r in p.get_exploration(eid)["revisions"].values())
        assert len(p.intelligence.calls) == 2
        browser.close()


def test_large_preview_uses_full_dialog_width_from_concepts_and_history(tmp_path):
    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    eid, rid = started(p)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        mount_host(page, p, eid)

        def check_large_preview(invoker):
            dialog = page.get_by_role("dialog", name="Interactive concept preview")
            expect(dialog).to_be_visible()
            expect(dialog.locator("iframe")).to_have_count(1)
            expect(dialog.get_by_role("button", name="Open large preview")).to_have_count(0)
            stage = dialog.locator(".preview-stage")
            expect(stage).to_be_visible()
            assert stage.bounding_box()["width"] >= dialog.bounding_box()["width"] - 44
            dialog.get_by_role("button", name="Back to concepts").press("Escape")
            expect(dialog).to_have_count(0)
            expect(invoker).to_be_focused()

        page.get_by_role("button", name="Open preview", exact=True).first.click()
        check_large_preview(page.get_by_role("button", name="Open preview", exact=True).first)
        page.get_by_role("button", name="Choose this direction").first.click()
        page.get_by_role("button", name="Open large preview", exact=True).click()
        check_large_preview(page.get_by_role("button", name="Open large preview", exact=True))
        p.refine(eid, rid, "Keep claiming", request_id="refine", grant=Grant(actions=("refine",)))
        page.evaluate("review.refresh()")
        page.get_by_label("Version history").select_option(rid)
        expect(page.get_by_text("Earlier version", exact=True)).to_be_visible()
        page.get_by_role("button", name="Open large preview", exact=True).click()
        check_large_preview(page.get_by_role("button", name="Open large preview", exact=True))
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name="Open large preview", exact=True).click()
        check_large_preview(page.get_by_role("button", name="Open large preview", exact=True))
        browser.close()


def test_comparison_profile_keeps_distinctions_and_discussion_local(tmp_path):
    p = Possibly(tmp_path, intelligence=FakeIntelligence())
    eid, rid = started(p)
    result = p.review_surface(eid, profile="comparison")
    nodes = result["messages"][2]["updateComponents"]["components"]
    by_id = {c["id"]: c for c in nodes}
    assert "overall" not in by_id["root"]["children"]
    assert by_id[rid + "-tradeoff"]["text"].startswith("Tradeoff")
    assert by_id[rid + "-discuss"]["action"]["event"]["context"]["revision_id"] == rid
    assert not p.review_snapshot(eid)["decisions"]
    with pytest.raises(PossiblyError):
        p.review_surface(eid, profile="unknown")
