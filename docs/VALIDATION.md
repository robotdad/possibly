# Validation — 2026-09-15

## Automated checks

- 23 local tests: library round trip, retry/idempotency, one-use continuation,
  revision conflicts, accepted corrections, late publication, question/answer identity,
  reopening/reactivation, interruption/cleanup, partial artifacts, material resolution,
  provider-free help, CLI export, offline browser execution, dashboard selection and
  refresh, origin/token checks, owned subprocess lifecycle, and expired queued grants.
- Upstream Amplifier Smart Tools conformance kit: 16 PASS, 0 FAIL, 0 SKIP.
- Ruff lint and formatting checks pass.
- Source distribution and wheel build. Wheel includes SMART_TOOL.md, caller guide,
  library, CLI, and dashboard HTML.

## Live Amplifier Agent trial

Used a synthetic community-garden scheduling brief with the explicitly authorized
Anthropic environment provider. No real user documents were supplied.

| Operation | Outcome | Wall time |
|---|---|---:|
| Explore | Three visual approaches: shift claiming, availability matching, rotation/swaps | 167 s |
| Make interactive | Clickable shift-claiming prototype | 125 s |
| Refine | Shorter action labels and clearer day/volunteer confirmation | 77 s |
| Export and finish | Standalone HTML, handoff, retained revisions and successful cleanup | Deterministic |

The embedded engine wrote candidate artifacts, exercised them with offline Chromium,
received rendered screenshots as image blocks, and submitted structured output through
its tool interface. A separate rendering of the final export reported no JavaScript
errors or blocked requests. The synthetic selection is explicitly marked as automated
validation, not human design approval.

The first compatibility probe caught a session_cwd type mismatch; the integration now
passes Path objects. An initial generation returned unstructured final text; submit_result
now makes structured output a tool action. These failures were explicit and did not
produce a successful artifact receipt.

## What this does not establish

These checks do not ratify the draft human experience contracts. Useful alternatives,
faithful reference transfers and successful fresh-agent implementation still require
approved scenario reviews. The measured trial is one scenario, not a latency benchmark.
Only macOS was exercised. Remote/multi-host operation and production reliability are
not claimed.

## Direction workspace update

26 tests pass, including real Chromium checks for branch tabs, revision-following,
feedback retention, HTML export, saved appearance preference, system light/dark
changes, and existing authentication/isolation checks. All 16 spec conformance
checks pass. Saved RoomFix content was visually reviewed in the new dashboard;
a 390px viewport check found no dashboard horizontal overflow. Theme guidance
for future model-generated prototypes has not yet had a fresh live model trial.

## Review snapshots and multi-screen previews

27 tests pass, including autosaved unsent feedback visible to library callers,
out-of-order save protection, exploration-wide feedback, preview expansion, and
existing dashboard/contract checks. All 16 conformance checks pass. Expanded
previews and dashboard width at 390px were checked in Chromium. Multi-screen
concepts use local navigation within the exported HTML, not separate remote pages.

## Performance implementation

- 38 tests pass, including exact/atomic edits, hash-bound evidence, inherited asserted
  flow regression checks, inspection cache invalidation, provider request limits,
  screenshot injection, streaming/nonstreaming terminal submission, stale checkpoint
  rejection and deterministic/idempotent finalization without a configured provider.
- `examples/performance_probe.py` exercises the real installed Amplifier engine/loop
  and Chromium with a scripted offline provider: two requests, two tools, no full HTML
  output, screenshot delivered in request two, no post-submission prose/review call.
  This verifies integration; it does not measure live provider speed or visual quality.
- Five synthetic complete-checkpoint finalizations: 7.04, 6.01, 4.25, 4.68, 7.80 ms
  (median 6.01 ms). Browser/model work was completed before this timed section.
- All 16 Smart Tools conformance checks pass. Ruff checks and formatting pass.
- No paid/live model benchmark was run in this implementation pass. Provider-internal
  HTTP retries are included in request duration, not independently instrumented.
- Old drafts lacking submitted metadata and hash-bound evidence are not automatically
  recoverable. Finalization explicitly identifies missing checks; new model repair
  remains separately authorized work.


## Live pinball performance trial (2026-09-15)

Completed explore → select Collection First → make interactive → Stern-inspired refine → export → finish,
then reopened the same pre-styling revision for a targeted refinement/export/finish comparison.
Provider: Anthropic, explicitly pinned `claude-sonnet-5`; earlier trials used that installed default.
Retained evidence: `examples/generated/pinball-perf/state`, operation diagnostics and checkpoints.

| Operation | Wall time | Result |
|---|---:|---|
| Three integrated concepts | 411.66 s | Completed; earlier comparable trial timed out at 600 s |
| Make selected concept interactive | 25.04 s | Reused HTML; score-entry assertions passed |
| First Stern-inspired refinement | 145.86 s | Inherited score flow preserved; exported |
| Repeat with concise CSS override guidance and native select support | 127.51 s | Exported; additional mocked search/add and dropdown flow exercised |
| First export CLI including process startup | 0.075 s | Deterministic, no provider call |

The second style trial used the same starting artifact/model but added interaction checks, so this is
an indicative comparison, not a controlled benchmark. It was 12.6% faster and emitted 12,798 output
tokens versus 16,314 (21.6% fewer). It still required a selector retry. Generation dominates the
operation time; browser and startup costs are small. Exploration still overbuilds: three artifacts
were approximately 22–26 KB despite representative-screen guidance.

Implemented follow-up: native `select` inspection action with value-based selection and regression
test; style instructions prefer compact overrides rather than repeating entire stylesheets.
Full suite: 39 passed; Ruff passed; smart-tool conformance: 16 passed.

Both exports are byte-identical to their respective validated checkpoint artifacts. The saved
screenshots show the higher scores and venues; assertions verify the original machine's updated
best, mocked Xenon addition, dropdown choice, and simulated photo-confirmation visibility. The
second extended flow does not assert history after its final save (the screenshot shows the updated
collection card). Theme switching has implementation/static evidence, not comprehensive visual
assertions in every mode. Direct local-file opening in the in-app browser was blocked by browser
security policy; it was not bypassed. Verification relies on retained tool-owned offline browser
checks, screenshot review and byte equality, not a separate manual exported-file browser run.

Preferred export: `examples/generated/pinball-perf/export-improved/prototype.html`, with
`handoff.json` and `preview.png`. Original style trial retained under `export/`. Both sessions were
finished, cleanup reported success. These remain mockups: placeholder cabinet art, simulated
Pinside/photo recognition, and in-memory state (reload resets scores). The visual quality is modest;
this trial establishes the caller/refinement/export flow and performance evidence, not a finished app.


## Provider configuration and settings (2026-09-15)

Upgraded Amplifier Agent from v0.12.0 to v0.17.0, using its nine-provider catalog.
Added environment defaults (OpenAI default), process-only overrides, native credential
presence reporting, CLI/library connection tests and explicit provider login, dashboard
settings/test/login progress, and accessible system/light/dark icon control.
No Possibly configuration/credential file is written; provider-owned OAuth caches remain allowed.

Live environment-configured providers all passed connection tests and real Agent
integration tests (existing score artifact, browser click+assertion, image review,
structured submission; two provider calls each). Observed default models:
OpenAI gpt-5.6-sol, Anthropic claude-sonnet-5, Gemini gemini-3.7-flash.
Retained live smoke evidence: examples/generated/provider-smoke/<provider>/.

See src/possibly/docs/providers.md for timings, environment precedence, connection-test
scope and login instructions. No live ChatGPT/Copilot authorization was attempted because
neither had configured credentials; auth progress/refresh are tested with isolated doubles.
ChatGPT's auth module was also resolved through the real Agent module resolver without
mounting an unauthenticated provider or starting login. This avoids the validation noise
observed when trying to mount before first login.

Validation: full suite passed (48 tests); focused dashboard/provider checks passed after
the final accessibility change, and an additional Copilot-cache redaction test passed
(49 tests total). Ruff, all 16 conformance checks and the offline
real-Engine terminal-submission probe passed on Agent v0.17.0.

## 2026-09-15 diversity pass

Three household/pinball rounds (18 candidate attempts), two full export flows,
20 offline responsive/theme flow replays, 60 tests, 16 conformance checks and
the offline Amplifier probe. See [DIVERSITY-EVALUATION.md](DIVERSITY-EVALUATION.md)
for per-model measurements, failed attempts, critiques and limitations.
