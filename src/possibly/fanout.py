"""Bounded process-isolated concept exploration; no engine state is shared between workers."""

import copy
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .checkpoints import Diagnostics
from .models import PossiblyError
from .providers import ProviderConfig, catalog, credential_status

LENSES = [
    {
        "id": "triage",
        "question": "What deserves my attention next?",
        "instruction": "Organize around situations, urgency and the next useful action. Make prioritization the central task, not a decorative dashboard over an inventory.",
    },
    {
        "id": "context",
        "question": "What belongs together, and what does its history tell me?",
        "instruction": "Organize around places, objects or relationships and their history. Reveal context that changes the next decision; do not merely rearrange the same to-do list.",
    },
    {
        "id": "outcome",
        "question": "What am I trying to achieve, and what is the smallest useful step?",
        "instruction": "Organize around goals, progress and constrained plans. Help users choose a next step under time, cost or opportunity constraints rather than just record items.",
    },
]


def plan_exploration(candidates=None, concurrency=3):
    """Resolve a 2–3 candidate task-diverse plan, without model calls. Credentials are never returned.

    Candidate fields: provider, optional model/reasoning_effort, lens (id/question/instruction).
    Automatic choice uses up to three configured providers; one provider may supply multiple lenses.
    Copilot callers can supply distinct discovered model IDs explicitly.
    """
    if type(concurrency) is not int or not 1 <= concurrency <= 3:
        raise PossiblyError("invalid_plan", "Concurrency must be 1–3.")
    if candidates is None:
        configured = [p for p in catalog() if credential_status(p)["configured"]]
        preferred = [p for p in ("openai", "gemini", "anthropic") if p in configured]
        preferred += [p for p in configured if p not in preferred]
        if not preferred:
            raise PossiblyError("provider_unavailable", "No configured providers for diverse exploration.")
        candidates = [
            {"provider": preferred[i % len(preferred)], "lens": lens} for i, lens in enumerate(LENSES)
        ]
    if not isinstance(candidates, list) or not 2 <= len(candidates) <= 3:
        raise PossiblyError("invalid_plan", "Supply 2–3 candidates.")
    rows = []
    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or set(candidate) - {
            "id",
            "provider",
            "model",
            "reasoning_effort",
            "lens",
        }:
            raise PossiblyError("invalid_plan", "Unknown candidate fields.")
        config = ProviderConfig.resolve(
            candidate.get("provider"),
            candidate.get("model") or "",
            candidate.get("reasoning_effort") or "",
            {},
        )
        lens = candidate.get("lens", LENSES[i])
        if not isinstance(lens, dict) or not all(
            isinstance(lens.get(k), str) and lens[k].strip() for k in ("id", "question", "instruction")
        ):
            raise PossiblyError("invalid_plan", "Each lens needs id, question and instruction.")
        rows.append(
            {
                "id": f"concept-{i + 1}",
                "provider": config.provider,
                "model": config.model or None,
                "reasoning_effort": config.effort or None,
                "lens": copy.deepcopy(lens),
            }
        )
    if len({r["lens"]["id"] for r in rows}) != len(rows):
        raise PossiblyError("invalid_plan", "Use distinct task lenses; cosmetic variation is not enough.")
    return {"candidates": rows, "concurrency": concurrency}


def terminate(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        except ProcessLookupError:
            pass


def generate(request, workspace, grant, cancelled, on_candidate):
    plan = request["exploration_plan"]
    rows = plan["candidates"]
    count = len(rows)
    if grant["max_model_calls"] < count * 2 or grant["max_tool_calls"] < count * 3:
        raise PossiblyError(
            "invalid_grant",
            "Fan-out needs at least two model calls and three tool calls per candidate in the total grant.",
        )
    workspace = Path(workspace)
    diagnostics = Diagnostics(workspace)
    diagnostics.data.update(
        kind="fanout", candidates=[], max_concurrency=plan["concurrency"], budget_scope="whole batch"
    )
    pending, running, completed = list(rows), [], []
    start = time.monotonic()
    deadline = start + grant["timeout_seconds"]
    if grant.get("expires_at") is not None:
        deadline = min(deadline, start + max(0, grant["expires_at"] - time.time()))
    brief = {
        "intent": request["context"],
        "requirements": [],
        "assumptions": ["Task lenses are exploration hypotheses, not added requirements."],
        "open_choices": [r["lens"]["question"] for r in rows],
    }
    try:
        while pending or running:
            if cancelled():
                raise PossiblyError("cancelled", "Exploration stopped; completed candidates remain retained.")
            if time.monotonic() >= deadline:
                for item in running:
                    item["record"].update(status="timed_out")
                for row in pending:
                    diagnostics.data["candidates"].append({**row, "status": "not_started"})
                break
            while pending and len(running) < plan["concurrency"]:
                row = pending.pop(0)
                root = workspace / row["id"]
                root.mkdir(mode=0o700, exist_ok=True)
                child_request = {
                    **request,
                    "exploration_plan": None,
                    "single_candidate": row,
                    "shared_brief": brief,
                }
                child_grant = {
                    **grant,
                    "timeout_seconds": max(1, deadline - time.monotonic()),
                    "max_model_calls": grant["max_model_calls"] // count,
                    "max_tool_calls": grant["max_tool_calls"] // count,
                }
                input_path = root / "input.json"
                input_path.write_text(
                    json.dumps({"request": child_request, "grant": child_grant, "config": row})
                )
                input_path.chmod(0o600)
                log = (root / "worker.log").open("wb")
                env = {**os.environ, "POSSIBLY_PROVIDER_CONFIG": "{}"}
                process = subprocess.Popen(
                    [sys.executable, "-m", "possibly.fanout_worker", str(root)],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
                record = {**row, "status": "running", "started_at": time.time()}
                diagnostics.data["candidates"].append(record)
                running.append({"process": process, "root": root, "record": record, "log": log})
            for item in list(running):
                if item["process"].poll() is None:
                    continue
                root, record = item["root"], item["record"]
                try:
                    result = json.loads((root / "result.json").read_text())
                except (OSError, ValueError):
                    result = {
                        "error": {"code": "worker_failed", "message": "Worker exited without a result."}
                    }
                record.update(seconds=round(time.time() - record["started_at"], 3))
                if "error" in result:
                    record.update(status="failed", error=result["error"])
                else:
                    direction = result["directions"][0]
                    record.update(status="succeeded", provenance=direction["provenance"])
                    completed.append(direction)
                    if on_candidate:
                        on_candidate({"brief": brief, "directions": [direction]})
                item["log"].close()
                running.remove(item)
            diagnostics.flush()
            if running:
                time.sleep(0.1)
    finally:
        recorded = {c["id"] for c in diagnostics.data["candidates"]}
        for row in pending:
            if row["id"] not in recorded:
                diagnostics.data["candidates"].append({**row, "status": "not_started"})
        for item in running:
            terminate(item["process"])
            item["log"].close()
            if item["record"]["status"] == "running":
                item["record"]["status"] = "cancelled"
        diagnostics.data.update(
            status="completed" if len(completed) == count else "partial" if completed else "failed",
            seconds=round(time.monotonic() - start, 3),
        )
        diagnostics.flush()
    if not completed:
        raise PossiblyError(
            "exploration_failed",
            "No candidate completed within the shared grant.",
            "Inspect per-candidate diagnostics before retrying.",
        )
    return {
        "brief": brief,
        "directions": completed,
        "fanout": diagnostics.data,
        "partial": len(completed) < count,
    }
