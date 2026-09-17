"""Deterministic A2UI review projection. No provider, HTTP, or execution ownership."""

import json
from pathlib import Path

from .models import PossiblyError

PROTOCOL = "v0.9.1"
CATALOG = "https://github.com/robotdad/possibly/catalogs/review-v1.json"


def review_catalog():
    """Return the pinned renderer capabilities and inline review catalog, without IO side effects."""
    return json.loads((Path(__file__).with_name("static") / "review-catalog.json").read_text())


def surface_id(state):
    return f"possibly-{state['id']}-{state['active_period_id']}"


def present(client, exploration_id, view=None, reviewer_id="default"):
    """Return a complete replayable surface. Hosts may diff components/data between reads."""
    state = client.get_exploration(exploration_id)
    view = {} if view is None else view
    if not isinstance(view, dict) or set(view) - {
        "direction_id",
        "revision_id",
        "comparing",
        "preview",
        "focused",
    }:
        raise PossiblyError("invalid_view", "Unknown review view fields.")
    if not isinstance(reviewer_id, str) or not 0 < len(reviewer_id) <= 200:
        raise PossiblyError("invalid_view", "Supply a reviewer ID of 1–200 characters.")
    if any(k in view and not isinstance(view[k], str) for k in ("direction_id", "revision_id")):
        raise PossiblyError("invalid_view", "Direction and revision IDs must be strings.")
    if "focused" in view and type(view["focused"]) is not bool:
        raise PossiblyError("invalid_view", "focused must be a boolean.")
    revisions = state["revisions"]
    chosen = list(
        dict.fromkeys(
            revisions[d["revision_id"]]["direction_id"]
            for d in state["decisions"]
            if d["action"] == "select" and d["revision_id"] in revisions
        )
    )
    saved = state.get("review_states", {}).get(reviewer_id, {})
    direction = view.get("direction_id", saved.get("view_id", "compare"))
    if direction not in chosen:
        direction = "compare"
    comparing = view.get("comparing", [])
    preview = view.get("preview", [])
    for ids in (comparing, preview):
        if (
            not isinstance(ids, list)
            or len(ids) > 2
            or any(not isinstance(i, str) or i not in revisions for i in ids)
        ):
            raise PossiblyError("invalid_view", "Preview and comparison accept at most two known revisions.")
    if any(len(ids) != len(set(ids)) for ids in (comparing, preview)):
        raise PossiblyError("invalid_view", "Do not repeat revisions in a comparison or preview.")
    if rid := view.get("revision_id"):
        if rid not in revisions or revisions[rid]["direction_id"] != direction:
            raise PossiblyError("invalid_view", "The requested revision does not belong to this workspace.")
    components = []
    active = state["lifecycle"] == "active"
    sid = surface_id(state)

    def node(id, component, **props):
        components.append({"id": id, "component": component, **props})
        return id

    def text(id, value, variant="body"):
        return node(id, "Text", text=str(value), variant=variant)

    def layout(id, children, kind="stack", label="", expanded=False):
        return node(id, "ReviewLayout", children=children, kind=kind, label=label, expanded=expanded)

    def event(name, **context):
        return {"event": {"name": name, "context": context}}

    def button(id, label, name, enabled=True, primary=False, **context):
        return node(
            id,
            "Button",
            child=text(id + "-label", label),
            action=event(name, **context),
            isValid=enabled,
            variant="primary" if primary else "default",
        )

    def decision(id, label, action, rid=None, draft=None, enabled=True):
        context = {"revision_id": rid or "", "expected_state_version": state["state_version"]}
        if draft:
            context["text"] = {"path": f"/drafts/{draft}"}
        return button(id, label, action, active and enabled, action == "select", **context)

    def feedback(id, rid=None, refinement=False):
        key = rid or "overall"
        field = node(
            id + "-input",
            "ReviewInput",
            label="Refinement feedback" if refinement else "Concept feedback" if rid else "Overall feedback",
            value={"path": f"/drafts/{key}"},
            disabled=not active,
            onChange=event(
                "draft", revision_id=rid or "", view_id=direction, text={"path": f"/drafts/{key}"}
            ),
        )
        actions = [decision(id + "-send", "Send feedback", "feedback", rid, key)]
        if refinement:
            actions.append(decision(id + "-correct", "Correct brief", "brief_correction", rid, key))
        return layout(
            id,
            [field, layout(id + "-actions", actions, "actions")],
            "stack" if refinement else "details",
            "Feedback on this concept" if rid else "Overall feedback / combine ideas",
        )

    def about(rev):
        children = []
        for key, label in (
            ("approach", "Approach"),
            ("tradeoff", "Tradeoff"),
            ("invariants", "Preserved behavior"),
            ("assumptions", "Assumptions"),
            ("mocked", "Simulated behavior"),
        ):
            if value := rev.get(key):
                prefix = rev["id"] + "-" + key
                children.extend(
                    [
                        text(prefix + "-label", label, "h4"),
                        text(prefix, "\n".join(value) if isinstance(value, list) else value),
                    ]
                )
        return layout(rev["id"] + "-about", children, "details", "About this direction")

    def prototype(rev, prefix):
        review = rev.get("review", {})
        return node(
            prefix,
            "PrototypePreview",
            revisionId=rev["id"],
            title=rev["name"],
            width=review.get("viewport", {}).get("width", 1280),
            height=review.get("viewport", {}).get("height", 900),
            colorScheme=review.get("color_scheme", "light"),
            onExpand=event("preview", revision_id=rev["id"]),
        )

    tabs = [
        node(
            "tab-compare",
            "ReviewTab",
            label="Compare concepts",
            selected=direction == "compare",
            action=event("navigate", direction_id="compare"),
        )
    ]
    for did in chosen:
        rev = next(r for r in revisions.values() if r["direction_id"] == did)
        tabs.append(
            node(
                "tab-" + did,
                "ReviewTab",
                label=rev["name"],
                selected=direction == did,
                action=event("navigate", direction_id=did),
            )
        )
    root = [layout("tabs", tabs, "tabs", "Exploration workspaces")]
    if not active:
        root.append(
            text("lifecycle", f"Exploration {state['lifecycle']}. Retained work is read-only.", "caption")
        )
    root.append(
        layout(
            "brief",
            [text("brief-text", (state.get("brief") or {}).get("intent") or state["context"])],
            "details",
            "Exploration brief",
        )
    )
    # Diagnostics may change without a design state_version change. Read them on every projection.
    progress = []
    for op in state["operations"].values():
        progress.append(f"{op['kind'].replace('_', ' ')}: {op['state'].replace('_', ' ')}")
        for q in op.get("questions", []):
            if q["state"] == "pending":
                key = q["id"]
                root.append(
                    layout(
                        "question-" + key,
                        [
                            text(key + "-prompt", q["prompt"], "h3"),
                            text(key + "-why", q["why_needed"]),
                            node(
                                key + "-input",
                                "ReviewInput",
                                label=q["prompt"],
                                value={"path": f"/answers/{key}"},
                                disabled=not active,
                            ),
                            button(
                                key + "-answer",
                                "Answer",
                                "answer",
                                active,
                                operation_id=op["id"],
                                question_id=key,
                                text={"path": f"/answers/{key}"},
                            ),
                        ],
                        "panel",
                    )
                )
        if op["kind"] == "explore":
            for candidate in client.operation_diagnostics(exploration_id, op["id"])["diagnostics"].get(
                "candidates", []
            ):
                progress.append(
                    f"{candidate['lens']['question']} · {candidate['provider']} · {candidate['status']}"
                )
    root.append(
        layout("progress", [text("progress-text", "\n".join(progress))], "details", "Generation status")
    )
    current_rid = None
    if direction == "compare":
        root.extend(
            [
                text("compare-title", "Compare concepts", "h2"),
                text(
                    "compare-help",
                    "Try a concept at its original proportions, or mark two for side-by-side comparison.",
                ),
                layout(
                    "overall",
                    [
                        text("overall-title", "Feedback on the whole exploration", "h3"),
                        text("overall-help", "What is missing across these ideas? What would you combine?"),
                        feedback("overall-feedback"),
                    ],
                    "overall",
                ),
                layout(
                    "comparison",
                    [
                        text("compare-count", f"{len(comparing)} of 2 concepts marked for comparison"),
                        button(
                            "compare-open", "Open side-by-side comparison", "compare", len(comparing) == 2
                        ),
                    ],
                    "actions",
                ),
            ]
        )
        cards = []
        for rev in revisions.values():
            if rev["parent"]:
                continue
            rid = rev["id"]
            prov = rev.get("provenance", {})
            thumb = node(
                rid + "-thumbnail",
                "RevisionThumbnail",
                revisionId=rid,
                title=rev["name"],
                action=event("preview", revision_id=rid),
            )
            content = [
                text(rid + "-name", rev["name"], "h3"),
                text(
                    rid + "-question", rev.get("task_model", {}).get("user_question") or rev["approach"], "h4"
                ),
            ]
            if overlooked := rev.get("task_model", {}).get("overlooked_need"):
                content.append(text(rid + "-reveals", "Reveals: " + overlooked))
            content.extend(
                [
                    text(
                        rid + "-provenance",
                        " · ".join(str(prov[k]) for k in ("provider", "model") if prov.get(k)),
                        "caption",
                    ),
                    about(rev),
                ]
            )
            if rev["superseded"]:
                content.append(
                    text(rid + "-superseded", "Superseded draft · unavailable for selection", "caption")
                )
            choose = (
                button(rid + "-choose", "Open workspace", "navigate", direction_id=rev["direction_id"])
                if rev["direction_id"] in chosen
                else decision(
                    rid + "-choose", "Choose this direction", "select", rid, enabled=not rev["superseded"]
                )
            )
            content.extend(
                [
                    layout(
                        rid + "-actions",
                        [
                            button(rid + "-open", "Open preview", "preview", revision_id=rid),
                            button(
                                rid + "-compare",
                                "Remove from comparison" if rid in comparing else "Mark for comparison",
                                "mark",
                                revision_id=rid,
                            ),
                            choose,
                        ],
                        "actions",
                    ),
                    feedback(rid + "-feedback", rid),
                ]
            )
            cards.append(layout(rid + "-card", [thumb, layout(rid + "-content", content, "content")], "card"))
        root.append(layout("gallery", cards or [text("preparing", "Preparing your alternatives.")], "grid"))
    else:
        branch = [r for r in revisions.values() if r["direction_id"] == direction]
        current = next((r for r in reversed(branch) if not r["superseded"]), branch[-1])
        rev = next((r for r in branch if r["id"] == view.get("revision_id")), current)
        current_rid = rev["id"]
        options = [{"value": "", "label": "Latest version"}] + [
            {
                "value": r["id"],
                "label": f"Version {i + 1} · {r['kind']}" + (" · superseded" if r["superseded"] else ""),
            }
            for i, r in enumerate(branch)
        ]
        root.append(
            layout(
                "workspace-heading",
                [
                    text("workspace-title", branch[0]["name"], "h2"),
                    node(
                        "versions",
                        "RevisionPicker",
                        options=options,
                        value=view.get("revision_id") or "",
                        label="Version history",
                    ),
                    button(
                        "focus",
                        "Show refinement panel" if view.get("focused") else "Focus prototype",
                        "focus",
                    ),
                ],
                "actions",
            )
        )
        rid = rev["id"]
        side = [
            text("version-label", "Latest version" if rev == current else "Earlier version", "caption"),
            about(rev),
            text("refine-title", "Refine this version", "h3"),
            feedback(rid + "-refinement", rid, True),
            text("feedback-title", "Your feedback", "h3"),
        ]
        history = [
            d
            for d in state["decisions"]
            if d.get("text") and (not d["revision_id"] or any(r["id"] == d["revision_id"] for r in branch))
        ]
        side.extend(
            layout(
                "decision-" + d["id"],
                [text("decision-text-" + d["id"], d["text"])],
                "details",
                (
                    "Overall"
                    if not d["revision_id"]
                    else f"Version {next(i + 1 for i, r in enumerate(branch) if r['id'] == d['revision_id'])}"
                )
                + " · "
                + d["action"].replace("_", " "),
                expanded=d is history[-1],
            )
            for d in reversed(history)
        )
        if not history:
            side.append(text("no-feedback", "No feedback sent yet."))
        side.append(
            layout(
                "exports",
                [
                    text("export-help", "Download the exact reviewed prototype and implementation handoff."),
                    button(
                        "export-html",
                        "Download HTML",
                        "export",
                        rev["kind"] == "interactive" and not rev["superseded"],
                        revision_id=rid,
                        format="html",
                    ),
                    button(
                        "export-handoff",
                        "Download handoff",
                        "export",
                        rev["kind"] == "interactive" and not rev["superseded"],
                        revision_id=rid,
                        format="handoff",
                    ),
                ],
                "details",
                "Export this version",
            )
        )
        root.append(
            layout(
                "workspace",
                [prototype(rev, "workspace-preview"), layout("sidebar", side, "panel")],
                "focused" if view.get("focused") else "workspace",
            )
        )
    if preview:
        root.append(
            layout(
                "preview-dialog",
                [
                    button("preview-close", "Back to concepts", "close_preview"),
                    layout(
                        "preview-grid",
                        [
                            layout(
                                "preview-cell-" + rid,
                                [
                                    text("preview-title-" + rid, revisions[rid]["name"], "h3"),
                                    prototype(revisions[rid], "preview-" + rid),
                                ],
                            )
                            for rid in preview
                        ],
                        "compare",
                    ),
                ],
                "dialog",
                "Interactive concept preview",
            )
        )
    node("root", "Column", children=root)
    data = {"drafts": dict(saved.get("drafts", {})), "answers": {}}
    return {
        "protocol": PROTOCOL,
        "catalog_id": CATALOG,
        "surface_id": sid,
        "state_version": state["state_version"],
        "lifecycle": state["lifecycle"],
        "cursor": state["cursor"],
        "view": {**view, "direction_id": direction},
        "revision_id": current_rid,
        "sequence": saved.get("sequence", 0),
        "messages": [
            {"version": PROTOCOL, "createSurface": {"surfaceId": sid, "catalogId": CATALOG}},
            {"version": PROTOCOL, "updateDataModel": {"surfaceId": sid, "path": "/", "value": data}},
            {"version": PROTOCOL, "updateComponents": {"surfaceId": sid, "components": components}},
        ],
    }


def dispatch(client, exploration_id, action, request_id, reviewer_id="default", sequence=0):
    """Route an A2UI action through existing public operations; never infer a generation grant."""
    if not isinstance(action, dict) or set(action) - {
        "name",
        "surfaceId",
        "sourceComponentId",
        "timestamp",
        "context",
    }:
        raise PossiblyError("invalid_action", "Supply an A2UI action object.")
    state = client.get_exploration(exploration_id)
    if action.get("surfaceId") != surface_id(state):
        raise PossiblyError("stale_surface", "This review belongs to another exploration or active period.")
    name, context = action.get("name"), action.get("context", {})
    if not isinstance(context, dict):
        raise PossiblyError("invalid_action", "Action context must be an object.")
    allowed = {
        "draft": {"view_id", "revision_id", "text"},
        "select": {"revision_id", "expected_state_version"},
        "reject": {"revision_id", "expected_state_version"},
        "feedback": {"revision_id", "expected_state_version", "text"},
        "brief_correction": {"revision_id", "expected_state_version", "text"},
        "export": {"revision_id", "format"},
        "answer": {"operation_id", "question_id", "text"},
    }
    if not isinstance(name, str) or name not in allowed or set(context) - allowed[name]:
        raise PossiblyError("invalid_action", "Unsupported review action or context fields.")
    for key in ("revision_id", "operation_id", "question_id", "text", "view_id", "format"):
        if key in context and not isinstance(context[key], str):
            raise PossiblyError("invalid_action", f"{key} must be text.")
    if context.get("format", "html") not in {"html", "handoff"}:
        raise PossiblyError("invalid_action", "Choose html or handoff export.")
    rid = context.get("revision_id") or None
    if name == "draft":
        return client.save_review_state(
            exploration_id,
            view_id=context.get("view_id", "compare"),
            revision_id=rid,
            draft=context.get("text", ""),
            reviewer_id=reviewer_id,
            sequence=sequence,
            request_id=request_id,
        )
    if name in {"select", "reject", "feedback", "brief_correction"}:
        if type(context.get("expected_state_version")) is not int:
            raise PossiblyError("invalid_action", "A decision requires its reviewed state version.")
        result = client.record_decision(
            exploration_id,
            rid,
            action=name,
            text=context.get("text", ""),
            expected_state_version=context["expected_state_version"],
            request_id=request_id,
        )
        if name == "select":
            result = {**result, "view": {"direction_id": state["revisions"][rid]["direction_id"]}}
        return result
    if name == "export":
        return client.export(exploration_id, rid, request_id=request_id)
    if not all(
        isinstance(context.get(k), str) and context[k].strip()
        for k in ("operation_id", "question_id", "text")
    ):
        raise PossiblyError("invalid_action", "An answer needs operation, question, and nonempty text.")
    return client.answer(
        exploration_id,
        context["operation_id"],
        context["question_id"],
        context["text"],
        request_id=request_id,
    )
