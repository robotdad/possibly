"""Capture the shipping comparison dialog from retained demo revisions, without model calls.

Usage: uv run python examples/capture_readme.py STORAGE EXPLORATION_ID OUTPUT.png
The retained artifacts must be fictional, approved for publication, and self-contained.
The browser replays read-only public-library results; it never writes to the source store.
"""

import argparse
import hashlib
from pathlib import Path

from playwright.sync_api import sync_playwright

from possibly import Possibly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storage", type=Path)
    parser.add_argument("exploration_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    library = Possibly(args.storage)
    state = library.get_exploration(args.exploration_id, max_embedded_bytes=1_000_000)
    state.pop("runner", None)
    roots = [revision for revision in state["revisions"].values() if not revision["parent"]]
    if len(roots) != 2:
        parser.error("Use a retained demo with exactly two initial concepts.")
    for revision in roots:
        revision["html"] = library.read_artifact(args.exploration_id, revision["id"])
        print(revision["name"], hashlib.sha256(revision["html"].encode()).hexdigest())
    dashboard = Path(__file__).parents[1] / "src/possibly/dashboard.html"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, device_scale_factor=2, color_scheme="light"
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def replay(route):
            path = route.request.url.removeprefix("http://localhost")
            if path == "/":
                route.fulfill(body=dashboard.read_text(), content_type="text/html")
            elif path == "/state":
                route.fulfill(json=state)
            elif path == "/progress":
                route.fulfill(json=[])
            elif path == "/review-state":
                # Navigation's view-state autosave is local to this capture.
                route.fulfill(json={})
            else:
                route.abort()

        page.route("**/*", replay)
        page.goto("http://localhost/")
        page.get_by_role("tab", name="Compare concepts", exact=True).click()
        for _ in roots:
            page.get_by_role("button", name="Mark for comparison", exact=True).first.click()
        page.get_by_role("button", name="Open side-by-side comparison").click()
        dialog = page.get_by_role("dialog", name="Interactive concept preview")
        for index in range(2):
            dialog.locator("iframe").nth(index).content_frame.locator("body").wait_for()
        page.evaluate("document.fonts.ready")
        for frame in page.frames[1:]:
            frame.evaluate("document.fonts.ready")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        dialog.screenshot(path=str(args.output), animations="disabled")
        assert not errors, errors
        print(f"Captured {args.output}")
        browser.close()


if __name__ == "__main__":
    main()
