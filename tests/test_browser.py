import asyncio

import pytest

from possibly.artifacts import inspect_html, validate_html
from possibly.models import PossiblyError

HTML = '<!doctype html><html><head><title>Test</title></head><body><button id="claim" onclick="this.textContent=\'Claimed\'">Claim</button></body></html>'


def test_offline_clickthrough():
    result = asyncio.run(inspect_html(HTML, [{"action": "click", "selector": "#claim"}]))
    assert result["text"] == "Claimed"
    assert not result["errors"]
    assert result["screenshot_base64"]


@pytest.mark.parametrize(
    "bad",
    [
        '<img src="https://example.com/a.png">',
        '<iframe src="data:text/html,hi"></iframe>',
        '<style>@import "x";</style>',
    ],
)
def test_external_assets_rejected(bad):
    with pytest.raises(PossiblyError):
        validate_html(HTML.replace("</body>", bad + "</body>"))


def test_screenshot_review_preserves_interaction_evidence_until_edit(tmp_path, monkeypatch):
    from possibly.intelligence import CandidateTools

    async def inspect(html, steps):
        return {
            "errors": [],
            "blocked_requests": [],
            "text": "Claimed",
            "steps_run": list(steps),
            "screenshot_base64": "AA==",
            "network": "disabled",
        }

    monkeypatch.setattr("possibly.intelligence.inspect_html", inspect)
    tools = CandidateTools(tmp_path, 20)
    tools.write("candidate", HTML)
    asyncio.run(tools.inspect("candidate", [{"action": "click", "selector": "#claim"}]))
    review = asyncio.run(tools.inspect("candidate", []))
    assert review["steps_run"] == []
    assert review["verified_interactions"][0]["visible_result"] == "Claimed"
    tools.write("candidate", HTML.replace("Claim</button>", "Book</button>"))
    review = asyncio.run(tools.inspect("candidate", []))
    assert review["verified_interactions"] == []
