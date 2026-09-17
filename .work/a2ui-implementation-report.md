# A2UI review workspace — implementation and trial report

Branch: `feature/a2ui-review-workspace`

## What is implemented

The dashboard now uses an actual A2UI v0.9.1 MessageProcessor and Lit renderer,
with a shared deterministic Python presenter and an explicit review catalog.
Concept comparison, task descriptions, selection, feedback, correction, questions,
revision history, progress, preview sizing/focus, and export are wired through it.
Provider settings and appearance remain host-level controls.

The public library and generated CLI help expose `review_catalog`, `review_surface`,
and `review_action`. Existing domain methods still own all durable mutations,
idempotent receipts, state-version checks, and generation authority. The renderer
contains no default backend address or credentials; hosts inject its IO callbacks.

The six custom widgets handle review layout, draft input, workspace tabs, revision
selection, thumbnail access, and isolated prototype previews. Native text rendering
implements the standard Text schema; Button/Column/Row/Card use the upstream catalog.
The built-in viewer and an independently bridged test host use the same presenter
and bundled renderer. `examples/embedded_review.py` is an executable second host.

Generated prototypes are still self-contained HTML. The separately recorded idea
of generating A2UI prototypes has not been implemented in this pass.

## Important behavior

- Routine surface reads contain neither prototype bytes nor thumbnails, grants,
  runner URLs, provider configuration, or credentials. Artifacts load on demand.
- A retained surface and component diffs preserve an interactive iframe and local
  drafts during background changes. View changes during a poll await the new view
  before recording review context.
- Drafts autosave with reviewer sequences; submission does not clear newer typing.
  A stale submission reports rejection and keeps the text for review and retry.
- Selection and feedback keep exact revision targets. Navigation is not selection.
- The preview preserves captured viewport/theme and uses a script-enabled opaque
  sandbox plus restrictive CSP. Host tokens never enter the preview document.
- Disconnecting/unmounting a host stops its polling, not the exploration. Epoch
  changes invalidate earlier surfaces. Retained work remains available after stop.
- Feedback does not wake a caller or authorize generation. Existing one-use
  continuations and explicit library grants keep their original semantics.

## Validation

- Final full Python/browser suite: **69 passed**, including a delayed
  poll/navigation regression and stale-form preservation/retry.
- Upstream A2UI v0.9.1 schema checks cover gallery, comparison, workspace, history,
  correction, and pending-question projections, including child-reference validity.
- Smart Tools conformance: **16 passed, 0 failed, 0 skipped**.
- Scripted real Agent performance probe passed without model requests: artifact
  inspection, screenshot in the next provider call, and terminal submission.
- Ruff checks and formatting, Prettier checks, and whitespace checks pass.
- Built a wheel and installed it outside the checkout. Catalog reads and the
  bundled renderer are present and work without a frontend build.
- Browser bundle is approximately **264 KB**, plus catalog and license assets.
  No CDN calls or Node runtime are required to view a workspace.

## Live provider round trips

Brief: a household repair planner with the same issue, urgency, time/cost,
DIY/professional, dependencies, and progress scope across three task models.
Providers were selected through the existing auto fan-out plan; the reported model
names below are observed provider provenance, not assumptions about defaults.

| Provider / observed model | Task representation | Initial generation | Interactive + refinement + UI export |
|---|---|---|---|
| Gemini / `gemini-3.7-flash` | Room and subsystem context/history | 38.4 s, 4 model calls | Passed |
| OpenAI / `gpt-5.6-sol` | Attention queue organized around the next useful action | 71.2 s, 3 model calls | Passed |
| Anthropic / `claude-sonnet-5` | Weekend capacity planning under time and budget | 145.9 s, 7 model calls | Passed |

For each provider, the trial selected its concept in the A2UI dashboard, requested
an interactive revision with a bounded library grant, submitted feedback through
the UI, refined through the library using the selected provenance, and downloaded
both HTML and JSON handoff through the UI. Downloaded HTML matched the exact
retained final revision. The refinement added an explicit demo-only label while
preserving verified interactions; it was deliberately small so this evaluated
integration continuity rather than an unrelated redesign.

The test also opened side-by-side comparison, captured desktop light/dark and mobile
workspaces, and checked the exported prototypes offline. Across the three exports:
**20 flow checks, 152 passed assertions, zero reported script errors, zero blocked
requests, zero horizontal overflow** at 1280×900 and 390×844 in both themes.
The dashboard recorded **zero page errors**. All live trial runners were stopped;
cleanup succeeded, with retained artifacts left available.

### Failed first batch and cost boundaries

The earlier trial used an 18-call shared generation budget (six calls per candidate).
Gemini completed; OpenAI and Anthropic exhausted their allowances during generation
and review. Possibly preserved the partial result. That runner was stopped cleanly.

The second batch used a 36-call shared budget and a 360-second deadline. Each of
six continuation operations had a 12-call, 24-tool-call, 240-second grant. All
completed within those limits. No unbounded retry loop or automatic fresh grants
were added to the product.

Across both trials, retained diagnostics record **46 model requests**, approximately
**464,523 input tokens and 70,794 output tokens**. These are provider-reported totals;
cache accounting differs between providers and no dollar-cost calculation is claimed.
The successful batch and its six continuations account for 31 of those requests.

## Where to look tomorrow

- `src/possibly/presentation.py`: deterministic UI projection and action routing.
- `web/review.js`, `web/catalog.js`: renderer, custom components, and host adapter.
- `src/possibly/docs/caller-guide.md`: public integration contract and callback example.
- `examples/embedded_review.py`: a second host with its own authenticated transport.
- `examples/a2ui_roundtrip.py`: opt-in, bounded live regression driver.
- `examples/generated/a2ui-live-roundtrip/roundtrip.json`: retained live evidence.
- The `gemini`, `openai`, and `anthropic` subdirectories of that trial contain each
  HTML export, handoff, and screenshots. Generated trial files remain git-ignored.

To inspect the retained result from the repository root without starting generation:

```sh
uv run python examples/embedded_review.py \
  examples/generated/a2ui-live-roundtrip \
  exp_f1289f51e6ef4213bf3ca758989d7191
```

The command prints a private viewer URL and opens no browser. It can review/export
the stopped exploration. Ctrl-C closes only this example host. Use the ordinary
library reopen/grant flow if you choose to continue generation.

## Findings and remaining limits

1. **The separation is useful.** The second host needs callbacks and styling, not
   copied workflow logic. UI description alone still does not bridge Python into
   another application's process or provide its authorization policy.
2. **A2UI does not eliminate custom components.** A generic renderer needs the
   review catalog implementations, especially the HTML preview. This is a concrete
   consideration for the Smart Tools discussion.
3. **Published APIs need pinning.** This uses Lit 0.10.3 and web_core 0.10.7. Lit
   0.10.4 is deprecated upstream. The upstream schema exporter emitted dangling
   local references, so the build generates expanded schemas with A2UI references;
   independent protocol validation catches this class of defect.
4. **This is a local integration POC.** Authenticated loopback hosting is preserved;
   remote multi-user authentication, cross-user authorization, and a general event
   transport are not added. Reviewer IDs identify drafts, not identities for access.
5. **Polling remains the transport.** Two-second reads produce complete projections;
   the browser applies component diffs. A streaming/event transport can reuse the
   same presenter later. A2UI is not the source of truth for domain state.
6. **Prototype state is intentionally transient.** Background updates preserve it;
   navigating away, choosing another revision, or reloading remounts the prototype.
   Persisted feedback survives reload. Unsubmitted question answers remain local.
7. **Evaluation is bounded.** The three task models differ meaningfully, and their
   declared flows passed, but that is not exhaustive validation of every generated
   control or numeric assumption. Native renderer portability beyond this browser
   component implementation has not been tested.

## Preview follow-up

User review exposed a shadow-DOM styling bug: single-preview dialogs retained two
columns because their single-child selector lived outside the layout component.
Moved the rule into the component and removed the redundant expand button inside
an already-expanded preview. Regression coverage now asserts full content width
from concepts, selected workspaces, and history, including mobile. Final suite:
**70 passed**. Visually verified the corrected retained Gemini/OpenAI previews in
the in-app browser. No additional model calls.
