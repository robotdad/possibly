"""Versioned artifact evidence and small, atomic recovery checkpoints. No provider access."""

import copy
import hashlib
import json
import os
import time
from pathlib import Path

from .models import PossiblyError


def digest(html):
    return hashlib.sha256(html.encode()).hexdigest()


def save_checkpoint(root, data):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / "checkpoint.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False))
    temp.chmod(0o600)
    with temp.open("rb") as handle:
        os.fsync(handle.fileno())
    temp.replace(target)


def read_checkpoint(root):
    path = Path(root) / "checkpoint.json"
    if not path.exists():
        raise PossiblyError(
            "checkpoint_missing", "No retained validation checkpoint exists for this operation."
        )
    return json.loads(path.read_text())


def validated_output(checkpoint, kind):
    """Publish only exact bytes with submitted metadata and current review evidence."""
    result = copy.deepcopy(checkpoint.get("result"))
    if not result or "question" in result:
        raise PossiblyError("checkpoint_incomplete", "No completed artifact submission is retained.")
    missing = []
    for direction in result.get("directions", []):
        name = direction.get("candidate")
        html = checkpoint.get("candidates", {}).get(name)
        review = checkpoint.get("reviews", {}).get(name, {})
        version = digest(html) if html is not None else None
        if (
            version is None
            or review.get("artifact_hash") != version
            or review.get("errors")
            or review.get("blocked_requests")
        ):
            missing.append(f"{name}: passing browser inspection for current artifact")
        if checkpoint.get("visual_seen", {}).get(name) != version or version is None:
            missing.append(f"{name}: model visual review of current artifact")
        if kind != "explore":
            checks = review.get("verified_interactions", [])
            if not any(
                c.get("assertions_passed", 0)
                and any(s.get("action") in {"click", "fill", "select"} for s in c.get("steps", []))
                for c in checks
            ):
                missing.append(f"{name}: interaction with a verified visible outcome")
            required = checkpoint.get("required_flows", [])
            for flow in required:
                if not any(c.get("steps") == flow and c.get("assertions_passed", 0) for c in checks):
                    missing.append(f"{name}: inherited central-flow regression check")
        direction["html"] = html
        direction["review"] = {
            k: v for k, v in review.items() if k not in {"screenshot_base64", "thumbnail_base64"}
        }
    if not result.get("directions"):
        missing.append("structured directions")
    if missing:
        raise PossiblyError(
            "checkpoint_incomplete",
            "Validation checkpoint is not ready for publication.",
            "Run the missing checks or explicitly request a repair; finalization never calls a model.",
            missing=missing,
        )
    return result


class Diagnostics:
    def __init__(self, root):
        self.root = Path(root)
        self.data = {
            "started_at": time.time(),
            "stages": [],
            "provider_calls": [],
            "usage": {},
            "status": "running",
        }
        self.flush()

    def flush(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = self.root / "diagnostics.tmp"
        temp.write_text(json.dumps(self.data))
        temp.chmod(0o600)
        temp.replace(self.root / "diagnostics.json")

    def stage(self, name, started, **details):
        self.data["stages"].append(
            {"stage": name, "seconds": round(time.monotonic() - started, 4), **details}
        )
        self.flush()
