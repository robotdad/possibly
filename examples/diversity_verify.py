"""Offline QA/export of retained trial artifacts; no generation or provider access."""

import asyncio
import base64
import json
import time
from pathlib import Path

from possibly import Possibly
from possibly.artifacts import inspect_html
from possibly.checkpoints import digest


async def main():
    for name in ("repairs", "pinball"):
        root = Path(__file__).parent / "generated" / "diversity" / "round3" / name
        p = Possibly(root)
        eid = json.loads((root / "start.json").read_text())["receipt"]["exploration_id"]
        operation = p.get_operation(
            eid, json.loads((root / "refine.json").read_text())["receipt"]["operation_id"]
        )
        assert operation["state"] == "succeeded", operation["state"]
        rid = operation["result"]["revision_ids"][0]
        r = p.get_revision(eid, rid)
        start = time.perf_counter()
        receipt = p.export(eid, rid, request_id="export-" + rid)["receipt"]
        elapsed = time.perf_counter() - start
        out = root / "export"
        out.mkdir(exist_ok=True)
        (out / "prototype.html").write_text(receipt["html"])
        (out / "handoff.json").write_text(json.dumps(receipt["handoff"], indent=2))
        assert digest(receipt["html"]) == r["review"]["artifact_hash"]
        rows = []
        for theme in ("light", "dark"):
            for width, height in ((1280, 900), (390, 844)):
                for index, flow in enumerate(r["review"]["verified_interactions"]):
                    review = await inspect_html(
                        receipt["html"],
                        flow["steps"],
                        viewport={"width": width, "height": height},
                        color_scheme=theme,
                    )
                    (out / f"{theme}-{width}-{index}.png").write_bytes(
                        base64.b64decode(review["thumbnail_base64"])
                    )
                    row = {
                        k: review[k]
                        for k in (
                            "errors",
                            "blocked_requests",
                            "assertions_passed",
                            "horizontal_overflow",
                            "viewport",
                            "color_scheme",
                        )
                    }
                    rows.append(row)
                    assert (
                        not row["errors"] and not row["blocked_requests"] and not row["horizontal_overflow"]
                    ), row
        result = {
            "revision_id": rid,
            "export_seconds": elapsed,
            "sha256": digest(receipt["html"]),
            "checks": rows,
        }
        (out / "verification.json").write_text(json.dumps(result, indent=2))
        print(name, json.dumps(result))


asyncio.run(main())
