# Optional MCP and MCP Apps adapter

Possibly remains a library-first Smart Tool. This optional adapter uses the official
MCP Python SDK 2.x and MCP Apps SDK 2.x; it adds no dependency on a particular host.
The normal library and CLI do not import MCP or require it to be installed.

## Install and connect

```sh
uv tool install --python 3.12 'possibly[mcp] @ git+https://github.com/robotdad/possibly'
possibly-mcp --storage /absolute/path/to/possibly-state
```

Configure that command and argument array as a **stdio MCP server** in your host.
For example, this conventional client configuration is equivalent:

```json
{
  "mcpServers": {
    "possibly": {
      "command": "possibly-mcp",
      "args": ["--storage", "/absolute/path/to/possibly-state"]
    }
  }
}
```

The host chooses the process environment and access to this store. Use separate
stores/processes for different trust boundaries. This is not an unauthenticated
HTTP service. No browser or loopback viewer service is started by the adapter.
The same retained store can be inspected through the existing public library/CLI.

Without `--model-env`, reading state, decisions, drafts, exports and cleanup work,
but generation is rejected before acceptance. To authorize generation, add
`--model-env` and optionally `--provider`, `--model`, and `--reasoning-effort`.
Only supply the provider environment variables you intend this tool to use.
Provider-owned OAuth behavior remains the behavior documented in `providers.md`.
Install Chromium using the normal Possibly setup before model-backed generation.
The host's conversation model is not automatically used by this server.

## Discovery and shared control

`tools/list` provides typed JSON Schemas for `possibly_start`,
`possibly_get_exploration`, `possibly_get_operation`, `possibly_wait_operation`,
`possibly_read_changes`, `possibly_open_review`, `possibly_save_review_state`,
`possibly_acknowledge_review_intent`, `possibly_review_snapshot`,
`possibly_get_revision`, `possibly_read_artifact`, `possibly_record_decision`,
`possibly_make_interactive`, `possibly_refine`, `possibly_answer`,
`possibly_finalize_operation`, `possibly_operation_diagnostics`, `possibly_export`,
`possibly_read_export_chunk`,
`possibly_finish`, `possibly_stop`, `possibly_wait_cleanup`, `possibly_reopen`,
`possibly_resume_operation`, `possibly_reactivate_operation`,
`possibly_provider_settings`, `possibly_configure_provider`,
`possibly_provider_models`, `possibly_test_provider`, and
`possibly_provider_login`, `possibly_start_provider_job`, and
`possibly_provider_job`.
`possibly_status` reports whether model access was explicitly bound.
Discovery marks `possibly_finish` and `possibly_stop` as destructive lifecycle
operations; all other annotations retain their operation-specific read-only status.

Every review control invokes those same model-visible tools. No app-only business
actions or host-private endpoints exist. Grants have explicit action lists, bounded
turns/deadlines/tool/model calls, and no implicit prototype continuation in the UI.
The grant is not a dollar ceiling. A draft or recorded feedback does not itself
start generation. The library's optional one-use continuation remains available
when a calling agent explicitly supplies it in its initial grant.

Tool results carry a meaningful JSON text fallback and structured envelope:
`{operation, exploration_id, result}`. Results retain the library's receipt,
operation, revision and state-version identities. Use a new request ID for new
intent, and reuse one only for an exact retry. Stale decisions fail visibly; they
are not retargeted. There is no exactly-once guarantee for external model calls
across crashes. Use operation diagnostics before authorizing recovery.

The initial adapter accepts text context at start. Material references, fan-out
planning, and direct runner driving remain available through the library/CLI; they
are not yet exposed through MCP. Provider settings, bounded model discovery,
connection test, and provider-owned login are exposed through the same public
library adapter as the native settings dialog. They require the MCP process's
existing explicit `--model-env` authority where applicable and a separate explicit
per-action request. Provider setup tools are App-visible rather than model-visible;
that visibility is enforced by the trusted MCP host, not cryptographic proof of a
human click. A raw client accepted by that same trusted stdio host is therefore not
an untrusted-model bypass. The App never gains credentials, a token, or authority
to change another process. Provider jobs and device-flow progress are retained
against the exploration; opening settings never starts one. A host with no Apps
support can use all exposed tools normally. No MCP sampling, subscriptions or MCP
Tasks are negotiated yet; native operation handles and deterministic polling are
explicit. An owned runner may continue after the MCP connection or view closes.
Use `possibly_stop` and inspect cleanup to stop it.

## Portable review view

Tools advertise `_meta.ui.resourceUri: "ui://possibly/review"`, and `resources/read`
returns self-contained `text/html;profile=mcp-app`. Hosts negotiate the standard
`io.modelcontextprotocol/ui` extension and render it through their normal Apps
bridge. The HTML bundles the official SDK; end users need neither Node nor a CDN.
It is built from the native dashboard document and controller, with only a narrow
MCP public-library transport substituted for the loopback HTTP transport. It
therefore retains native comparison cards, thumbnail/preview sizing, side-by-side
comparison, direction workspaces, version history, feedback/correction, export
eligibility, provider settings, and appearance controls rather than presenting a
separate reduced workflow.

Before mounting, a host calls `possibly_open_review` and passes that actual result
to the App. The retained result supplies a review identity: omitting one creates a
separate view; an existing identity is reused only when the caller explicitly
chooses it. The App can turn a generic `possibly_get_exploration` initial result
into a new public attachment before the native controller starts, but that fallback
cannot recover an opaque remount. Review identity is not an authorization credential.

The view polls only deterministic state/artifact reads. It hydrates displayed
roots/history with bounded concurrent reads and lazily retrieves a newly opened
history entry. Artifacts are capped at 1 MB UTF-8 and thumbnails are bounded before
snapshot serialization. An oversized artifact reports the bound rather than silently
transmitting it. Export metadata is returned first; the App reconstructs exact
HTML/handoff through public 64-KB `possibly_read_export_chunk` reads, rather than
receiving an unbounded result. Native local light/dark choices override host
appearance. In System mode, the adapter uses the host's resolved light/dark
context and falls back to media preference; partial host-context updates merge
without remounting the native controller or discarding drafts. Unsent drafts are
context, not generation authority. Opaque App frames do not assume durable web
storage: the adapter uses a declared retained review identity and public
review-state. Pending mutations retain their original ID and full payload, are
replayed only through the library receipt path after transport loss, and are never
acknowledged by a state read or matching decision text. A definite domain rejection
clears only that request. Closing the view does not stop an exploration; standard
`ui/resource-teardown` flushes retained pending drafts and stops the App's own
timers/listeners without cancelling domain work.

Generated prototypes live in a separate `sandbox="allow-scripts"` opaque iframe.
They have no MCP App SDK or control bridge. The library's artifact CSP denies
network access, and the App SDK validates parent-window messages. The resource
requests no network domains or browser permissions; it requests only `blob:`
nested frames for isolated prototypes. Hosts may refuse that capability and still
retain all textual tools. Runner URLs, access tokens and private log paths are
removed from adapter results, including the private URL on a
`presentation_available` observation. Other caller-provided URLs remain visible.
A tool result never grants generated content access to a presenter token or provider
credentials.

Export produces blob download links. A host that disallows downloads may use
`possibly_export` followed by bounded `possibly_read_export_chunk` reads to save the
same retained HTML and JSON handoff. Export is provider-free and does not implicitly
finish the exploration.

## Develop and verify

```sh
uv sync --extra dev --extra mcp
npm ci --prefix mcp-app
npm run build --prefix mcp-app
uv run pytest tests/test_mcp.py tests/test_mcp_browser.py -q
```

Commit `src/possibly/mcp_app.html` when changing view sources; the package ships this
built document. The independent browser fixture uses the official `AppBridge`, not
a particular product, and verifies shared state, draft targets and prototype
isolation. MCP tests cover stdio reconnect, schema limits, retry receipts, stale
conflicts, lifecycle retention and provider-free behavior. Tests use scripted
intelligence and spend no model tokens. They do not certify live provider or
Chromium generation quality.
