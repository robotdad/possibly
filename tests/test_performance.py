import asyncio
from types import SimpleNamespace

import pytest
from amplifier_core.message_models import ChatRequest, Message
from test_contracts import HTML, FakeIntelligence, design, started

from possibly import Grant, Possibly, PossiblyError
from possibly.artifacts import isolate_html
from possibly.checkpoints import Diagnostics, digest, read_checkpoint, save_checkpoint, validated_output
from possibly.intelligence import CandidateTools
from possibly.runtime import ObservedProvider, SubmissionComplete

FLOW = [
    {"action": "click", "selector": "button"},
    {"action": "assert_text", "selector": "button", "value": "Claimed"},
]


def result():
    value = design(1)
    value["directions"][0].pop("html")
    value["directions"][0]["candidate"] = "base"
    return value


def checked(root):
    tools = CandidateTools(root, 20, request={"kind": "refine", "base": {"html": HTML}})
    asyncio.run(tools.inspect("base", FLOW))
    tools.visual_seen["base"] = digest(tools.candidates["base"])
    tools.submit(result())
    return tools


def test_exact_patch_is_atomic_and_unchanged_write_keeps_evidence(tmp_path):
    tools = checked(tmp_path)
    original = tools.candidates["base"]
    version = digest(original)
    tools.write("base", original)
    assert tools.visual_seen["base"] == version
    assert tools.reviews["base"]["verified_interactions"]
    assert isolate_html(original) == original
    with pytest.raises(PossiblyError, match="exactly once"):
        tools.patch(
            "base", version, [{"old": "Claim shift", "new": "Changed"}, {"old": "absent", "new": "x"}]
        )
    assert tools.candidates["base"] == original
    with pytest.raises(PossiblyError, match="current candidate hash"):
        tools.patch("base", "outdated", [{"old": "Claim shift", "new": "Book"}])
    tools.patch("base", version, [{"old": "Claim shift", "new": "Reserve shift"}])
    assert "base" not in tools.reviews
    assert "base" not in tools.visual_seen
    assert tools.result is None


def test_browser_assertions_catch_removed_behavior_and_inherit(tmp_path):
    tools = checked(tmp_path / "initial")
    base = {"html": tools.candidates["base"], "review": tools.reviews["base"]}
    refined = CandidateTools(tmp_path / "next", 20, request={"kind": "refine", "base": base})
    # Same visible control, broken state update. A click-only check would pass.
    refined.patch(
        "base", digest(refined.candidates["base"]), [{"old": "this.textContent='Claimed'", "new": "void 0"}]
    )
    with pytest.raises(AssertionError):
        asyncio.run(refined.inspect("base", []))
    assert refined.result is None


def test_click_only_is_not_a_task_verification(tmp_path):
    tools = CandidateTools(tmp_path, 10, request={"kind": "refine", "base": {"html": HTML}})
    asyncio.run(tools.inspect("base", FLOW[:1]))
    tools.visual_seen["base"] = digest(tools.candidates["base"])
    with pytest.raises(PossiblyError) as exc:
        tools.submit(result())
    assert exc.value.code == "checkpoint_incomplete"
    assert any("verified visible outcome" in item for item in exc.value.details["missing"])


def test_checkpoint_tamper_or_missing_visual_is_rejected(tmp_path):
    tools = checked(tmp_path)
    checkpoint = read_checkpoint(tmp_path)
    checkpoint["candidates"]["base"] += "\n"
    with pytest.raises(PossiblyError):
        validated_output(checkpoint, "refine")
    checkpoint = tools.checkpoint()
    checkpoint["visual_seen"] = {}
    with pytest.raises(PossiblyError):
        validated_output(checkpoint, "refine")


class TimedOutAfterSubmit(FakeIntelligence):
    def generate(self, request, workspace, grant, cancelled):
        checked(workspace)
        raise PossiblyError("execution_timeout", "Simulated timeout after validated submission")


def test_deterministic_finalize_after_failure_without_provider(tmp_path):
    client = Possibly(tmp_path / "store", intelligence=FakeIntelligence())
    eid, rid = started(client)
    client.intelligence = TimedOutAfterSubmit()
    failed = client.refine(eid, rid, "Theme", grant=Grant(actions=("refine",)), request_id="fail")
    oid = failed["receipt"]["operation_id"]
    assert failed["operation"]["state"] == "failed"
    partial = failed["operation"]["partial_artifacts"][0]
    assert client.get_revision(eid, partial)["direction_id"] == client.get_revision(eid, rid)["direction_id"]
    client.intelligence = None
    finalized = client.finalize_operation(eid, oid, request_id="finish")
    revision = finalized["receipt"]["result"]["revision_ids"][0]
    assert client.get_revision(eid, revision)["kind"] == "interactive"
    assert client.finalize_operation(eid, oid, request_id="finish")["status"] == "replayed"
    assert client.get_operation(eid, oid)["failure"] is None


def test_finalize_rejects_changed_brief_and_incomplete_checkpoint(tmp_path):
    client = Possibly(tmp_path / "store", intelligence=FakeIntelligence())
    eid, rid = started(client)
    client.intelligence = TimedOutAfterSubmit()
    failed = client.refine(eid, rid, "Theme", grant=Grant(actions=("refine",)), request_id="fail")
    oid = failed["receipt"]["operation_id"]
    root = client.store.root / "operations" / oid / "1"
    checkpoint = read_checkpoint(root)
    checkpoint["result"] = None
    save_checkpoint(root, checkpoint)
    with pytest.raises(PossiblyError) as exc:
        client.finalize_operation(eid, oid, request_id="incomplete")
    assert exc.value.code == "checkpoint_incomplete"
    client.record_decision(eid, rid, action="brief_correction", text="Different intent", request_id="correct")
    with pytest.raises(PossiblyError) as exc:
        client.finalize_operation(eid, oid, request_id="stale")
    assert exc.value.code == "stale_checkpoint"


def test_images_arrive_in_same_loop_and_submission_stops_model_calls(tmp_path):
    tools = CandidateTools(tmp_path, 20, request={"kind": "refine", "base": {"html": HTML}})
    asyncio.run(tools.inspect("base", FLOW))
    diag = Diagnostics(tmp_path)
    requests = []

    class Provider:
        default_model = "test-model"

        async def complete(self, request, **kwargs):
            requests.append(request)
            return SimpleNamespace(usage={"input_tokens": 12, "output_tokens": 5})

    provider = ObservedProvider(Provider(), tools, diag, 2)
    request = ChatRequest(messages=[Message(role="user", content="test")])
    asyncio.run(provider.complete(request))
    assert requests[0].messages[-1].content[-1].type == "image"
    assert len(request.messages) == 1  # original request untouched
    assert tools.visual_seen["base"] == digest(tools.candidates["base"])
    tools.submit(result())
    with pytest.raises(SubmissionComplete):
        asyncio.run(provider.complete(request))
    assert len(requests) == 1
    assert diag.data["provider_calls"][0]["usage"]["input_tokens"] == 12
    assert diag.data["provider_calls"][0]["model"] == "test-model"


def test_model_call_limit_and_error_diagnostics(tmp_path):
    tools = CandidateTools(tmp_path, 20)
    diag = Diagnostics(tmp_path)

    class Provider:
        async def complete(self, request, **kwargs):
            raise RuntimeError("secret must not be recorded")

    proxy = ObservedProvider(Provider(), tools, diag, 1)
    request = ChatRequest(messages=[])
    with pytest.raises(RuntimeError):
        asyncio.run(proxy.complete(request))
    with pytest.raises(PossiblyError) as exc:
        asyncio.run(proxy.complete(request))
    assert exc.value.code == "model_call_budget_exhausted"
    assert "secret" not in str(diag.data)
    assert diag.data["provider_calls"][0]["error_type"] == "RuntimeError"


def test_streaming_provider_images_usage_and_terminal_submission(tmp_path):
    tools = CandidateTools(tmp_path, 20)
    diag = Diagnostics(tmp_path)

    class StreamProvider:
        async def stream(self, request, **kwargs):
            yield {"usage": {"output_tokens": 3}}

    proxy = ObservedProvider(StreamProvider(), tools, diag, 2)

    async def run():
        assert [c async for c in proxy.stream(ChatRequest(messages=[]))] == [{"usage": {"output_tokens": 3}}]
        tools.submit({"question": {"prompt": "Which?", "why_needed": "Unknown task"}})
        with pytest.raises(SubmissionComplete):
            async for _ in proxy.stream(ChatRequest(messages=[])):
                pass

    asyncio.run(run())
    assert len(diag.data["provider_calls"]) == 1
    assert diag.data["usage"]["output_tokens"] == 3


def test_inspection_cache_is_exact_to_artifact_and_steps(tmp_path, monkeypatch):
    calls = []

    async def inspect(html, steps):
        calls.append((html, steps))
        return {
            "text": "Claimed",
            "errors": [],
            "blocked_requests": [],
            "steps_run": steps,
            "assertions_passed": 1,
            "screenshot_base64": "AA==",
        }

    monkeypatch.setattr("possibly.intelligence.inspect_html", inspect)
    tools = CandidateTools(tmp_path, 20, request={"base": {"html": HTML}})
    asyncio.run(tools.inspect("base", FLOW))
    asyncio.run(tools.inspect("base", FLOW))
    assert len(calls) == 1
    tools.patch("base", digest(tools.candidates["base"]), [{"old": "Claim shift", "new": "Reserve"}])
    asyncio.run(tools.inspect("base", FLOW))
    assert len(calls) == 2


def test_native_select_verifies_changed_state(tmp_path):
    html = """<html><body><select id="machine" onchange="document.querySelector('output').textContent=this.value"><option value="a">Alpha</option><option value="b">Beta</option></select><output>a</output></body></html>"""
    tools = CandidateTools(tmp_path, 10, request={"kind": "refine", "base": {"html": html}})
    steps = [
        {"action": "select", "selector": "#machine", "value": "b"},
        {"action": "assert_value", "selector": "#machine", "value": "b"},
        {"action": "assert_text", "selector": "output", "value": "b"},
    ]
    review = asyncio.run(tools.inspect("base", steps))
    assert review["assertions_passed"] == 2
    tools.visual_seen["base"] = digest(tools.candidates["base"])
    tools.submit(result())


@pytest.mark.parametrize("method", ["complete", "stream"])
@pytest.mark.parametrize("model_limit", [3, 4])
@pytest.mark.parametrize("tool_limit", [6, 7])
def test_three_concept_budget_includes_submission_and_stops_provider(
    tmp_path, monkeypatch, method, model_limit, tool_limit
):
    async def inspect(html, steps):
        return {
            "text": "Claim shift",
            "errors": [],
            "blocked_requests": [],
            "steps_run": steps,
            "assertions_passed": 0,
            "screenshot_base64": "AA==",
        }

    monkeypatch.setattr("possibly.intelligence.inspect_html", inspect)
    diag = Diagnostics(tmp_path)
    tools = CandidateTools(tmp_path, tool_limit, diagnostics=diag)
    mounted = {tool.name: tool for tool in tools.mountables()}
    requests = []

    class Provider:
        async def complete(self, request, **kwargs):
            requests.append(request)
            return SimpleNamespace(usage={})

        async def stream(self, request, **kwargs):
            requests.append(request)
            yield {"usage": {}}

    proxy = ObservedProvider(Provider(), tools, diag, model_limit)
    request = ChatRequest(messages=[])

    async def model_call():
        if method == "complete":
            await proxy.complete(request)
        else:
            async for _ in proxy.stream(request):
                pass

    async def run():
        await model_call()
        for name in ("bounded", "autopage", "linked"):
            assert (await mounted["write_candidate"].execute({"name": name, "html": HTML})).success
        await model_call()
        for name in tools.candidates:
            assert (await mounted["inspect_candidate"].execute({"name": name})).success
        await model_call()  # Deliver the three screenshots before terminal submission.
        submission = {"brief": {"intent": "Compare task approaches"}, "directions": []}
        for name in tools.candidates:
            direction = design(1)["directions"][0]
            direction.pop("html")
            direction.update(name=name, candidate=name)
            submission["directions"].append(direction)
        if tool_limit == 7:
            assert (await mounted["submit_result"].execute(submission)).success
            with pytest.raises(SubmissionComplete):
                await model_call()
            return
        with pytest.raises(PossiblyError) as failure:
            await mounted["submit_result"].execute(submission)
        assert failure.value.code == "tool_budget_exhausted"
        with pytest.raises(PossiblyError) as rejected:
            await mounted["write_candidate"].execute({"name": "must-not-write", "html": HTML})
        assert rejected.value is failure.value
        for _ in range(2):
            with pytest.raises(PossiblyError) as later:
                await model_call()
            assert later.value is failure.value

    asyncio.run(run())
    assert len(requests) == len(diag.data["provider_calls"]) == 3
    checkpoint = read_checkpoint(tmp_path)
    assert bool(checkpoint["result"]) == (tool_limit == 7)
    assert set(checkpoint["candidates"]) == {"bounded", "autopage", "linked"}
    assert len(checkpoint["reviews"]) == len(checkpoint["visual_seen"]) == 3
    for record in (checkpoint, diag.data):
        assert record["tool_calls_admitted"] == tool_limit
        assert record["tool_calls"] == record["tool_calls_attempted"] == (8 if tool_limit == 6 else 7)
    assert not (tmp_path / "must-not-write.html").exists()


def test_terminal_submission_uses_last_tool_admission(tmp_path):
    tools = CandidateTools(tmp_path, 1)
    submit = next(tool for tool in tools.mountables() if tool.name == "submit_result")
    response = asyncio.run(
        submit.execute({"question": {"prompt": "Which task?", "why_needed": "Unknown intent"}})
    )
    assert response.success
    assert tools.calls == tools.attempts == 1
    with pytest.raises(SubmissionComplete):
        asyncio.run(submit.execute({"question": {"prompt": "duplicate"}}))
    assert tools.calls == tools.attempts == 1


def test_model_budget_failure_prevents_tool_admission_and_keeps_first_error(tmp_path):
    tools = CandidateTools(tmp_path, 1)
    diag = Diagnostics(tmp_path)

    class Provider:
        async def complete(self, request, **kwargs):
            return SimpleNamespace(usage={})

    proxy = ObservedProvider(Provider(), tools, diag, 1)
    request = ChatRequest(messages=[])
    asyncio.run(proxy.complete(request))
    with pytest.raises(PossiblyError) as first:
        asyncio.run(proxy.complete(request))
    assert first.value.code == "model_call_budget_exhausted"
    write = next(tool for tool in tools.mountables() if tool.name == "write_candidate")
    with pytest.raises(PossiblyError) as rejected:
        asyncio.run(write.execute({"name": "denied", "html": HTML}))
    assert rejected.value is first.value
    assert tools.calls == 0 and tools.attempts == 1
    assert not tools.candidates


def test_legacy_diagnostics_do_not_invent_admission_counts(tmp_path):
    client = Possibly(tmp_path / "store", intelligence=FakeIntelligence())
    receipt = client.start("A garden watering app", request_id="start", grant=Grant())
    eid, oid = receipt["receipt"]["exploration_id"], receipt["receipt"]["operation_id"]
    legacy = {"tool_calls": 8, "status": "incomplete"}
    with client.store.transaction() as db:
        state = client.store.get(eid, db)
        state["operations"][oid]["diagnostics"] = legacy
        client.store.put(db, state)
    assert client.operation_diagnostics(eid, oid)["diagnostics"] == legacy
    checkpoint = {"schema": 1, "result": None, "tool_calls": 8}
    save_checkpoint(tmp_path, checkpoint)
    assert read_checkpoint(tmp_path) == checkpoint
