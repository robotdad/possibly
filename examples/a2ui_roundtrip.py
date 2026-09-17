"""Opt-in live A2UI review trial. Uses an existing start.json and finite per-operation grants.

Run: uv run python examples/a2ui_roundtrip.py examples/generated/a2ui-live-roundtrip
The caller must explicitly authorize live generation. This script selects each provider's
concept, makes it interactive, submits UI feedback, refines, downloads, and stops the runner.
No credentials or authenticated viewer URLs are included in its public report.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from possibly import Grant, Possibly
from possibly.artifacts import inspect_html
from possibly.checkpoints import digest
from possibly.intelligence import AmplifierIntelligence


def run(root):
    p = Possibly(root, intelligence=AmplifierIntelligence(allow_environment=True), execution="owned_runner")
    eid = json.loads((root / "start.json").read_text())["receipt"]["exploration_id"]
    report = {"exploration_id": eid, "providers": [], "browser_errors": []}

    def save():
        (root / "roundtrip.json").write_text(json.dumps(report, indent=2))

    def wait(oid, seconds=420):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            op = p.wait_operation(eid, oid, timeout=15)["operation"]
            if op["state"] not in {"running", "queued"}:
                return op
        raise RuntimeError("Bounded trial observation deadline elapsed")

    def operation(result, row, stage):
        oid = result["receipt"]["operation_id"]
        op = wait(oid)
        row[stage] = {"id": oid, "state": op["state"], "failure": op.get("failure")}
        save()
        if op["state"] != "succeeded":
            raise RuntimeError(f"{stage}: {op['state']}")
        return op["result"]["revision_ids"][0]

    try:
        first = next(iter(p.get_exploration(eid)["operations"]))
        report["generation"] = wait(first).get("result")
        save()
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
            page.on("pageerror", lambda err: report["browser_errors"].append(str(err)))
            page.goto(p.get_exploration(eid)["runner"]["url"])
            page.get_by_role("button", name="Choose this direction").first.wait_for()
            originals = [r for r in p.get_exploration(eid)["revisions"].values() if not r["parent"]]
            if len(originals) >= 2:
                for i in range(2):
                    page.get_by_role("button", name="Mark for comparison", exact=True).first.click()
                    expect(
                        page.get_by_role("button", name="Remove from comparison", exact=True)
                    ).to_have_count(i + 1)
                page.get_by_role("button", name="Open side-by-side comparison").click()
                expect(page.locator("iframe")).to_have_count(2)
                page.screenshot(path=str(root / "comparison.png"), full_page=True)
                page.get_by_role("button", name="Back to concepts").click()
            for rev in originals:
                provider = rev["provenance"]["provider"]
                row = {"provider": provider, "initial_revision": rev["id"]}
                report["providers"].append(row)
                out = root / provider
                out.mkdir(exist_ok=True)
                try:
                    page.get_by_role("tab", name="Compare concepts", exact=True).click()
                    card = page.locator(".card").filter(
                        has=page.get_by_role("heading", name=rev["name"], exact=True)
                    )
                    card.get_by_role("button", name="Choose this direction").click()
                    page.get_by_label("Refinement feedback").wait_for()
                    assert p.review_snapshot(eid)["selected_revision"] == rev["id"]
                    rid = operation(
                        p.make_interactive(
                            eid,
                            rev["id"],
                            request_id="interactive-" + provider,
                            grant=Grant(
                                actions=("make_interactive",),
                                timeout_seconds=240,
                                max_model_calls=12,
                                max_tool_calls=24,
                            ),
                        ),
                        row,
                        "interactive",
                    )
                    page.reload()
                    page.get_by_label("Refinement feedback").wait_for()
                    feedback = (
                        "Preserve this task organization and every verified interaction. Add a clearly visible "
                        "'Demo only — changes stay in this prototype' label near the primary task. "
                        "Keep it readable in light and dark themes and on mobile. Use a small targeted patch; "
                        "do not rewrite the application. Verify the inherited flow still works."
                    )
                    page.get_by_label("Refinement feedback").fill(feedback)
                    page.get_by_role("button", name="Send feedback", exact=True).click()
                    expect(page.get_by_label("Refinement feedback")).to_have_value("")
                    assert p.review_snapshot(eid)["decisions"][-1]["revision_id"] == rid
                    final = operation(
                        p.refine(
                            eid,
                            rid,
                            feedback,
                            request_id="refine-" + provider,
                            grant=Grant(
                                actions=("refine",),
                                timeout_seconds=240,
                                max_model_calls=12,
                                max_tool_calls=24,
                            ),
                        ),
                        row,
                        "refine",
                    )
                    page.reload()
                    page.get_by_text("Export this version", exact=True).click()
                    for label, name in (
                        ("Download HTML", "prototype.html"),
                        ("Download handoff", "handoff.json"),
                    ):
                        with page.expect_download() as downloaded:
                            page.get_by_role("button", name=label, exact=True).click()
                        downloaded.value.save_as(out / name)
                    assert (out / "prototype.html").read_text() == p.read_artifact(eid, final)
                    row["final_revision"] = final
                    row["artifact_hash"] = digest((out / "prototype.html").read_text())
                    row["provenance"] = p.get_revision(eid, final)["provenance"]
                    for theme in ("light", "dark"):
                        page.emulate_media(color_scheme=theme)
                        page.screenshot(path=str(out / f"workspace-{theme}.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.screenshot(path=str(out / "workspace-mobile.png"), full_page=True)
                    row["workspace_overflow"] = page.evaluate(
                        "document.documentElement.scrollWidth > innerWidth + 1"
                    )
                    page.set_viewport_size({"width": 1440, "height": 1100})
                    row["status"] = "exported"
                    print(provider, "roundtrip exported", flush=True)
                except Exception as exc:
                    row["status"] = "failed"
                    row["error"] = str(exc).split("Call log:")[0]
                    print(provider, "roundtrip failed:", row["error"], flush=True)
                save()
            browser.close()
        for row in report["providers"]:
            if row["status"] != "exported":
                continue
            rev = p.get_revision(eid, row["final_revision"])
            checks = []
            for theme in ("light", "dark"):
                for width, height in ((1280, 900), (390, 844)):
                    for flow in rev["review"]["verified_interactions"]:
                        try:
                            result = asyncio.run(
                                inspect_html(
                                    p.read_artifact(eid, rev["id"]),
                                    flow["steps"],
                                    viewport={"width": width, "height": height},
                                    color_scheme=theme,
                                )
                            )
                            checks.append(
                                {
                                    k: result[k]
                                    for k in (
                                        "errors",
                                        "blocked_requests",
                                        "assertions_passed",
                                        "horizontal_overflow",
                                        "viewport",
                                        "color_scheme",
                                    )
                                }
                            )
                        except Exception as exc:
                            checks.append({"error": str(exc), "theme": theme, "width": width})
            row["offline_checks"] = checks
            save()
    finally:
        report["cleanup"] = p.stop(eid, request_id="trial-cleanup")["cleanup"]
        save()
    return report


if __name__ == "__main__":
    result = run(Path(sys.argv[1]).resolve())
    print(
        json.dumps(
            {
                "providers": [(p["provider"], p["status"]) for p in result["providers"]],
                "cleanup": result["cleanup"]["status"],
            }
        )
    )
