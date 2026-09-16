"""Standalone HTML checks and network-denied browser inspection, shared by agent tools and publication."""

import base64
import re
from html.parser import HTMLParser

from .models import PossiblyError

CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; media-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []
        self.styles = []
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "style":
            self.in_style = True
        if attrs.get("style"):
            self.styles.append(attrs["style"])
        if tag in {"iframe", "object", "embed", "base"}:
            self.errors.append(f"Unsupported embedded/control element: {tag}")
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
            self.errors.append("Automatic navigation is not allowed.")
        for key in ("src", "href", "action", "poster", "srcset"):
            value = attrs.get(key, "").strip()
            if value and not value.startswith(("data:", "#")):
                self.errors.append(f"{tag}.{key} must be embedded data or a local fragment: {value[:100]}")

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.styles.append(data)


def validate_html(html):
    if not isinstance(html, str) or len(html.encode()) > 8_000_000:
        raise PossiblyError("invalid_artifact", "HTML must be text smaller than 8 MB.")
    errors = []
    if not re.search(r"<html[\s>]", html, re.I) or not re.search(r"<body[\s>]", html, re.I):
        errors.append("Provide a complete HTML document with html and body elements.")
    parser = AssetParser()
    parser.feed(html)
    errors.extend(parser.errors)
    css = "\n".join(parser.styles)
    for url in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", css, re.I):
        if not url.startswith(("data:", "#")):
            errors.append(f"External CSS resource: {url[:100]}")
    if re.search(r"@import\b", css, re.I):
        errors.append("CSS imports are not self-contained.")
    if errors:
        raise PossiblyError(
            "invalid_artifact",
            "HTML is not self-contained.",
            "Embed assets and remove navigation.",
            issues=errors,
        )
    return {"standalone": True, "bytes": len(html.encode())}


def isolate_html(html):
    validate_html(html)
    # Strip only our own policy before reinserting it; unchanged writes stay byte-stable.
    meta = '<meta http-equiv="Content-Security-Policy" content="' + CSP + '">'
    html = html.replace(meta, "")
    # First policy wins in conjunction with any additional policies. Generated code never receives credentials.
    meta = '<meta http-equiv="Content-Security-Policy" content="' + CSP + '">'
    if re.search(r"<head[^>]*>", html, re.I):
        return re.sub(r"(<head[^>]*>)", lambda m: m[0] + meta, html, count=1, flags=re.I)
    return re.sub(r"(<html[^>]*>)", lambda m: m[0] + "<head>" + meta + "</head>", html, count=1, flags=re.I)


async def inspect_html(html, steps=(), *, browser=None, viewport=None, color_scheme="light"):
    """Run Chromium offline. Steps: {action: click|fill|select|assert_*, selector, value?}; selectors target the mockup only."""
    validate_html(html)
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise PossiblyError(
            "browser_unavailable",
            "Playwright is not installed.",
            "Install Possibly and run: playwright install chromium",
        ) from exc
    if browser is None:
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch()
            except Exception as exc:
                raise PossiblyError(
                    "browser_unavailable", "Chromium could not launch.", "Run: playwright install chromium"
                ) from exc
            try:
                return await inspect_html(
                    html, steps, browser=browser, viewport=viewport, color_scheme=color_scheme
                )
            finally:
                await browser.close()
    context = await browser.new_context(
        offline=True, viewport=viewport or {"width": 1280, "height": 900}, color_scheme=color_scheme
    )
    try:
        await context.route("**/*", lambda route: route.abort())
        page = await context.new_page()
        errors, blocked = [], []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("requestfailed", lambda req: blocked.append(req.url))
        await page.set_content(isolate_html(html), wait_until="load", timeout=15000)
        thumbnail = await page.screenshot(full_page=False)
        assertions = 0
        from playwright.async_api import expect

        for step in steps:
            target = page.locator(step.get("selector", "body"))
            action = step.get("action")
            if action == "click":
                await target.click(timeout=3000)
            elif action == "fill":
                await target.fill(step.get("value", ""), timeout=3000)
            elif action == "select":
                await target.select_option(value=step["value"], timeout=3000)
            elif action == "assert_text":
                await expect(target).to_be_visible(timeout=3000)
                await expect(target).to_contain_text(step["value"], timeout=3000)
                assertions += 1
            elif action == "assert_value":
                await expect(target).to_be_visible(timeout=3000)
                await expect(target).to_have_value(step["value"], timeout=3000)
                assertions += 1
            elif action == "assert_visible":
                await expect(target).to_be_visible(timeout=3000)
                assertions += 1
            else:
                raise PossiblyError(
                    "invalid_step", "Use click, fill, select, assert_text, assert_value or assert_visible."
                )
        # Bound encoded visual context without changing the reviewed viewport or HTML.
        for quality in (75, 55, 35):
            screenshot = await page.screenshot(full_page=False, type="jpeg", quality=quality)
            if len(screenshot) <= 64_000:
                break
        broken_images = await page.locator("img").evaluate_all(
            "nodes => nodes.filter(n => n.getBoundingClientRect().width && n.getBoundingClientRect().height && (!n.complete || n.naturalWidth === 0)).map(n => n.alt || 'unnamed image')"
        )
        errors.extend("Image did not decode: " + name for name in broken_images)
        return {
            "errors": errors,
            "blocked_requests": blocked,
            "text": (await page.locator("body").inner_text())[:16000],
            "screenshot_base64": base64.b64encode(screenshot).decode(),
            "screenshot_media_type": "image/jpeg",
            "thumbnail_base64": base64.b64encode(thumbnail).decode(),
            "steps_run": list(steps),
            "assertions_passed": assertions,
            "horizontal_overflow": await page.evaluate(
                "document.documentElement.scrollWidth > innerWidth + 1"
            ),
            "viewport": viewport or {"width": 1280, "height": 900},
            "color_scheme": color_scheme,
            "network": "disabled",
        }
    finally:
        await context.close()
