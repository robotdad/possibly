import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_contracts import FakeIntelligence, design

from possibly import Grant, Possibly, PossiblyError
from possibly.fanout import LENSES, generate, plan_exploration


def plan():
    return plan_exploration(
        [{"provider": "openai", "lens": LENSES[0]}, {"provider": "gemini", "lens": LENSES[1]}]
    )


def test_plan_rejects_cosmetic_duplicates_and_bad_limits():
    with pytest.raises(PossiblyError):
        plan_exploration([{"provider": "openai", "lens": LENSES[0]}] * 2)
    with pytest.raises(PossiblyError):
        plan_exploration(concurrency=4)
    assert plan()["candidates"][1]["provider"] == "gemini"
    assert plan_exploration(**plan()) == plan()


def test_streamed_candidates_survive_later_worker_failure(tmp_path):
    class Streaming(FakeIntelligence):
        def generate(self, request, workspace, grant, cancelled, on_candidate):
            output = design(1)
            on_candidate(output)
            output.update(
                fanout={"candidates": [{"status": "succeeded"}, {"status": "failed"}]}, partial=True
            )
            return output

    p = Possibly(tmp_path, intelligence=Streaming())
    result = p.start(
        "Repairs",
        request_id="start",
        grant=Grant(),
        exploration_plan={"candidates": [{"provider": "openai"}, {"provider": "gemini"}]},
    )
    eid = result["receipt"]["exploration_id"]
    state = p.get_exploration(eid)
    assert len(state["revisions"]) == 1
    assert result["operation"]["state"] == "succeeded"
    assert result["operation"]["result"]["partial"]
    assert sum(e["kind"] == "candidate_ready" for e in p.store.get(eid)["events"]) == 1
    replay = p.start(
        "Repairs",
        request_id="start",
        grant=Grant(),
        exploration_plan={"candidates": [{"provider": "openai"}, {"provider": "gemini"}]},
    )
    assert replay["status"] == "replayed"


def test_process_batch_divides_budget_and_keeps_success(tmp_path, monkeypatch):
    spawned = []

    def popen(argv, **kwargs):
        root = Path(argv[-1])
        data = json.loads((root / "input.json").read_text())
        spawned.append(data)
        output = design(1)
        output["directions"][0]["provenance"] = {"provider": data["config"]["provider"]}
        if len(spawned) == 2:
            output = {"error": {"code": "unavailable", "message": "No access"}}
        (root / "result.json").write_text(json.dumps(output))
        return SimpleNamespace(poll=lambda: 0)

    monkeypatch.setattr("possibly.fanout.subprocess.Popen", popen)
    ready = []
    result = generate(
        {"context": "Repairs", "exploration_plan": plan()},
        tmp_path,
        Grant().to_dict(),
        lambda: False,
        ready.append,
    )
    assert result["partial"] and len(ready) == 1
    assert sum(x["grant"]["max_model_calls"] for x in spawned) <= 12
    assert sum(x["grant"]["max_tool_calls"] for x in spawned) <= 20
    assert all(x["request"]["shared_brief"] == spawned[0]["request"]["shared_brief"] for x in spawned)


def test_css_validation_does_not_misread_javascript():
    from possibly.artifacts import validate_html

    validate_html(
        "<html><body><script>URL.createObjectURL(blob);URL.revokeObjectURL(a.href)</script></body></html>"
    )
    with pytest.raises(PossiblyError):
        validate_html('<html><body style="background:url(https://example.test/image.png)"></body></html>')


def test_visible_broken_embedded_image_is_reported():
    import asyncio

    from possibly.artifacts import inspect_html

    result = asyncio.run(
        inspect_html(
            '<html><body><img width="80" height="80" alt="Broken cabinet" src="data:image/png;base64,AAAA"></body></html>'
        )
    )
    assert any("Broken cabinet" in e for e in result["errors"])


def test_cancellation_terminates_workers_and_retains_status(tmp_path, monkeypatch):
    spawned, stopped = [], []

    def popen(*args, **kwargs):
        process = SimpleNamespace(poll=lambda: None)
        spawned.append(process)
        return process

    monkeypatch.setattr("possibly.fanout.subprocess.Popen", popen)
    monkeypatch.setattr("possibly.fanout.terminate", stopped.append)
    with pytest.raises(PossiblyError, match="stopped"):
        generate(
            {"context": "Repairs", "exploration_plan": plan()},
            tmp_path,
            Grant().to_dict(),
            lambda: bool(spawned),
            None,
        )
    assert stopped == spawned and len(stopped) == 2
    diagnostics = json.loads((tmp_path / "diagnostics.json").read_text())
    assert all(c["status"] == "cancelled" for c in diagnostics["candidates"])


def test_fanout_does_not_require_default_provider_key(tmp_path, monkeypatch):
    from possibly.intelligence import AmplifierIntelligence

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = Possibly(tmp_path, intelligence=AmplifierIntelligence(allow_environment=True))
    p._preflight(plan())


def test_single_worker_requires_task_model(tmp_path):
    from possibly.intelligence import CandidateTools

    tool = CandidateTools(tmp_path, 8, request={"kind": "explore", "single_candidate": {"id": "one"}})
    with pytest.raises(PossiblyError, match="task_model"):
        tool.submit(design(1))


def test_refinement_uses_origin_unless_explicit_override(monkeypatch):
    from possibly.intelligence import AmplifierIntelligence

    for key in ("POSSIBLY_PROVIDER", "POSSIBLY_MODEL", "POSSIBLY_REASONING_EFFORT"):
        monkeypatch.delenv(key, raising=False)
    origin = {"provenance": {"provider": "gemini", "model": "example-model"}}
    default = AmplifierIntelligence(allow_environment=True)
    inherited = default.for_revision(origin)
    assert inherited.configuration().provider == "gemini"
    assert inherited.configuration().model == "example-model"
    explicit = AmplifierIntelligence(provider="openai", allow_environment=True)
    assert explicit.for_revision(origin) is explicit


def test_streamed_candidates_stay_stale_after_brief_change(tmp_path):
    class Streaming(FakeIntelligence):
        def generate(self, request, workspace, grant, cancelled, on_candidate):
            on_candidate(design(1))
            with p.store.transaction() as db:
                eid = db.execute("SELECT id FROM explorations").fetchone()[0]
                state = p.store.get(eid, db)
                state["design_epoch"] += 1  # A separately accepted change of intent.
                p.store.put(db, state)
            on_candidate(design(1))
            on_candidate(design(1))
            output = design(3)
            output.update(fanout={"candidates": []}, partial=False)
            return output

    p = Possibly(tmp_path, intelligence=Streaming())
    result = p.start(
        "Repairs",
        request_id="start",
        grant=Grant(),
        exploration_plan={
            "candidates": [{"provider": "openai"}, {"provider": "gemini"}, {"provider": "anthropic"}]
        },
    )
    revisions = list(p.get_exploration(result["receipt"]["exploration_id"])["revisions"].values())
    assert [r["superseded"] for r in revisions] == [False, True, True]


def test_owned_runner_preserves_implicit_provider_choice(monkeypatch):
    from possibly.intelligence import AmplifierIntelligence
    from possibly.runner import runner_environment

    monkeypatch.delenv("POSSIBLY_PROVIDER", raising=False)
    assert "POSSIBLY_PROVIDER" not in runner_environment(AmplifierIntelligence(allow_environment=True))
    assert (
        runner_environment(AmplifierIntelligence(provider="gemini", model="model-x", allow_environment=True))[
            "POSSIBLY_PROVIDER"
        ]
        == "gemini"
    )
    monkeypatch.setenv("POSSIBLY_PROVIDER", "anthropic")
    assert (
        runner_environment(AmplifierIntelligence(allow_environment=True))["POSSIBLY_PROVIDER"] == "anthropic"
    )
