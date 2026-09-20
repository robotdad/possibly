"""Public library. Every mutation has a durable request receipt; retries never drive work twice."""

import copy
import json
import os
import threading
import time
from dataclasses import asdict
from pathlib import Path

from .artifacts import isolate_html
from .checkpoints import read_checkpoint, validated_output
from .models import Grant, PossiblyError, Presentation
from .store import Store, event, new_id

ACTIONS = {"explore", "make_interactive", "refine"}


class Possibly:
    """Bind an explicit durable store, optional intelligence and caller identity.

    execution='in_process' drives new operations before returning; 'owned_runner'
    starts a subprocess with explicit model environment opt-in. Deterministic calls
    need neither a model nor a runner. Public results contain only JSON values.
    """

    def _provider_adapter(self):
        from .intelligence import AmplifierIntelligence

        return self.intelligence or AmplifierIntelligence()

    @staticmethod
    def plan_exploration(candidates=None, concurrency=3):
        """Resolve a bounded task-diverse provider/model plan without generation. See start exploration_plan."""
        from .fanout import plan_exploration

        return plan_exploration(candidates, concurrency)

    def provider_settings(self):
        """Read redacted provider settings; does not call a model or save configuration."""
        return self._provider_adapter().provider_settings()

    def configure_provider(
        self,
        provider,
        model=None,
        reasoning_effort=None,
        provider_config=None,
        exploration_id=None,
    ):
        """Apply an effective non-secret provider configuration for one execution scope."""
        if self.intelligence is None:
            raise PossiblyError(
                "model_access_required", "Bind an intelligence adapter before configuring it."
            )
        from .providers import checked_config

        current = self.intelligence.configuration() if hasattr(self.intelligence, "configuration") else None
        options = (
            checked_config(provider_config)
            if provider_config is not None
            else copy.deepcopy(
                current.options if current is not None and current.provider == provider else {}
            )
        )
        effective_model = (
            model
            if model is not None
            else (current.model if current is not None and current.provider == provider else None)
        )
        effective_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else (current.effort if current is not None and current.provider == provider else None)
        )
        result = self.intelligence.configure_provider(provider, effective_model, effective_effort, options)
        if exploration_id is not None and self.execution == "owned_runner":
            with self.store.transaction() as db:
                state = self.store.get(exploration_id, db)
                self._active(state)
                if any(
                    operation["state"] in {"queued", "running"} for operation in state["operations"].values()
                ):
                    raise PossiblyError(
                        "provider_busy", "Wait for active generation before changing providers."
                    )
                state["provider_runtime"] = {
                    "scope": f"{exploration_id}:{state['active_period_id']}",
                    "provider": provider,
                    "model": effective_model,
                    "reasoning_effort": effective_effort,
                    "provider_config": options,
                    "updated_at": time.time(),
                }
                self.store.put(db, state)
        return result

    def apply_runtime_provider_configuration(self, exploration_id):
        """Apply this exploration period's serialized effective runtime configuration."""
        if self.intelligence is None:
            return None
        try:
            state = self.store.get(exploration_id)
            data = state.get("provider_runtime")
            if data is None:
                return None
            if data.get("scope") != f"{exploration_id}:{state['active_period_id']}":
                raise PossiblyError(
                    "provider_configuration_invalid", "Runtime configuration belongs to another period."
                )
            return self.intelligence.configure_provider(
                data["provider"],
                data.get("model"),
                data.get("reasoning_effort"),
                data["provider_config"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PossiblyError(
                "provider_configuration_invalid", "Owned runner configuration is invalid."
            ) from exc

    def provider_models(self, provider=None, timeout_seconds=30):
        """Discover provider model IDs without generation. Requires authorized provider access."""
        return self._provider_adapter().provider_models(provider, timeout_seconds)

    def test_provider(
        self, provider=None, model=None, reasoning_effort=None, provider_config=None, timeout_seconds=60
    ):
        """Send one small connection-test request through the configured Amplifier provider."""
        return self._provider_adapter().test_provider(
            provider, model, reasoning_effort, provider_config, timeout_seconds
        )

    def provider_login(self, provider=None, timeout_seconds=300, on_progress=None):
        """Run explicit provider login; progress contains device instructions, never credentials."""
        return self._provider_adapter().provider_login(provider, timeout_seconds, on_progress)

    def start_provider_job(
        self,
        exploration_id,
        *,
        kind,
        request_id,
        reviewer_id=None,
        provider=None,
        model=None,
        reasoning_effort=None,
        provider_config=None,
        timeout_seconds=None,
    ):
        """Start one bounded, retained provider action; opening a view never starts one."""
        if kind not in {"test", "models", "login"}:
            raise PossiblyError("invalid_settings", "Provider job kind must be test, models, or login.")
        if provider_config is not None:
            from .providers import checked_config

            provider_config = checked_config(provider_config)
        timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else (300 if kind == "login" else 30 if kind == "models" else 60)
        )
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 300:
            raise PossiblyError(
                "invalid_settings", "Provider job timeout must be an integer from 1 through 300 seconds."
            )

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state)
            if any(operation["state"] in {"queued", "running"} for operation in state["operations"].values()):
                raise PossiblyError("provider_busy", "Wait for active generation before provider setup work.")
            if reviewer_id is not None and reviewer_id not in state.setdefault("review_states", {}):
                raise PossiblyError(
                    "review_attachment_required", "Open a retained review before starting a provider job."
                )
            jobs = state.setdefault("provider_jobs", {})
            if any(job["state"] == "running" for job in jobs.values()):
                raise PossiblyError("provider_busy", "A provider action is already running.")
            job = {
                "id": new_id("provider_job"),
                "kind": kind,
                "state": "running",
                "reviewer_id": reviewer_id,
                "messages": [],
                "result": None,
                "error": None,
                "requested_at": time.time(),
                "timeout_seconds": timeout_seconds,
            }
            jobs[job["id"]] = job
            self.store.put(db, state)
            return self._receipt(state, provider_job=copy.deepcopy(job))

        result = self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "start_provider_job",
                "eid": exploration_id,
                "kind": kind,
                "reviewer": reviewer_id,
                "provider": provider,
                "model": model,
                "effort": reasoning_effort,
                "provider_config": provider_config,
                "timeout": timeout_seconds,
            },
            accept,
        )
        if result["status"] == "accepted":
            job_id = result["receipt"]["provider_job"]["id"]
            thread = threading.Thread(
                target=self._run_provider_job,
                kwargs={
                    "exploration_id": exploration_id,
                    "job_id": job_id,
                    "kind": kind,
                    "provider": provider,
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "provider_config": provider_config,
                    "timeout_seconds": timeout_seconds,
                },
                daemon=True,
            )
            thread.start()
        return result

    def _run_provider_job(
        self,
        *,
        exploration_id,
        job_id,
        kind,
        provider,
        model,
        reasoning_effort,
        provider_config,
        timeout_seconds,
    ):
        def progress(message):
            with self.store.transaction() as db:
                state = self.store.get(exploration_id, db)
                job = state.get("provider_jobs", {}).get(job_id)
                if job and job["state"] == "running":
                    job["messages"].append(str(message)[:2000])
                    self.store.put(db, state)

        try:
            result = (
                self.provider_login(provider, timeout_seconds, progress)
                if kind == "login"
                else self.provider_models(provider, timeout_seconds)
                if kind == "models"
                else self.test_provider(provider, model, reasoning_effort, provider_config, timeout_seconds)
            )
            outcome = {"state": "complete", "result": result, "error": None}
        except PossiblyError as exc:
            outcome = {"state": "failed", "result": None, "error": exc.to_dict()["error"]}
        except Exception:
            outcome = {
                "state": "failed",
                "result": None,
                "error": {
                    "code": "provider_job_failed",
                    "message": "Provider action failed. Check setup and try again.",
                },
            }
        with self.store.transaction() as db:
            state = self.store.get(exploration_id, db)
            job = state.get("provider_jobs", {}).get(job_id)
            if job and job["state"] == "running":
                job.update(outcome, completed_at=time.time())
                self.store.put(db, state)

    def provider_job(self, exploration_id, reviewer_id=None):
        """Read the newest retained provider job for this review without triggering work."""
        state = self.store.get(exploration_id)
        jobs = list(state.get("provider_jobs", {}).values())
        if reviewer_id is not None:
            jobs = [job for job in jobs if job.get("reviewer_id") == reviewer_id]
        if not jobs:
            return {"status": "idle", "messages": []}
        job = max(jobs, key=lambda value: value["requested_at"])
        return {
            "status": job["state"],
            "kind": job["kind"],
            "messages": list(job["messages"]),
            "result": copy.deepcopy(job["result"]),
            "error": copy.deepcopy(job["error"]),
            "job_id": job["id"],
        }

    def __init__(
        self, storage, *, intelligence=None, material_resolver=None, caller="local", execution="in_process"
    ):
        self.store = Store(storage)
        self.intelligence = intelligence
        self.material_resolver = material_resolver
        self.caller, self.execution = caller, execution
        if execution not in {"in_process", "owned_runner"}:
            raise PossiblyError("invalid_execution", "Choose in_process or owned_runner.")

    def _active(self, state, expected=None):
        if state["lifecycle"] != "active":
            raise PossiblyError("closed", "This exploration is closed.", "Explicitly reopen retained work.")
        if expected is not None and expected != state["state_version"]:
            raise PossiblyError(
                "state_conflict",
                "The exploration changed since you read it.",
                "Read the current snapshot before submitting again.",
                current_state_version=state["state_version"],
            )

    def _grant(self, grant, action):
        g = asdict(grant) if isinstance(grant, Grant) else copy.deepcopy(grant)
        if not isinstance(g, dict):
            raise PossiblyError("grant_required", "Model work requires an explicit execution grant.")
        try:
            g = asdict(Grant(**g))
            valid = (
                isinstance(g["actions"], (list, tuple))
                and all(a in ACTIONS for a in g["actions"])
                and action in g["actions"]
                and type(g["max_turns"]) is int
                and type(g["max_tool_calls"]) is int
                and 1 <= g["max_turns"] <= 20
                and 1 <= g["timeout_seconds"] <= 3600
                and 1 <= g["max_tool_calls"] <= 100
                and type(g["max_model_calls"]) is int
                and 1 <= g["max_model_calls"] <= 100
            )
            if g["expires_at"] is not None and g["expires_at"] <= time.time():
                valid = False
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise PossiblyError(
                "invalid_grant", "Grant is expired, out of bounds, or does not allow this action."
            )
        return g

    def _revision(self, state, rid):
        if rid not in state["revisions"]:
            raise PossiblyError("revision_not_found", "The exact revision is not part of this exploration.")
        return state["revisions"][rid]

    def _operation(self, state, kind, grant, target=None, instruction=""):
        oid = new_id("op")
        op = {
            "id": oid,
            "exploration_id": state["id"],
            "kind": kind,
            "state": "queued",
            "active_period_id": state["active_period_id"],
            "target": target,
            "instruction": instruction,
            "grant": self._grant(grant, kind) if grant is not None else None,
            "turns_used": 0,
            "seconds_used": 0.0,
            "answers": [],
            "questions": [],
            "base_epoch": state["design_epoch"],
            "partial_artifacts": [],
            "result": None,
            "failure": None,
        }
        state["operations"][oid] = op
        event(state, "operation_accepted", operation_id=oid, operation_kind=kind)
        return op

    def _receipt(self, state, **fields):
        return {
            "receipt_id": new_id("receipt"),
            "exploration_id": state["id"],
            "state_version": state["state_version"],
            **fields,
        }

    def _preflight(self, exploration_plan=None, base=None):
        if self.intelligence is None:
            raise PossiblyError(
                "model_access_required",
                "No intelligence adapter is bound.",
                "Bind AmplifierIntelligence or pass --model-env.",
            )
        if exploration_plan and hasattr(self.intelligence, "preflight_plan"):
            self.intelligence.preflight_plan()
        else:
            adapter = (
                self.intelligence.for_revision(base)
                if hasattr(self.intelligence, "for_revision")
                else self.intelligence
            )
            adapter.preflight()
        if self.execution == "owned_runner":
            from .intelligence import AmplifierIntelligence

            if not isinstance(self.intelligence, AmplifierIntelligence):
                raise PossiblyError("runner_unavailable", "Owned runner supports AmplifierIntelligence only.")

    def _drive(self, result):
        if result["status"] != "accepted":
            return result
        receipt = result["receipt"]
        eid, oid = receipt["exploration_id"], receipt.get("operation_id") or receipt.get("follow_up")
        if not oid:
            return result
        if self.execution == "owned_runner":
            from .runner import launch

            result["execution"] = launch(self, eid)
        else:
            result["operation"] = self.run_operation(eid, oid)
        return result

    def start(
        self,
        context: str = "",
        *,
        request_id: str,
        grant: Grant,
        presentation=Presentation(),
        materials=(),
        exploration_plan=None,
    ):
        """Explore context and/or materials: {name, content} or {name, reference, required?}.

        References are read only by an explicitly bound host material_resolver callable.
        """
        g = asdict(grant) if isinstance(grant, Grant) else copy.deepcopy(grant)
        p = (
            asdict(presentation)
            if isinstance(presentation, Presentation)
            else asdict(Presentation(**presentation))
        )
        if not isinstance(context, str) or (not context.strip() and not materials):
            raise PossiblyError(
                "context_required", "Supply conversation context, material contents, or declared references."
            )
        if p["mode"] not in {"headless", "host", "builtin"}:
            raise PossiblyError("invalid_presentation", "Choose headless, host or builtin.")
        if p["mode"] == "builtin" and (not p["service"] or self.execution != "owned_runner"):
            raise PossiblyError(
                "presentation_authority", "Builtin presentation requires service authority and owned_runner."
            )
        for m in materials:
            if (
                not isinstance(m, dict)
                or not m.get("name")
                or not (isinstance(m.get("content"), str) or isinstance(m.get("reference"), str))
            ):
                raise PossiblyError(
                    "invalid_material",
                    "Materials require name and content, or a reference resolved by an explicitly bound host resolver.",
                )
        payload = {
            "method": "start",
            "exploration_plan": exploration_plan,
            "context": context,
            "materials": materials,
            "grant": g,
            "presentation": p,
        }

        def accept(db):
            self._grant(g, "explore")
            self._preflight(exploration_plan)
            resolved, source_errors = [], []
            for material in materials:
                if "content" in material:
                    resolved.append({"name": material["name"], "content": material["content"]})
                    continue
                reference = material["reference"]
                from urllib.parse import urlsplit

                if urlsplit(reference).username is not None:
                    raise PossiblyError("credential_reference", "Credential-bearing URLs cannot be retained.")
                try:
                    if self.material_resolver is None:
                        raise ValueError("No host resolver")
                    content = self.material_resolver(reference)
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError("No readable material")
                except Exception:
                    if material.get("required", True):
                        raise PossiblyError(
                            "required_material_unavailable",
                            "A required reference could not be read.",
                            "Supply its content or bind an authorized material_resolver.",
                            reference=reference,
                        )
                    source_errors.append(
                        {"name": material["name"], "reference": reference, "status": "unavailable"}
                    )
                else:
                    resolved.append({"name": material["name"], "reference": reference, "content": content})
            if not context.strip() and not resolved:
                raise PossiblyError("no_usable_context", "No supplied material could be read.")
            state = {
                "id": new_id("exp"),
                "state_version": 0,
                "design_epoch": 0,
                "active_period_id": new_id("period"),
                "lifecycle": "active",
                "context": context,
                "materials": resolved,
                "source_errors": source_errors,
                "brief": None,
                "brief_history": [],
                "revisions": {},
                "decisions": [],
                "selected_revision": None,
                "operations": {},
                "events": [],
                "presentation": p,
                "runner": None,
                "continuation": self._grant(g, "explore")
                if g.get("prototype_after_selection", False)
                else None,
                "continuation_used": False,
            }
            if exploration_plan is not None:
                from .fanout import plan_exploration

                state["exploration_plan"] = plan_exploration(
                    **({} if exploration_plan == "auto" else exploration_plan)
                )
            op = self._operation(state, "explore", g)
            self.store.put(db, state)
            return self._receipt(state, operation_id=op["id"])

        return self._drive(self.store.mutate(self.caller, request_id, payload, accept))

    def get_exploration(self, exploration_id, *, max_embedded_bytes=256_000):
        """Return an atomic bounded snapshot; immutable HTML is retrieved separately.

        A review snapshot is deliberately metadata-first.  Generated thumbnails are
        optional presentation data, so an oversized thumbnail is explicitly omitted
        rather than inflating an MCP result beyond a host's safe response budget.
        Callers can still retrieve the exact revision/artifact through its public
        read method.
        """
        if not isinstance(max_embedded_bytes, int) or not 1 <= max_embedded_bytes <= 1_000_000:
            raise PossiblyError(
                "invalid_limit", "Embedded snapshot byte limit must be an integer from 1 through 1000000."
            )
        state = self.store.get(exploration_id)
        state.setdefault("review_states", {})
        state["cursor"] = len(state.pop("events"))
        # Never disclose presenter capability tokens to embedded prototype content.
        if state["runner"]:
            from .runner import viewer_url

            state["runner"]["url"] = viewer_url(self.store.root, state["runner"])
        embedded = 0
        for revision in state["revisions"].values():
            revision.pop("html", None)
            thumbnail = revision.get("thumbnail")
            if thumbnail is None:
                continue
            size = len(str(thumbnail).encode("utf-8"))
            if size > max_embedded_bytes or embedded + size > max_embedded_bytes:
                revision.pop("thumbnail", None)
                revision["thumbnail_omitted"] = {
                    "code": "thumbnail_too_large",
                    "bytes": size,
                    "limit": max_embedded_bytes,
                }
            else:
                embedded += size
        return state

    def get_operation(self, exploration_id, operation_id):
        state = self.store.get(exploration_id)
        if operation_id not in state["operations"]:
            raise PossiblyError("operation_not_found", "Unknown operation ID.")
        op = state["operations"][operation_id]
        op["execution_status"] = {
            "mode": op.get("execution_mode", self.execution),
            "availability": "available",
        }
        if op["state"] in {"running", "queued"}:
            runner = state.get("runner")
            if op["state"] == "running" and op.get("owner_pid"):
                try:
                    os.kill(op["owner_pid"], 0)
                except ProcessLookupError:
                    op["execution_status"]["availability"] = "recovery_required"
                    op["state"] = "interrupted"
            if runner and time.time() - runner.get("heartbeat", 0) > 10:
                op["execution_status"]["availability"] = "recovery_required"
            elif op["state"] == "queued" and not runner:
                op["execution_status"]["availability"] = "unavailable"
        return op

    def wait_operation(self, exploration_id, operation_id, *, timeout=30):
        """Observe only; a timeout neither cancels nor drives execution."""
        deadline = time.monotonic() + min(max(timeout, 0), 60)
        while True:
            op = self.get_operation(exploration_id, operation_id)
            if (
                op["state"] not in {"running", "queued"}
                or op["execution_status"]["availability"] != "available"
            ):
                return {"status": "observed", "operation": op}
            if time.monotonic() >= deadline:
                return {"status": "wait_timed_out", "operation": op}
            time.sleep(0.1)

    def read_changes(self, exploration_id, *, cursor=0, limit=100):
        state = self.store.get(exploration_id)
        if cursor < 0 or cursor > len(state["events"]):
            raise PossiblyError(
                "history_gap",
                "Cursor does not identify retained history.",
                "Read get_exploration and restart from its cursor.",
            )
        events = state["events"][cursor : cursor + min(max(limit, 1), 1000)]
        return {
            "exploration_id": exploration_id,
            "events": events,
            "next_cursor": events[-1]["cursor"] if events else cursor,
            "has_more": cursor + len(events) < len(state["events"]),
        }

    def save_review_state(
        self,
        exploration_id,
        *,
        view_id="compare",
        revision_id=None,
        view_revision_id=None,
        draft="",
        request_id,
        reviewer_id="default",
        sequence=0,
        appearance="system",
    ):
        """Autosave review context, never a decision or generation grant.

        Each reviewer/tab owns a monotonic sequence. Older saves cannot overwrite newer ones.
        Drafts are keyed by exact revision, or 'overall' for exploration-wide notes.
        """
        if not isinstance(draft, str) or len(draft) > 20000:
            raise PossiblyError("invalid_draft", "Draft must be text of at most 20000 characters.")
        if (
            not isinstance(sequence, int)
            or sequence < 0
            or not isinstance(reviewer_id, str)
            or not 0 < len(reviewer_id) <= 200
            or appearance not in {"system", "light", "dark"}
        ):
            raise PossiblyError(
                "invalid_review",
                "Supply a reviewer ID, nonnegative sequence, and system/light/dark appearance.",
            )

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state)
            if revision_id:
                self._revision(state, revision_id)
            if view_revision_id:
                self._revision(state, view_revision_id)
            if view_id != "compare" and view_id not in {
                r["direction_id"] for r in state["revisions"].values()
            }:
                raise PossiblyError("invalid_view", "Unknown review workspace.")
            reviews = state.setdefault("review_states", {})
            review = reviews.setdefault(
                reviewer_id,
                {
                    "sequence": -1,
                    "drafts": {},
                    "pending_mutations": {},
                    "view_id": "compare",
                    "revision_id": None,
                    "view_revision_id": None,
                    "appearance": "system",
                },
            )
            review.setdefault("pending_mutations", {})
            if sequence <= review["sequence"]:
                return self._receipt(state, saved=False)
            review.update(
                sequence=sequence,
                view_id=view_id,
                revision_id=revision_id,
                view_revision_id=view_revision_id,
                appearance=appearance,
                saved_at=time.time(),
            )
            review["drafts"][revision_id or "overall"] = draft
            # Review saves don't change the design version or invalidate submitted decisions.
            self.store.put(db, state)
            return self._receipt(state, saved=True, review=copy.deepcopy(review))

        return self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "save_review_state",
                "eid": exploration_id,
                "view": view_id,
                "revision": revision_id,
                "view_revision": view_revision_id,
                "draft": draft,
                "reviewer": reviewer_id,
                "sequence": sequence,
                "appearance": appearance,
            },
            accept,
        )

    def open_review(self, exploration_id, *, request_id, reviewer_id=None):
        """Create or explicitly reattach a retained presentation-review identity.

        An MCP Apps frame is opaque and cannot use browser storage as its identity
        source.  A host receives this result before it mounts the native controller;
        omitting ``reviewer_id`` always creates an independent retained view, while
        supplying an existing ID is the explicit reuse path.
        """
        if reviewer_id is not None and (not isinstance(reviewer_id, str) or not 0 < len(reviewer_id) <= 200):
            raise PossiblyError(
                "invalid_review", "reviewer_id must be a nonempty string of at most 200 characters."
            )

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state)
            reviews = state.setdefault("review_states", {})
            identity = reviewer_id or new_id("review")
            review = reviews.setdefault(
                identity,
                {
                    "sequence": -1,
                    "drafts": {},
                    "pending_mutations": {},
                    "view_id": "compare",
                    "revision_id": None,
                    "view_revision_id": None,
                    "appearance": "system",
                    "created_at": time.time(),
                },
            )
            review.setdefault("pending_mutations", {})
            self.store.put(db, state)
            return self._receipt(
                state,
                reviewer_id=identity,
                review=copy.deepcopy(review),
                attachment={"exploration_id": exploration_id, "reviewer_id": identity},
            )

        return self.store.mutate(
            self.caller,
            request_id,
            {"method": "open_review", "eid": exploration_id, "reviewer": reviewer_id},
            accept,
        )

    @staticmethod
    def _review_intent(state, reviewer_id, *, request_id, path, payload, view_id):
        """Record the exact presenter mutation in the same transaction as its receipt."""
        if reviewer_id is None:
            return
        reviews = state.setdefault("review_states", {})
        review = reviews.get(reviewer_id)
        if review is None:
            raise PossiblyError(
                "review_attachment_required",
                "Open or explicitly attach a retained review before submitting from a portable view.",
            )
        review.setdefault("pending_mutations", {})[request_id] = {
            "request_id": request_id,
            "path": path,
            "payload": copy.deepcopy(payload),
            "view_id": view_id,
            "recorded_at": time.time(),
        }

    def acknowledge_review_intent(self, exploration_id, *, reviewer_id, mutation_request_id, request_id):
        """Clear one acknowledged presentation intent without inferring success from state."""

        def accept(db):
            state = self.store.get(exploration_id, db)
            review = state.setdefault("review_states", {}).get(reviewer_id)
            if review is None:
                raise PossiblyError("review_not_found", "This retained review identity is unavailable.")
            removed = review.setdefault("pending_mutations", {}).pop(mutation_request_id, None)
            self.store.put(db, state)
            return self._receipt(state, acknowledged=bool(removed), mutation_request_id=mutation_request_id)

        return self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "acknowledge_review_intent",
                "eid": exploration_id,
                "reviewer": reviewer_id,
                "mutation_request": mutation_request_id,
            },
            accept,
        )

    def review_snapshot(self, exploration_id):
        """Read saved dashboard views/drafts and submitted decisions before continuing a conversation.

        Drafts are context only, not accepted instructions. Browser text not yet saved is unavailable.
        """
        state = self.store.get(exploration_id)
        return {
            "exploration_id": exploration_id,
            "lifecycle": state["lifecycle"],
            "state_version": state["state_version"],
            "reviews": state.get("review_states", {}),
            "decisions": state["decisions"],
            "selected_revision": state["selected_revision"],
        }

    def get_revision(self, exploration_id, revision_id):
        rev = self._revision(self.store.get(exploration_id), revision_id)
        return {k: v for k, v in rev.items() if k != "html"}

    def read_artifact(self, exploration_id, revision_id, *, max_bytes=None):
        """Read one immutable artifact, optionally refusing oversized UTF-8 content before serialization."""
        html = self._revision(self.store.get(exploration_id), revision_id)["html"]
        if max_bytes is not None:
            if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 1_000_000:
                raise PossiblyError(
                    "invalid_limit", "Artifact byte limit must be an integer from 1 through 1000000."
                )
            actual = len(html.encode("utf-8"))
            if actual > max_bytes:
                raise PossiblyError(
                    "artifact_too_large",
                    f"Artifact is {actual} UTF-8 bytes, above the requested {max_bytes}-byte limit.",
                    "Read/export this exact revision through a caller with an appropriate bounded artifact policy.",
                )
        return html

    def record_decision(
        self,
        exploration_id,
        revision_id,
        *,
        action,
        request_id,
        text="",
        expected_state_version=None,
        reviewer_id=None,
        view_id=None,
    ):
        """Record select/reject/feedback/brief_correction against exactly what was reviewed."""
        if action not in {"select", "reject", "feedback", "brief_correction"}:
            raise PossiblyError("invalid_action", "Choose select, reject, feedback or brief_correction.")
        if action in {"feedback", "brief_correction"} and not text.strip():
            raise PossiblyError("text_required", "Feedback and brief corrections require text.")

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state, expected_state_version)
            rev = self._revision(state, revision_id) if revision_id else None
            if rev is None and action != "feedback":
                raise PossiblyError("revision_required", "This decision requires an exact revision.")
            if action == "select" and rev["superseded"]:
                raise PossiblyError(
                    "stale_revision",
                    "This revision is superseded.",
                    "Review current material or refine the old base explicitly.",
                )
            decision = {
                "id": new_id("decision"),
                "action": action,
                "revision_id": revision_id,
                "text": text,
                "active_period_id": state["active_period_id"],
            }
            self._review_intent(
                state,
                reviewer_id,
                request_id=request_id,
                path="/decision",
                payload={
                    "exploration_id": exploration_id,
                    "revision_id": revision_id,
                    "action": action,
                    "text": text,
                    "expected_state_version": expected_state_version,
                    "request_id": request_id,
                    "reviewer_id": reviewer_id,
                    "view_id": view_id,
                },
                view_id=view_id,
            )
            state["decisions"].append(decision)
            follow_up = None
            if action == "select":
                # Selection is navigation among branches, not an intent correction.
                state["selected_revision"] = revision_id
                if rev["kind"] == "storyboard" and state["continuation"] and not state["continuation_used"]:
                    g = copy.deepcopy(state["continuation"])
                    g["actions"] = ["make_interactive"]
                    try:
                        self._grant(g, "make_interactive")
                    except PossiblyError:
                        state["continuation"] = None
                    else:
                        op = self._operation(state, "make_interactive", g, revision_id)
                        follow_up = op["id"]
                        state["continuation_used"] = True
            if action == "brief_correction":
                state["design_epoch"] += 1
                if state["brief"]:
                    state["brief_history"].append(state["brief"])
                brief = copy.deepcopy(state["brief"] or {})
                brief["id"] = new_id("brief")
                brief.setdefault("accepted_corrections", []).append(text)
                state["brief"] = brief
                for item in state["revisions"].values():
                    item["superseded"] = True
            event(state, "decision_recorded", decision=decision, follow_up=follow_up)
            self.store.put(db, state)
            return self._receipt(
                state,
                decision_id=decision["id"],
                target=revision_id,
                follow_up=follow_up,
                pending_action="refine"
                if action in {"feedback", "brief_correction"}
                else ("make_interactive" if action == "select" and not follow_up else None),
            )

        result = self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "decision",
                "eid": exploration_id,
                "rid": revision_id,
                "action": action,
                "text": text,
                "expected": expected_state_version,
                "reviewer": reviewer_id,
                "view": view_id,
            },
            accept,
        )
        # Recording decisions stays provider-free. An existing runner consumes authorized follow-ups.
        return result

    def _request_work(self, kind, exploration_id, revision_id, instruction, grant, request_id, expected):
        g = asdict(grant) if isinstance(grant, Grant) else copy.deepcopy(grant)

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state, expected)
            revision = self._revision(state, revision_id)
            self._preflight(base=revision)
            op = self._operation(state, kind, g, revision_id, instruction)
            event(state, "explicit_base_chosen", operation_id=op["id"], revision_id=revision_id)
            self.store.put(db, state)
            return self._receipt(state, operation_id=op["id"])

        return self._drive(
            self.store.mutate(
                self.caller,
                request_id,
                {
                    "method": kind,
                    "eid": exploration_id,
                    "rid": revision_id,
                    "instruction": instruction,
                    "grant": g,
                    "expected": expected,
                },
                accept,
            )
        )

    def make_interactive(
        self, exploration_id, revision_id, *, grant, request_id, expected_state_version=None
    ):
        return self._request_work(
            "make_interactive",
            exploration_id,
            revision_id,
            "Make the selected central task clickable.",
            grant,
            request_id,
            expected_state_version,
        )

    def refine(
        self, exploration_id, revision_id, instruction, *, grant, request_id, expected_state_version=None
    ):
        """Explicitly choose a reviewed base. Earlier revisions remain immutable."""
        return self._request_work(
            "refine", exploration_id, revision_id, instruction, grant, request_id, expected_state_version
        )

    def answer(
        self,
        exploration_id,
        operation_id,
        question_id,
        text,
        *,
        request_id,
        expected_state_version=None,
        reviewer_id=None,
        view_id=None,
    ):
        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state, expected_state_version)
            op = state["operations"].get(operation_id)
            question = next((q for q in (op or {}).get("questions", []) if q["id"] == question_id), None)
            if not question or question["state"] != "pending" or op["state"] != "waiting_input":
                raise PossiblyError(
                    "question_conflict", "This question is not awaiting an answer.", question=question
                )
            self._grant(op["grant"], op["kind"])
            self._review_intent(
                state,
                reviewer_id,
                request_id=request_id,
                path="/answer",
                payload={
                    "exploration_id": exploration_id,
                    "operation_id": operation_id,
                    "question_id": question_id,
                    "text": text,
                    "expected_state_version": expected_state_version,
                    "request_id": request_id,
                    "reviewer_id": reviewer_id,
                    "view_id": view_id,
                },
                view_id=view_id,
            )
            question["state"] = "answered"
            op["answers"].append({"question_id": question_id, "prompt": question["prompt"], "answer": text})
            op["state"] = "queued"
            event(state, "answer_recorded", operation_id=operation_id, question_id=question_id)
            self.store.put(db, state)
            return self._receipt(state, operation_id=operation_id, question_id=question_id)

        result = self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "answer",
                "eid": exploration_id,
                "oid": operation_id,
                "qid": question_id,
                "text": text,
                "expected": expected_state_version,
                "reviewer": reviewer_id,
                "view": view_id,
            },
            accept,
        )
        # Caller may answer without model access; an available runner picks it up.
        return self._drive(result) if self.intelligence is not None else result

    def run_operation(self, exploration_id, operation_id):
        """Explicitly drive queued work in this process. Claim is atomic; never replays a running turn."""
        snapshot = self.store.get(exploration_id)
        self._preflight(
            snapshot.get("exploration_plan")
            if snapshot["operations"].get(operation_id, {}).get("kind") == "explore"
            else None,
            base=snapshot["revisions"].get(snapshot["operations"].get(operation_id, {}).get("target")),
        )
        with self.store.transaction() as db:
            state = self.store.get(exploration_id, db)
            self._active(state)
            op = state["operations"].get(operation_id)
            if not op or op["state"] != "queued":
                raise PossiblyError("operation_conflict", "Only queued operations may be driven.")
            if any(o["state"] == "running" for o in state["operations"].values()):
                raise PossiblyError("operation_busy", "Another operation is running in this exploration.")
            self._grant(op["grant"], op["kind"])
            if (
                op["turns_used"] >= op["grant"]["max_turns"]
                or op["seconds_used"] >= op["grant"]["timeout_seconds"]
            ):
                op["state"] = "failed"
                op["failure"] = {"code": "budget_exhausted", "message": "Request new bounded work."}
                event(state, "operation_failed", operation_id=operation_id)
                self.store.put(db, state)
                return copy.deepcopy(op)
            op["state"] = "running"
            op["turns_used"] += 1
            op["started_at"] = time.time()
            op["owner_pid"] = os.getpid()
            op["execution_mode"] = self.execution
            op["execution_active"] = True
            op["base_epoch"] = state["design_epoch"]
            event(state, "operation_running", operation_id=operation_id)
            self.store.put(db, state)
            base = state["revisions"].get(op["target"])
            branch_ids = {
                rid
                for rid, revision in state["revisions"].items()
                if base and revision["direction_id"] == base["direction_id"]
            }
            branch_brief = next(
                (
                    b
                    for b in [state["brief"], *state["brief_history"]]
                    if base and b and b["id"] == base["brief_id"]
                ),
                state["brief"],
            )
            # Corrections are global; ordinary feedback belongs to the reviewed direction.
            if branch_brief:
                branch_brief = copy.deepcopy(branch_brief)
                branch_brief["accepted_corrections"] = (state["brief"] or {}).get("accepted_corrections", [])
            request = {
                "operation_id": operation_id,
                "kind": op["kind"],
                "turn": op["turns_used"],
                "context": state["context"],
                "exploration_plan": state.get("exploration_plan") if op["kind"] == "explore" else None,
                "materials": state["materials"],
                "source_errors": state.get("source_errors", []),
                "brief": branch_brief,
                "base": base,
                "instruction": op["instruction"],
                "answers": op["answers"],
                "decisions": [
                    d
                    for d in state["decisions"]
                    if not base
                    or d["revision_id"] is None
                    or d["revision_id"] in branch_ids
                    or d["action"] == "brief_correction"
                ],
            }
            grant = copy.deepcopy(op["grant"])
            grant["timeout_seconds"] -= op["seconds_used"]
        started = time.monotonic()

        def cancelled():
            live = self.store.get(exploration_id)
            return live["lifecycle"] != "active" or live["active_period_id"] != op["active_period_id"]

        partial = []
        try:
            workspace = self.store.root / "operations" / operation_id / str(op["turns_used"])
            workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                if request.get("exploration_plan"):

                    def publish_candidate(candidate):
                        self._validate_output(candidate, "refine")
                        with self.store.transaction() as db:
                            live = self.store.get(exploration_id, db)
                            current = live["operations"][operation_id]
                            if (
                                live["lifecycle"] != "active"
                                or current["active_period_id"] != live["active_period_id"]
                            ):
                                return
                            if (
                                not current.get("stream_stale")
                                and current.get("stream_epoch", current["base_epoch"]) == live["design_epoch"]
                            ):
                                current["base_epoch"] = live["design_epoch"]
                            else:
                                current["stream_stale"] = True
                            previous = (current.get("result") or {}).get("revision_ids", [])
                            self._publish_output(live, current, candidate, exploration_id)
                            current["result"]["revision_ids"] = previous + current["result"]["revision_ids"]
                            current["state"] = "running"
                            current["stream_epoch"] = live["design_epoch"]
                            event(
                                live,
                                "candidate_ready",
                                operation_id=operation_id,
                                revision_ids=current["result"]["revision_ids"],
                            )
                            self.store.put(db, live)

                    output = self.intelligence.generate(
                        request, workspace, grant, cancelled, on_candidate=publish_candidate
                    )
                    self._validate_output(output, "fanout")
                else:
                    output = self.intelligence.generate(request, workspace, grant, cancelled)
                    self._validate_output(output, op["kind"])
            finally:
                for path in list(Path(workspace).glob("*.html"))[:3]:
                    try:
                        partial.append({"name": path.stem, "html": isolate_html(path.read_text())})
                    except (PossiblyError, UnicodeError):
                        continue
            failure = None
        except Exception as exc:
            output = None
            failure = (
                exc.to_dict()["error"]
                if isinstance(exc, PossiblyError)
                else {
                    "code": "intelligence_failed",
                    "message": type(exc).__name__,
                    "remedy": "Check provider/engine configuration. No result was published.",
                }
            )
        with self.store.transaction() as db:
            state = self.store.get(exploration_id, db)
            current = state["operations"][operation_id]
            current["seconds_used"] += time.monotonic() - started
            current["execution_active"] = False
            current["checkpoint_turn"] = op["turns_used"]
            diagnostics_path = workspace / "diagnostics.json"
            if diagnostics_path.exists():
                current["diagnostics"] = json.loads(diagnostics_path.read_text())
            if failure or state["lifecycle"] != "active":
                for artifact in partial:
                    rid = new_id("rev")
                    state["revisions"][rid] = {
                        **artifact,
                        "id": rid,
                        "exploration_id": exploration_id,
                        "direction_id": state["revisions"].get(current["target"], {}).get("direction_id")
                        or new_id("direction"),
                        "parent": current["target"],
                        "brief_id": (state["brief"] or {}).get("id"),
                        "kind": "partial",
                        "superseded": True,
                        "approach": "Unverified partial output",
                        "tradeoff": "Generation did not complete.",
                        "invariants": [],
                        "mocked": [],
                        "assumptions": [],
                    }
                    current["partial_artifacts"].append(rid)
            if state["lifecycle"] != "active" or current["active_period_id"] != state["active_period_id"]:
                current["state"] = "cancelled"
            elif failure:
                current["state"], current["failure"] = "failed", failure
            elif "question" in output:
                q = {
                    "id": new_id("question"),
                    "operation_id": operation_id,
                    "exploration_id": exploration_id,
                    "state": "pending",
                    "prompt": output["question"]["prompt"],
                    "why_needed": output["question"]["why_needed"],
                    "answer_schema": {"type": "string"},
                }
                current["questions"].append(q)
                current["state"] = "waiting_input"
            elif output.get("fanout") and current.get("result"):
                current["result"].update(
                    partial=output.get("partial", False), candidates=output["fanout"]["candidates"]
                )
                current["state"] = "succeeded"
            else:
                self._publish_output(state, current, output, exploration_id)
            event(state, "operation_" + current["state"], operation_id=operation_id, result=current["result"])
            self.store.put(db, state)
        return self.get_operation(exploration_id, operation_id)

    def _publish_output(self, state, current, output, exploration_id):
        stale = current["base_epoch"] != state["design_epoch"]
        brief = {**output["brief"], "id": new_id("brief")}
        if not stale:
            if state["brief"]:
                state["brief_history"].append(state["brief"])
            # Accepted corrections cannot disappear from the current brief.
            brief["accepted_corrections"] = (state["brief"] or {}).get("accepted_corrections", [])
            state["brief"] = brief
        revisions = []
        for direction in output["directions"]:
            rid = new_id("rev")
            parent = state["revisions"].get(current["target"])
            state["revisions"][rid] = {
                **direction,
                "id": rid,
                "exploration_id": exploration_id,
                "direction_id": parent["direction_id"] if parent else new_id("direction"),
                "parent": current["target"],
                "brief_id": brief["id"],
                "kind": "storyboard" if current["kind"] == "explore" else "interactive",
                "superseded": stale,
                "html": isolate_html(direction["html"]),
            }
            revisions.append(rid)
        current["result"] = {"revision_ids": revisions, "brief": brief, "superseded": stale}
        current["state"] = "succeeded"
        if not stale:
            state["design_epoch"] += 1

    def finalize_operation(self, exploration_id, operation_id, *, request_id, expected_state_version=None):
        """Publish a complete retained checkpoint after a failed run. Deterministic: no model or browser.

        Missing metadata, visual review, or asserted interactions produces checkpoint_incomplete.
        Never treats old HTML-only partials as validated. A changed brief requires explicit new work.
        """
        started = time.monotonic()

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state, expected_state_version)
            op = state["operations"].get(operation_id)
            if not op or op["state"] != "failed" or op.get("execution_active"):
                raise PossiblyError("not_finalizable", "Only failed, inactive operations can be finalized.")
            if (
                op["active_period_id"] != state["active_period_id"]
                or op["base_epoch"] != state["design_epoch"]
            ):
                raise PossiblyError(
                    "stale_checkpoint", "The active period or design intent changed since this checkpoint."
                )
            root = (
                self.store.root
                / "operations"
                / operation_id
                / str(op.get("checkpoint_turn", op["turns_used"]))
            )
            checkpoint = read_checkpoint(root)
            if checkpoint.get("kind") != op["kind"]:
                raise PossiblyError("checkpoint_mismatch", "The checkpoint does not match this operation.")
            output = validated_output(checkpoint, op["kind"])
            self._validate_output(output, op["kind"])
            op["previous_failure"] = op["failure"]
            op["failure"] = None
            self._publish_output(state, op, output, exploration_id)
            op.setdefault("diagnostics", {}).setdefault("stages", []).append(
                {"stage": "deterministic_finalization", "seconds": time.monotonic() - started}
            )
            event(state, "operation_finalized", operation_id=operation_id, result=op["result"])
            self.store.put(db, state)
            return self._receipt(state, operation_id=operation_id, result=op["result"])

        return self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "finalize_operation",
                "eid": exploration_id,
                "oid": operation_id,
                "expected": expected_state_version,
            },
            accept,
        )

    def operation_diagnostics(self, exploration_id, operation_id):
        """Read stage times and provider call usage without prompts or credentials, including live progress."""
        state = self.store.get(exploration_id)
        op = state["operations"].get(operation_id)
        if not op:
            raise PossiblyError("operation_not_found", "Unknown operation.")
        root = self.store.root / "operations" / operation_id / str(op["turns_used"])
        path = root / "diagnostics.json"
        data = (
            json.loads(path.read_text())
            if path.exists() and op["state"] == "running"
            else op.get("diagnostics", {})
        )
        return {"operation_id": operation_id, "state": op["state"], "diagnostics": data}

    def _validate_output(self, output, kind):
        if not isinstance(output, dict):
            raise PossiblyError("invalid_model_result", "Expected an object from intelligence.")
        if "question" in output:
            q = output["question"]
            if not isinstance(q, dict) or not q.get("prompt") or not q.get("why_needed"):
                raise PossiblyError("invalid_model_result", "Question requires prompt and reason.")
            return
        directions = output.get("directions", [])
        if not isinstance(output.get("brief"), dict) or not isinstance(directions, list):
            raise PossiblyError("invalid_model_result", "Expected a brief and directions.")
        if (
            (kind == "explore" and not 2 <= len(directions) <= 3)
            or (kind == "fanout" and not 1 <= len(directions) <= 3)
            or (kind not in {"explore", "fanout"} and len(directions) != 1)
        ):
            raise PossiblyError(
                "invalid_model_result", "Explore needs 2–3 directions; prototype/refine needs one."
            )
        for direction in directions:
            for key in ("name", "approach", "tradeoff", "html"):
                if not isinstance(direction.get(key), str) or not direction[key].strip():
                    raise PossiblyError("invalid_model_result", f"Direction requires {key}.")
            for key in ("invariants", "mocked", "assumptions"):
                if not isinstance(direction.get(key), list):
                    raise PossiblyError("invalid_model_result", f"Direction requires a {key} list.")
            isolate_html(direction["html"])

    def export(
        self,
        exploration_id,
        revision_id,
        *,
        request_id,
        expected_state_version=None,
        reviewer_id=None,
        view_id=None,
    ):
        """Return immutable HTML and handoff as data. Export neither generates nor closes."""

        def accept(db):
            state = self.store.get(exploration_id, db)
            revision = self._revision(state, revision_id)
            if revision["kind"] != "interactive" or revision["superseded"]:
                raise PossiblyError(
                    "not_exportable",
                    "Export requires a current interactive revision.",
                    "Generate/refine the selected direction first.",
                )
            self._review_intent(
                state,
                reviewer_id,
                request_id=request_id,
                path="/export",
                payload={
                    "exploration_id": exploration_id,
                    "revision_id": revision_id,
                    "expected_state_version": expected_state_version,
                    "request_id": request_id,
                    "reviewer_id": reviewer_id,
                    "view_id": view_id,
                },
                view_id=view_id,
            )
            handoff = {
                "exploration_id": exploration_id,
                "revision_id": revision_id,
                "brief": next(
                    (
                        b
                        for b in [state["brief"], *state["brief_history"]]
                        if b and b["id"] == revision["brief_id"]
                    ),
                    state["brief"],
                ),
                "selected_experience": {k: v for k, v in revision.items() if k not in {"html", "review"}},
                "decisions": state["decisions"],
                "production_architecture": "Not prescribed; behavior is mocked.",
            }
            event(state, "exported", revision_id=revision_id)
            self.store.put(db, state)
            return self._receipt(state, revision_id=revision_id, html=revision["html"], handoff=handoff)

        return self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "export",
                "eid": exploration_id,
                "rid": revision_id,
                "expected": expected_state_version,
                "reviewer": reviewer_id,
                "view": view_id,
            },
            accept,
        )

    def read_export_chunk(self, exploration_id, request_id, export_kind, *, offset=0, max_bytes=65_536):
        """Read one bounded UTF-8 chunk from an already accepted exact export receipt."""
        if export_kind not in {"html", "handoff"}:
            raise PossiblyError("invalid_export", "Export kind must be html or handoff.")
        if (
            not isinstance(offset, int)
            or offset < 0
            or not isinstance(max_bytes, int)
            or not 1 <= max_bytes <= 65_536
        ):
            raise PossiblyError(
                "invalid_limit", "Export offsets must be nonnegative and chunks 1 through 65536 bytes."
            )
        stored = self.store.receipt(self.caller, request_id)
        payload, receipt = stored["payload"], stored["receipt"]
        if payload.get("method") != "export" or payload.get("eid") != exploration_id:
            raise PossiblyError("receipt_conflict", "This receipt does not belong to the requested export.")
        value = (
            receipt["html"] if export_kind == "html" else json.dumps(receipt["handoff"], ensure_ascii=False)
        )
        raw = value.encode("utf-8")
        if offset > len(raw):
            raise PossiblyError("invalid_offset", "Export offset is beyond the retained export.")
        chunk = raw[offset : offset + max_bytes]
        return {
            "exploration_id": exploration_id,
            "request_id": request_id,
            "export_kind": export_kind,
            "offset": offset,
            "total_bytes": len(raw),
            "data": chunk.decode("utf-8"),
            "complete": offset + len(chunk) == len(raw),
        }

    def finish(self, exploration_id, revision_id, *, request_id, expected_state_version):
        return self._close(exploration_id, revision_id, request_id, expected_state_version, "finished")

    def stop(self, exploration_id, *, request_id, reason=""):
        return self._close(exploration_id, None, request_id, None, "stopped", reason)

    def _close(self, eid, rid, request_id, expected, lifecycle, reason=""):
        def accept(db):
            state = self.store.get(eid, db)
            self._active(state, expected)
            if rid:
                rev = self._revision(state, rid)
                if rev["superseded"]:
                    raise PossiblyError("stale_revision", "Cannot finish on superseded work.")
            if lifecycle == "finished" and any(
                o["state"] in {"running", "queued", "waiting_input", "waiting_access"}
                for o in state["operations"].values()
            ):
                raise PossiblyError("work_in_flight", "Wait for pending work or explicitly stop it.")
            state["lifecycle"] = lifecycle
            state["continuation"] = None
            state.pop("provider_runtime", None)
            if rid:
                state["selected_revision"] = rid
            for op in state["operations"].values():
                if op["state"] in {"running", "queued", "waiting_input"}:
                    op["state"] = "interrupted" if op["state"] == "waiting_input" else "cancelled"
                for q in op["questions"]:
                    if q["state"] == "pending":
                        q["state"] = "suspended"
            cleanup = {
                "lifecycle": lifecycle,
                "write_fence_active": True,
                "retained_revision_ids": list(state["revisions"]),
                "retained_decision_ids": [d["id"] for d in state["decisions"]],
                "released_resources": [],
                "failed_resources": [],
            }
            cleanup_op = self._operation(state, "cleanup", None)
            cleanup_op["state"] = "running"
            state["cleanup_operation_id"] = cleanup_op["id"]
            cleanup["operation_id"] = cleanup_op["id"]
            state["cleanup"] = cleanup
            event(state, "exploration_" + lifecycle, reason=reason)
            self.store.put(db, state)
            return self._receipt(state, operation_id=cleanup_op["id"], cleanup=cleanup)

        result = self.store.mutate(
            self.caller,
            request_id,
            {"method": lifecycle, "eid": eid, "rid": rid, "expected": expected, "reason": reason},
            accept,
        )
        result["cleanup"] = self.wait_cleanup(eid)
        return result

    def wait_cleanup(self, exploration_id, timeout=10):
        """Await actual runner/foreground cleanup; persist a correlated terminal outcome."""
        deadline = time.monotonic() + min(timeout, 60)
        while True:
            state = self.store.get(exploration_id)
            if state["lifecycle"] == "active":
                raise PossiblyError("not_closing", "Request finish or stop before awaiting cleanup.")
            runner = state.get("runner")
            pending = []

            def alive(pid):
                if not pid:
                    return True
                try:
                    os.kill(pid, 0)
                    return True
                except ProcessLookupError:
                    return False

            # Process death is evidence that its local resources are gone; never signal an arbitrary saved PID.
            with self.store.transaction() as db:
                current = self.store.get(exploration_id, db)
                if runner and runner.get("state") != "closed":
                    if alive(runner.get("pid")):
                        pending.append(runner["id"])
                    else:
                        current["runner"]["state"] = "closed"
                        current["runner"]["url"] = None
                        (self.store.root / (runner["id"] + ".token")).unlink(missing_ok=True)
                for operation in current["operations"].values():
                    if operation.get("execution_active"):
                        if alive(operation.get("owner_pid")):
                            pending.append(operation["id"])
                        else:
                            operation["execution_active"] = False
                self.store.put(db, current)
            if not pending or time.monotonic() >= deadline:
                outcome = {
                    **state["cleanup"],
                    "status": "failed" if pending else "succeeded",
                    "lifecycle": "cleanup_failed" if pending else state["lifecycle"],
                    "failed_resources": [
                        {
                            "resource_id": rid,
                            "cause": "Cleanup not confirmed.",
                            "retry_action": "wait-cleanup",
                        }
                        for rid in pending
                    ],
                }
                with self.store.transaction() as db:
                    current = self.store.get(exploration_id, db)
                    op = current["operations"][current["cleanup_operation_id"]]
                    if op.get("result") != outcome:
                        op["state"] = "failed" if pending else "succeeded"
                        op["result"] = outcome
                        event(current, "cleanup_" + op["state"], operation_id=op["id"])
                        self.store.put(db, current)
                return outcome
            time.sleep(0.1)

    def reopen(self, exploration_id, revision_id, *, request_id):
        """New active period, no spending and no resurrection of old viewer contexts or operations."""

        def accept(db):
            state = self.store.get(exploration_id, db)
            if state["lifecycle"] == "active":
                raise PossiblyError("already_active", "This exploration is already active.")
            self._revision(state, revision_id)
            if state.get("runner") and state["runner"].get("state") != "closed":
                raise PossiblyError("cleanup_pending", "Complete old runner cleanup before reopening.")
            if any(o.get("execution_active") for o in state["operations"].values()):
                raise PossiblyError("cleanup_pending", "Foreground work has not confirmed cancellation.")
            state["active_period_id"] = new_id("period")
            state["lifecycle"] = "active"
            state["selected_revision"] = revision_id
            state["runner"] = None
            state.pop("provider_runtime", None)
            state["presentation"] = asdict(Presentation())
            event(state, "reopened", base=revision_id)
            self.store.put(db, state)
            return self._receipt(state, active_period_id=state["active_period_id"])

        return self.store.mutate(
            self.caller, request_id, {"method": "reopen", "eid": exploration_id, "rid": revision_id}, accept
        )

    def resume_operation(self, exploration_id, operation_id, *, grant, request_id):
        """Explicitly recover uncertain process interruption. A fresh grant authorizes possible repeated spending."""

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state)
            op = state["operations"].get(operation_id)
            if (
                not op
                or op["state"] not in {"interrupted", "running"}
                or op["active_period_id"] != state["active_period_id"]
            ):
                raise PossiblyError(
                    "not_resumable", "Only interrupted work in the same active period can resume."
                )
            if (
                op["state"] == "running"
                and state.get("runner")
                and time.time() - state["runner"].get("heartbeat", 0) < 10
            ):
                raise PossiblyError("still_running", "The runner is still alive.")
            if op.get("execution_active") and op.get("owner_pid"):
                try:
                    os.kill(op["owner_pid"], 0)
                except ProcessLookupError:
                    op["execution_active"] = False
                else:
                    raise PossiblyError("still_running", "The operation's owning process is still alive.")
            self._preflight()
            op["grant"] = self._grant(grant, op["kind"])
            op["turns_used"], op["seconds_used"] = 0, 0.0
            op["state"] = "queued"
            event(state, "recovery_authorized", operation_id=operation_id)
            self.store.put(db, state)
            return self._receipt(state, operation_id=operation_id)

        return self._drive(
            self.store.mutate(
                self.caller,
                request_id,
                {
                    "method": "resume",
                    "eid": exploration_id,
                    "oid": operation_id,
                    "grant": asdict(grant) if isinstance(grant, Grant) else grant,
                },
                accept,
            )
        )

    def reactivate_operation(
        self,
        exploration_id,
        operation_id,
        *,
        grant,
        request_id,
        expected_state_version,
        confirm_relevance=False,
    ):
        """Reactivate a suspended question after reopen, without generating or changing its identity."""

        def accept(db):
            state = self.store.get(exploration_id, db)
            self._active(state, expected_state_version)
            op = state["operations"].get(operation_id)
            if not confirm_relevance or not op or op["state"] != "interrupted":
                raise PossiblyError(
                    "not_reactivatable", "Confirm relevance of an interrupted operation after reopening."
                )
            suspended = [q for q in op["questions"] if q["state"] == "suspended"]
            if not suspended:
                raise PossiblyError("no_suspended_question", "This operation has no suspended question.")
            if op["target"]:
                self._revision(state, op["target"])
            op["grant"] = self._grant(grant, op["kind"])
            op["active_period_id"] = state["active_period_id"]
            op["state"] = "waiting_input"
            op["turns_used"], op["seconds_used"] = 0, 0.0
            for question in suspended:
                question["state"] = "pending"
            event(state, "question_reactivated", operation_id=operation_id)
            self.store.put(db, state)
            return self._receipt(state, operation_id=operation_id)

        return self.store.mutate(
            self.caller,
            request_id,
            {
                "method": "reactivate",
                "eid": exploration_id,
                "oid": operation_id,
                "grant": asdict(grant) if isinstance(grant, Grant) else grant,
                "expected": expected_state_version,
                "confirm": confirm_relevance,
            },
            accept,
        )

    def capabilities(self):
        from .help import capabilities

        return capabilities()

    def manifest(self):
        from .help import manifest

        return manifest()

    def skill(self):
        from .help import skill

        return skill()
