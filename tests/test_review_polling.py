"""Slow and suspended MCP review reads must not queue another polling storm."""

import asyncio

import pytest

pytest.importorskip("mcp")
from mcp import Client
from playwright.async_api import async_playwright, expect
from test_contracts import FakeIntelligence, started
from test_mcp_browser import mount

from possibly import Possibly
from possibly.mcp import create_server


class DelayedRead:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == self.name and not self.entered.is_set():
            self.entered.set()
            await self.release.wait()
        return await self.client.call_tool(name, arguments)


def test_slow_progress_is_single_flight_terminal_reads_are_reused_and_hidden_view_keeps_draft(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        eid, _ = started(library)
        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            delayed = DelayedRead(client, "possibly_operation_diagnostics")
            frame, _ = await mount(page, delayed, eid)
            await asyncio.wait_for(delayed.entered.wait(), 5)
            # More than two old progress intervals elapse with the first read pending.
            await asyncio.sleep(4.2)
            assert delayed.calls.count("possibly_get_exploration") == 1
            assert delayed.calls.count("possibly_operation_diagnostics") == 1
            delayed.release.set()
            child = page.frames[1]
            await child.wait_for_function("!polling")
            for _ in range(3):
                await child.evaluate("pollRefresh()")
            assert delayed.calls.count("possibly_get_exploration") == 4
            assert delayed.calls.count("possibly_operation_diagnostics") == 1

            await frame.get_by_text("Feedback on this concept", exact=True).first.click()
            await frame.get_by_label("Concept feedback").first.fill("Keep this unsubmitted feedback")
            await expect(frame.get_by_text("Draft saved", exact=True)).to_be_visible()
            await page.evaluate("sendPossiblyHostContext({'com.microsoft.amplifier/visibility':false})")
            await child.wait_for_function("!PossiblyDashboardAdapter.isVisible()")
            before = list(delayed.calls)
            for _ in range(3):
                await child.evaluate("pollRefresh()")
            assert delayed.calls == before
            await expect(frame.get_by_label("Concept feedback").first).to_have_value(
                "Keep this unsubmitted feedback"
            )
            await page.evaluate("sendPossiblyHostContext({'com.microsoft.amplifier/visibility':true})")
            await child.wait_for_function("PossiblyDashboardAdapter.isVisible() && !polling")
            assert delayed.calls.count("possibly_get_exploration") == 5
            assert delayed.calls.count("possibly_operation_diagnostics") == 1
            assert not library.review_snapshot(eid)["decisions"]
            assert len(library.intelligence.calls) == 1
            await browser.close()

    asyncio.run(run())


def test_teardown_during_state_read_never_reschedules_or_applies_late_state(tmp_path):
    async def run():
        library = Possibly(tmp_path, intelligence=FakeIntelligence(), caller="mcp")
        eid, _ = started(library)
        async with Client(create_server(library)) as client, async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            delayed = DelayedRead(client, "possibly_get_exploration")
            await mount(page, delayed, eid)
            await asyncio.wait_for(delayed.entered.wait(), 5)
            child = page.frames[1]
            await child.evaluate("PossiblyDashboardTeardown()")
            delayed.release.set()
            await child.wait_for_function("!polling")
            await child.evaluate("resumePolling(); pollRefresh()")
            await asyncio.sleep(2.2)
            assert delayed.calls.count("possibly_get_exploration") == 1
            assert delayed.calls.count("possibly_operation_diagnostics") == 0
            assert await child.evaluate("state === undefined")
            assert len(library.intelligence.calls) == 1
            await browser.close()

    asyncio.run(run())
