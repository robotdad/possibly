# Deckbox review: lessons for Possibly

Reviewed 2026-09-15. Reference: a local `deckbox-7-items` reference folder (seven HTML files).
Source/code review and static dependency checks only; the reference's claims about past
browser QA/model provenance were not independently verified. No new model calls were made.

## What is actually supplied

`index.html` is a static comparison gallery for six Converge concepts. The six candidate
files are Astra / Working Edition, Luna Max / Decision Ledger, Terra / Agreement Desk,
Fable / Signed Page, Opus / Sheet and Margin, and Gemini / Living Accord. No orchestration
source, common generation prompt, provider receipts, or QA/provenance files are included.
The footer explicitly says named provider instances were not confirmed and attribution
coverage varies. Treat the labels as author/model labels, not verified provider identities.

## Borrow for the dashboard

1. **Compact comparison cards.** Thumbnail, descriptive concept title, small model label,
   one clear UX distinction and one tradeoff. Collapse reviewer detail. This supports
   side-by-side scanning without six running embedded apps or walls of explanation.
2. **Choose any two for an interactive comparison.** The reference loads two iframes only
   after Compare, supports full-width opening, and unloads them on Clear. Put comparison
   controls near the gallery rather than forcing a scroll to the bottom. Retain Possibly's
   sandboxed srcdoc previews; the reference iframes have no sandbox attribute.
3. **Keep comparison and refinement distinct.** Choosing a concept opens the existing
   dedicated Possibly workspace, with full-size multi-screen navigation and export there.
   A thumbnail is a gallery aid, not a replacement for the full-fidelity working preview.
4. **Collapsible feedback side panel.** Opus's peek/half/full manager margin is a useful
   pattern for showing feedback and revision context without permanently shrinking the
   prototype. Avoid hiding essential actions/evidence behind the collapsed state.
5. **Visible revision changes.** Astra's before/after editions and Fable's contextual
   threads suggest a compact 'You requested / Changed / Preserved / Still mocked' summary,
   tied to the exact revision and feedback. Preserve unsent draft visibility and autosave.
6. **Honest readiness states.** The index marks Gemini as a limited, non-equivalent concept.
   Surface generating, ready, partial, failed, and checks-not-complete states separately.
   Automated checks and model review must not be presented as human approval.

Keep the current system/light/dark support; the reference index is explicitly light-only.
Do not copy the Converge agreement/ratification domain language into Possibly unnecessarily.

## Recommended provider fan-out

- Resolve one common brief and common central-flow acceptance criteria first.
- Offer an automatic, bounded diverse exploration: normally one concept each from up to
  three configured/capable providers, using the provider/model settings already available.
  Fewer available providers should still work, with distinct UX approaches on one model.
- With Copilot, discover currently accessible models through its provider and select a
  representative set of model families. Keep the transport provider (`github-copilot`)
  distinct from the actual model ID/family. Do not hard-code assumed entitlements.
- Give each worker one concept, an explicit organizing approach, the same required scope,
  and the same validation criteria. Avoid asking every worker for another three concepts.
- Stream each completed candidate into the gallery independently. A slow/failed worker
  must not discard other candidates. Retain incomplete artifacts with clear status.
- Budget the whole batch as well as each worker: candidate count, concurrency, model/tool
  call limits, total spend allowance if added, deadline and cancellation. Parallel work can
  reduce elapsed time but may cost more; this is not itself a measured performance win.
- Possibly currently serializes engine work with a process-global lock. Use isolated worker
  processes for genuine parallel Agent sessions, with parent-owned state publication,
  cancellation and durable receipts. Do not remove that lock and assume threads are safe.
- Record exact provider/model, instruction variant, base revision, timing, usage and checks
  on each candidate. Label this design exploration, not a provider quality benchmark:
  intentionally varied UX directions and unequal completed scope confound rankings.
- Refine the chosen candidate on its existing model by default. Offer deliberate model
  switching with the current HTML and inherited checks rather than rerunning the fan-out.

This is a proposed next implementation, not existing Possibly behavior.

## Self-containment: confirmed omissions and export requirements

The supplied index references these six missing files:
`qa/comparison/{astra,luna-max,terra,fable,opus,gemini}-direction.png`.
It also links to missing `research/provenance.json` and `research/build-completion.json`,
and six Raw file links point at a separate private hostname. The six candidate HTML files
are present. Thus the folder is not a complete portable gallery, and the index is not a
single-file export. The individual candidates have mostly inline HTML/CSS/JS/SVG; do not
misdescribe the missing gallery thumbnails as remote images inside every candidate.

For Possibly:

- Embed gallery thumbnails as data URLs or include every dependency in an explicitly
  complete multi-file bundle. For a promised standalone HTML, embed everything it needs.
- Keep original image bytes out of model-generated text: a host asset step should attach
  verified image data deterministically. This avoids spending model output tokens on base64.
  Keep placeholders explicitly mocked; do not pretend they are actual machine photographs.
- Export the actual reviewed artifact plus its own handoff/provenance, not links back to
  the temporary dashboard, another machine, or absent QA folders.
- Validate the exported deliverable from a clean directory with network disabled, not only
  from a running development session or browser cache. Check image decode/natural size and
  fonts as well as JS/network errors. A loaded page is not proof that its images rendered.
- Preserve sandbox isolation and handle unavailable storage gracefully. Several reference
  candidates have corrupt/unavailable localStorage recovery, worth carrying into generated
  mocks where persistence is explicitly requested.

Possibly's current static validator rejects this index's missing relative assets. Five of
six individual candidate files pass its static standalone check; this is not browser QA.
Fable revealed a validator false positive: the global CSS `url(...)` regex also matches
JavaScript `createObjectURL(blob)` and `revokeObjectURL(a.href)`. Scope CSS checks to actual
styles instead of scanning JavaScript. Record this as a follow-up, not evidence that Fable
loads external CSS. Keep runtime network denial and visual/image checks as separate layers.

## Suggested order

1. Compact gallery, embedded thumbnails, explicit two-up comparison and collapsible workspace feedback.
2. Bounded multi-provider fan-out with provenance, independent completion and shared acceptance scope.
3. Export-bundle completeness checks and targeted asset-decoding checks; fix CSS scanning false positives.
