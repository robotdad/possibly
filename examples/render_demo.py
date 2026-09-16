"""Render saved HTML with the same offline browser used by the intelligence tools."""

import asyncio
import base64
import sys
from pathlib import Path

from possibly.artifacts import inspect_html

for filename in sys.argv[1:]:
    source = Path(filename)
    result = asyncio.run(inspect_html(source.read_text()))
    target = source.with_suffix(".png")
    target.write_bytes(base64.b64decode(result["screenshot_base64"]))
    print(target, "errors:", result["errors"], "blocked:", result["blocked_requests"])
