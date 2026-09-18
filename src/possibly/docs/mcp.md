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
`possibly_read_changes`, `possibly_save_review_state`, `possibly_review_snapshot`,
`possibly_get_revision`, `possibly_read_artifact`, `possibly_record_decision`,
`possibly_make_interactive`, `possibly_refine`, `possibly_answer`,
`possibly_finalize_operation`, `possibly_operation_diagnostics`, `possibly_export`,
`possibly_finish`, `possibly_stop`, `possibly_wait_cleanup`, `possibly_reopen`,
`possibly_resume_operation`, and `possibly_reactivate_operation`.
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
planning, provider login/configuration, and direct runner driving remain available
through the library/CLI; they are not yet exposed through MCP. A host with no Apps
support can use all exposed tools normally. No MCP sampling, subscriptions or MCP
Tasks are negotiated yet; native operation handles and deterministic polling are
explicit. An owned runner may continue after the MCP connection or view closes.
Use `possibly_stop` and inspect cleanup to stop it.

## Portable review view

Tools advertise `_meta.ui.resourceUri: "ui://possibly/review"`, and `resources/read`
returns self-contained `text/html;profile=mcp-app`. Hosts negotiate the standard
`io.modelcontextprotocol/ui` extension and render it through their normal Apps
bridge. The HTML bundles the official SDK; end users need neither Node nor a CDN.
The UI compares retained revisions, previews generated HTML, records selection and
feedback, saves per-revision drafts, starts bounded refinements, answers pending
questions, exports, finishes, stops, and reopens retained work.

The view polls only deterministic state/artifact reads. It preserves the viewed
revision when new ones appear, and it publishes a bounded selection/draft summary
with standard `ui/update-model-context` when the host supports it. Hosts can always
read full domain state through the ordinary tools. Unsent drafts are context,
not generation authority. Closing the view does not stop an exploration.

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

Export produces blob download links. A host that disallows downloads may use the
`possibly_export` tool directly to save its returned HTML and JSON handoff instead.
Export is provider-free and does not implicitly finish the exploration.
Artifact and export results are currently inline; each host's response-size limits
apply. Large media/resource streaming is not part of this first adapter.

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
