# Possibly 0.1 implementation

The intelligence layer is **Amplifier Agent**, embedded through `amplifier_agent_lib.Engine`.
The package pins Agent v0.17.0 and keeps provider setup and model calls behind lazy imports.
The smart-tool-creator's spec/packaging guidance is used, but its Copilot-only scaffold is
not the runtime for this tool.

## Boundaries

- `lib.py`: public exploration API, authority, publication, lifecycle and handoff.
- `store.py`: atomic SQLite state, idempotent receipts and ordered observations.
- `intelligence.py`: scoped Amplifier sessions and write/patch/read/inspect/submit candidate tools. Actual screenshot blocks reach the agent before publication.
- `artifacts.py`: standalone checks, restrictive content policy, offline browser checks.
- `runner.py`: explicitly owned background execution and optional loopback dashboard.
- `help.py`, `SMART_TOOL.md`: library-owned skill/help, capability descriptions and manifest.
- `cli.py`: argument/file/stdin handling and JSON rendering only.

No tool is mounted that can read arbitrary host files, execute commands, delegate, or
submit human decisions. The retained generation workspace contains candidate artifacts, validation checkpoints and diagnostics.
The caller supplies reference contents; URL fetching remains a host resolver responsibility.

## Concrete choices from the draft API

1. Synchronous Python library with JSON-compatible results; async hosts can use a thread.
2. CLI takes a JSON argument object per capability. `--input @path` and stdin are adapters.
3. Explicit host-selected store; no implicit shared conversation or working directory.
4. Foreground execution or an explicitly owned runner. Waiting only observes.
5. Separate `make_interactive` operation for selections without continuation authority.
6. Feedback is durably recorded, then applied only through an explicit `refine` base choice.
7. Brief corrections conservatively supersede all previous visuals and preserve correction text.
8. Retained history and deduplication have no expiry in this version. Snapshot cursors are atomic.
9. Stop/finish fences writes immediately and reports correlated cleanup separately.
10. Returning creates a new active period. Suspended questions require explicit reactivation,
    fresh authority and relevance confirmation; ordinary resume cannot cross that boundary.

## Validation boundaries

Deterministic tests use an explicit fake intelligence adapter; it is never a production
fallback. Browser tests launch real Chromium offline and exercise controls. The external
Smart Tools conformance kit checks packaging/invocation; it does not validate visual quality.
Manual live probes in `examples/` use synthetic material and consume provider tokens.

This is a local POC, not a claim that every draft contract has been ratified. Human scenario
reviews must still establish useful alternatives, recognizable reference transfers, and
successful fresh-agent handoff. Remote authentication, distributed runners, deletion and
retention policies, dollar/token budgets, and automatic recovery of uncertain provider calls
remain outside this release. Runner crashes retain evidence and require explicit handling.

## Development

```sh
uv sync --extra dev --extra anthropic
uv run playwright install chromium
uv run pytest
uv run ruff check src tests examples
uv run ruff format --check src tests examples
```

Run the upstream conformance kit against this checkout after syncing. The descriptor points
to `.venv/bin/possibly` so the checks execute this distribution from a scratch directory.
Installed callers use the ordinary `possibly` executable.

## Direction workspaces

The built-in dashboard separates initial comparison (Explore) from focused direction tabs.
Select decisions retain every opened direction; `selected_revision` remains the most recent
selection for compatibility, not an exclusive winner. Selecting another direction does not
invalidate running work. Brief corrections still invalidate work against the old intent.
Each workspace follows its latest non-superseded revision unless the reviewer explicitly
chooses history, and shows feedback against the exact revision reviewed. Feedback remains
a deterministic decision for the caller; the dashboard does not invent generation grants.
Review versions also opens unselected directions, including completed children of
superseded roots. These workspaces are labeled as previews, and browsing never creates
a select decision. An exact MCP revision entry uses the public retained review/context
operations; only compatible review entry points advertise an initial App resource.
Export downloads the exact displayed interactive revision through the public library.
Dashboard appearance defaults to system preference, with a locally persisted override.
New generated artifacts are instructed to support system themes unless the brief specifies
a fixed appearance; existing artifacts are not rewritten by the dashboard theme control.


## Performance revision

`checkpoints.py` persists artifact hashes, review evidence and validated submissions.
`runtime.py` wraps mounted provider calls to deliver screenshots inline, enforce a
request limit, record numeric usage/timings, and stop after accepted submission.
There is no separate repeated screenshot-review execution loop. `artifacts.py`
provides outcome assertions and allows one browser process to serve isolated checks.
`finalize_operation` is a public, deterministic checkpoint publication operation.
It does not repair artifacts or invent missing review evidence.

Dashboard refresh is a single completion-scheduled cycle shared by the native
document and MCP view. State reads continue at a slower idle cadence so new
caller work can be discovered, while final diagnostics are retained until the
operation changes. Hidden views preserve their frame and drafts and pause reads;
resuming requests one current snapshot. Teardown invalidates pending reads before
clearing timers, so late results cannot restart polling or redraw a closed view.
These are presentation scheduling changes; library capabilities, decision receipts,
grants and generation authority are unchanged.
