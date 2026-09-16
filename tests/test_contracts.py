import copy
import json
import subprocess
import sys
import threading

import pytest

from possibly import Grant, Possibly, PossiblyError

HTML = '<!doctype html><html lang="en"><head><title>Garden</title></head><body><button onclick="this.textContent=\'Claimed\'">Claim shift</button></body></html>'


def design(count=2):
    return {
        "brief": {
            "intent": "Coordinate garden watering",
            "requirements": ["Claim shifts"],
            "assumptions": [],
            "open_choices": [],
        },
        "directions": [
            {
                "name": name,
                "approach": name,
                "tradeoff": "Choice versus coordination",
                "html": HTML,
                "invariants": ["People choose their shift"],
                "mocked": ["No server"],
                "assumptions": [],
            }
            for name in ["Calendar", "Availability"][:count]
        ],
    }


class FakeIntelligence:
    def __init__(self, outputs=None):
        self.outputs = list(outputs or [])
        self.calls = []

    def preflight(self):
        pass

    def generate(self, request, workspace, grant, cancelled):
        self.calls.append(copy.deepcopy(request))
        return self.outputs.pop(0) if self.outputs else design(2 if request["kind"] == "explore" else 1)


@pytest.fixture
def client(tmp_path):
    return Possibly(tmp_path / "store", intelligence=FakeIntelligence())


def started(p, continuation=False):
    receipt = p.start(
        "A garden watering app", request_id="start", grant=Grant(prototype_after_selection=continuation)
    )
    eid = receipt["receipt"]["exploration_id"]
    rid = receipt["operation"]["result"]["revision_ids"][0]
    return eid, rid


def test_complete_library_roundtrip_and_retention(client):
    eid, rid = started(client)
    client.record_decision(eid, rid, action="select", request_id="choose")
    prototype = client.make_interactive(
        eid, rid, grant=Grant(actions=("make_interactive",)), request_id="prototype"
    )
    r2 = prototype["operation"]["result"]["revision_ids"][0]
    refined = client.refine(
        eid,
        r2,
        "Simplify navigation; preserve claiming",
        grant=Grant(actions=("refine",)),
        request_id="refine",
    )
    r3 = refined["operation"]["result"]["revision_ids"][0]
    exported = client.export(eid, r3, request_id="export")
    assert exported["receipt"]["handoff"]["selected_experience"]["invariants"]
    assert client.get_exploration(eid)["lifecycle"] == "active"
    version = client.get_exploration(eid)["state_version"]
    assert (
        client.finish(eid, r3, request_id="finish", expected_state_version=version)["cleanup"]["status"]
        == "succeeded"
    )
    assert client.read_artifact(eid, rid)
    with pytest.raises(PossiblyError, match="closed"):
        client.record_decision(eid, rid, action="select", request_id="late")
    client.reopen(eid, r3, request_id="return")
    assert len(client.intelligence.calls) == 3
    assert client.get_revision(eid, r3)["parent"] == r2


def test_retry_and_one_use_continuation(client):
    eid, rid = started(client, continuation=True)
    first = client.record_decision(eid, rid, action="select", request_id="choose")
    replay = client.record_decision(eid, rid, action="select", request_id="choose")
    assert replay["status"] == "replayed"
    assert replay["receipt"] == first["receipt"]
    second = client.record_decision(eid, rid, action="select", request_id="choose-again")
    assert second["receipt"]["follow_up"] is None
    assert len(client.get_exploration(eid)["operations"]) == 2
    with pytest.raises(PossiblyError) as error:
        client.record_decision(eid, rid, action="reject", request_id="choose")
    assert error.value.code == "request_conflict"
    replay_start = client.start(
        "A garden watering app", request_id="start", grant=Grant(prototype_after_selection=True)
    )
    assert replay_start["status"] == "replayed"
    assert len(client.intelligence.calls) == 1


def test_question_answer_same_operation_and_conflict(tmp_path):
    intelligence = FakeIntelligence(
        [{"question": {"prompt": "Who claims shifts?", "why_needed": "Affects task flow"}}, design()]
    )
    p = Possibly(tmp_path, intelligence=intelligence)
    result = p.start("Garden", request_id="start", grant=Grant())
    eid, oid = result["receipt"]["exploration_id"], result["receipt"]["operation_id"]
    q = result["operation"]["questions"][0]
    answered = p.answer(eid, oid, q["id"], "Volunteers", request_id="answer")
    assert answered["operation"]["state"] == "succeeded"
    assert intelligence.calls[-1]["operation_id"] == oid
    assert p.answer(eid, oid, q["id"], "Volunteers", request_id="answer")["status"] == "replayed"
    with pytest.raises(PossiblyError) as error:
        p.answer(eid, oid, q["id"], "Staff", request_id="other")
    assert error.value.code == "question_conflict"


def test_provider_free_import_and_cli_help():
    code = 'import sys; from possibly.help import skill; print(skill()); assert "amplifier_agent_lib" not in sys.modules'
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0
    assert '<skill_content name="possibly">' in result.stdout
    cli = subprocess.run(
        [sys.executable, "-m", "possibly", "start", "--input", "-"], input="", capture_output=True, text=True
    )
    assert cli.returncode != 0
    assert json.loads(cli.stdout)["status"] == "rejected"


def test_snapshot_cursor_and_stale_submission(client):
    eid, rid = started(client)
    snapshot = client.get_exploration(eid)
    client.record_decision(eid, rid, action="select", request_id="one")
    changes = client.read_changes(eid, cursor=snapshot["cursor"])
    assert changes["events"][0]["kind"] == "decision_recorded"
    with pytest.raises(PossiblyError) as error:
        client.record_decision(
            eid, rid, action="reject", request_id="two", expected_state_version=snapshot["state_version"]
        )
    assert error.value.code == "state_conflict"


def test_correction_supersedes_and_feedback_keeps_target(client):
    eid, rid = started(client)
    client.record_decision(
        eid, rid, action="brief_correction", text="Only staff can assign shifts", request_id="correct"
    )
    assert all(r["superseded"] for r in client.get_exploration(eid)["revisions"].values())
    client.record_decision(eid, rid, action="feedback", text="Larger text", request_id="feedback")
    assert client.get_exploration(eid)["decisions"][-1]["revision_id"] == rid
    r = client.refine(eid, rid, "Apply correction", grant=Grant(actions=("refine",)), request_id="fix")
    assert "Only staff can assign shifts" in client.get_exploration(eid)["brief"]["accepted_corrections"]
    assert not r["operation"]["result"]["superseded"]


def test_late_generation_cannot_replace_correction(client):
    eid, rid = started(client)
    ready, release = threading.Event(), threading.Event()

    class Slow(FakeIntelligence):
        def generate(self, *args):
            ready.set()
            release.wait(5)
            return design(1)

    client.intelligence = Slow()
    outcomes = []
    thread = threading.Thread(
        target=lambda: outcomes.append(
            client.refine(eid, rid, "Theme", grant=Grant(actions=("refine",)), request_id="slow")
        )
    )
    thread.start()
    assert ready.wait(5)
    client.record_decision(eid, rid, action="brief_correction", text="Staff only", request_id="correction")
    release.set()
    thread.join(5)
    assert outcomes[0]["operation"]["result"]["superseded"]
    assert client.get_exploration(eid)["brief"]["accepted_corrections"] == ["Staff only"]


def test_failure_not_success_and_no_fallback(tmp_path):
    p = Possibly(tmp_path)
    with pytest.raises(PossiblyError) as error:
        p.start("Garden", request_id="a", grant=Grant())
    assert error.value.code == "model_access_required"
    assert not p.store.connect().execute("SELECT id FROM explorations").fetchall()


def test_cli_input_json_and_export(client, tmp_path):
    eid, rid = started(client)
    result = client.make_interactive(eid, rid, grant=Grant(actions=("make_interactive",)), request_id="make")
    r2 = result["operation"]["result"]["revision_ids"][0]
    output = tmp_path / "export"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "possibly",
            "--store",
            str(client.store.root),
            "export",
            "--input",
            json.dumps({"exploration_id": eid, "revision_id": r2, "request_id": "cli-export"}),
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stdout
    assert (output / "prototype.html").read_text().startswith("<!doctype")
    assert json.loads((output / "handoff.json").read_text())["revision_id"] == r2


def test_stop_fences_late_publication_and_awaits_foreground(client):
    eid, rid = started(client)
    ready = threading.Event()

    class Cancellable(FakeIntelligence):
        def generate(self, request, workspace, grant, cancelled):
            import time

            ready.set()
            while not cancelled():
                time.sleep(0.01)
            time.sleep(0.1)  # Actual cleanup must finish before stop reports success.
            return design(1)

    client.intelligence = Cancellable()
    thread = threading.Thread(
        target=lambda: client.refine(
            eid, rid, "Theme", grant=Grant(actions=("refine",)), request_id="running"
        )
    )
    thread.start()
    assert ready.wait(5)
    stopped = client.stop(eid, request_id="stop")
    thread.join(2)
    assert not thread.is_alive()
    assert stopped["cleanup"]["status"] == "succeeded"
    assert len(client.get_exploration(eid)["revisions"]) == 2
    assert client.get_operation(eid, stopped["receipt"]["operation_id"])["state"] == "succeeded"


def test_reopen_reactivate_question_preserves_identity(client):
    eid, rid = started(client)
    client.intelligence.outputs = [
        {"question": {"prompt": "Which navigation?", "why_needed": "Two conflicting references"}}
    ]
    result = client.refine(
        eid, rid, "Change navigation", grant=Grant(actions=("refine",)), request_id="refine"
    )
    op = result["operation"]
    qid = op["questions"][0]["id"]
    client.stop(eid, request_id="stop")
    client.reopen(eid, rid, request_id="reopen")
    with pytest.raises(PossiblyError):
        client.answer(eid, op["id"], qid, "Bottom tabs", request_id="too-early")
    client.reactivate_operation(
        eid,
        op["id"],
        grant=Grant(actions=("refine",)),
        request_id="reactivate",
        expected_state_version=client.get_exploration(eid)["state_version"],
        confirm_relevance=True,
    )
    answer = client.answer(eid, op["id"], qid, "Bottom tabs", request_id="answer")
    assert answer["operation"]["id"] == op["id"]
    assert answer["operation"]["state"] == "succeeded"


def test_expired_retry_returns_original_receipt(client):
    import time

    grant = Grant(expires_at=time.time() + 0.2)
    original = client.start("Garden", request_id="short", grant=grant)
    time.sleep(0.25)
    assert client.start("Garden", request_id="short", grant=grant)["receipt"] == original["receipt"]


def test_partial_artifact_retained_on_failure(client):
    from pathlib import Path

    class Partial(FakeIntelligence):
        def generate(self, request, workspace, grant, cancelled):
            (Path(workspace) / "unfinished.html").write_text(HTML)
            raise PossiblyError("generation_failed", "Synthetic failure after writing an artifact")

    client.intelligence = Partial()
    result = client.start("Garden", request_id="partial", grant=Grant())
    op = result["operation"]
    assert op["state"] == "failed"
    assert len(op["partial_artifacts"]) == 1
    eid = result["receipt"]["exploration_id"]
    rid = op["partial_artifacts"][0]
    assert client.read_artifact(eid, rid)
    assert client.get_revision(eid, rid)["superseded"]
    with pytest.raises(PossiblyError):
        client.record_decision(eid, rid, action="select", request_id="select-incomplete")


def test_invalid_grants_cannot_authorize_work(client):
    for g in (
        {"actions": "explore"},
        {"actions": ["explore"], "max_turns": True},
        {"actions": ["refine"]},
        {"actions": ["explore"], "timeout_seconds": 0},
    ):
        with pytest.raises(PossiblyError):
            client.start("Garden", request_id="invalid", grant=g)
    assert not client.intelligence.calls


def test_cancelled_operation_cannot_resume(client):
    eid, rid = started(client, continuation=True)
    selected = client.record_decision(eid, rid, action="select", request_id="choose")
    oid = selected["receipt"]["follow_up"]
    client.stop(eid, request_id="stop")
    client.reopen(eid, rid, request_id="reopen")
    with pytest.raises(PossiblyError) as error:
        client.resume_operation(eid, oid, grant=Grant(actions=("make_interactive",)), request_id="resume")
    assert error.value.code == "not_resumable"


def test_material_only_and_optional_required_resolution(tmp_path):
    calls = []

    def resolve(reference):
        calls.append(reference)
        if reference == "brief":
            return "Coordinate garden watering shifts"
        raise OSError("Unavailable")

    p = Possibly(tmp_path, intelligence=FakeIntelligence(), material_resolver=resolve)
    inputs = dict(
        request_id="materials",
        grant=Grant(),
        materials=[
            {"name": "Brief", "reference": "brief"},
            {"name": "Optional theme", "reference": "missing", "required": False},
        ],
    )
    result = p.start(**inputs)
    eid = result["receipt"]["exploration_id"]
    assert p.get_exploration(eid)["materials"][0]["content"]
    assert p.get_exploration(eid)["source_errors"][0]["status"] == "unavailable"
    p.start(**inputs)
    assert len(calls) == 2  # Replaying a receipt does not re-read changing external material.
    with pytest.raises(PossiblyError) as error:
        p.start(
            request_id="required", grant=Grant(), materials=[{"name": "Required", "reference": "missing"}]
        )
    assert error.value.code == "required_material_unavailable"


def test_selecting_another_direction_does_not_supersede_running_refinement(client):
    eid, rid = started(client)
    other = next(r for r in client.get_exploration(eid)["revisions"] if r != rid)
    ready, release = threading.Event(), threading.Event()

    class Slow(FakeIntelligence):
        def generate(self, *args):
            ready.set()
            release.wait(5)
            return design(1)

    client.intelligence = Slow()
    results = []
    thread = threading.Thread(
        target=lambda: results.append(
            client.refine(
                eid, rid, "Refine this branch", grant=Grant(actions=("refine",)), request_id="branch"
            )
        )
    )
    thread.start()
    assert ready.wait(5)
    client.record_decision(eid, other, action="select", request_id="other")
    release.set()
    thread.join(5)
    assert not results[0]["operation"]["result"]["superseded"]
    revision = results[0]["operation"]["result"]["revision_ids"][0]
    assert client.get_revision(eid, revision)["direction_id"] == client.get_revision(eid, rid)["direction_id"]


def test_refinement_receives_only_its_direction_feedback(client):
    eid, rid = started(client)
    other = next(r for r in client.get_exploration(eid)["revisions"] if r != rid)
    client.record_decision(
        eid, other, action="feedback", text="Calendar only feedback", request_id="other-feedback"
    )
    client.record_decision(eid, rid, action="feedback", text="Keep this direction", request_id="own-feedback")
    client.refine(eid, rid, "Refine", grant=Grant(actions=("refine",)), request_id="refine")
    assert [d["text"] for d in client.intelligence.calls[-1]["decisions"]] == ["Keep this direction"]


def test_review_drafts_are_ordered_context_not_decisions(client):
    eid, rid = started(client)
    before = client.get_exploration(eid)
    client.save_review_state(eid, revision_id=rid, draft="Newest", sequence=2, request_id="draft-2")
    client.save_review_state(eid, revision_id=rid, draft="Older", sequence=1, request_id="draft-1")
    snapshot = client.review_snapshot(eid)
    assert snapshot["reviews"]["default"]["drafts"][rid] == "Newest"
    assert snapshot["state_version"] == before["state_version"]
    assert not snapshot["decisions"]
    client.record_decision(eid, None, action="feedback", text="Combine concepts", request_id="overall")
    client.refine(eid, rid, "Combine", grant=Grant(actions=("refine",)), request_id="combined")
    assert client.intelligence.calls[-1]["decisions"][0]["text"] == "Combine concepts"


def test_selecting_completed_prototype_does_not_spend_continuation(client):
    eid, rid = started(client, continuation=True)
    result = client.refine(eid, rid, "Complete", grant=Grant(actions=("refine",)), request_id="ready")
    interactive = result["operation"]["result"]["revision_ids"][0]
    selected = client.record_decision(eid, interactive, action="select", request_id="choose-ready")
    assert selected["receipt"]["follow_up"] is None
