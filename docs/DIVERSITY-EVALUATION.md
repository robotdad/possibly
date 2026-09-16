# Task diversity and model trials — 15 September 2026

## Conclusion

Task lenses mattered more than provider count. Explicit domain-specific user questions
produced more useful alternatives than generic triage/context/outcome instructions.
Provider/model diversity adds another source of variation, but does not substitute
for defining distinct tasks. Keep the common brief fixed, then change the organizing
object, first action, decision and completion condition.

Three live passes used both household repairs and pinball: 18 candidate attempts,
13 completed concepts, five bounded failures. Selected concepts continued through
interactive generation, critique, refinement and exact offline export. This is a
small qualitative development experiment, not a controlled model benchmark. Lenses,
prompts, image encoding and models changed between passes, so timings do not isolate
model effects. No price/cost ranking is claimed.

## What the alternatives revealed

| Brief | Representation | Useful discovery | Critique |
|---|---|---|---|
| Repairs | Shared systems and symptom history | Several room-level issues may belong to one discussion/assessment | Initial copy overstated causal certainty and predicted savings; refined to tentative links and sample planning estimates |
| Repairs | Weekend time/budget envelope | Preparation and dependencies can matter more than urgency sorting | Attractive layout; some derived budget/progress values in early concepts were semantically wrong |
| Repairs | Handoff readiness | Evidence, access arrangements and an assigned owner are a separate task before scheduling work | Useful new task, but the model produced a visually generic list |
| Pinball | Active session diary | Stage quick photo/score captures, then explicitly confirm before changing records | Strong fit for noisy, rapid consecutive play; long-term browsing is secondary |
| Pinball | Mastery targets | Pick a reachable personal best and preserve venue context on attempts | Strongest visual hierarchy; initial target gap was hard-coded and mathematically inconsistent |
| Pinball | Venue/discovery | First-play opportunities and local cabinet history differ from global machine records | Interesting lens; some outputs still resembled a collection view with a different heading |

The selected repairs prototype combines shared-context exploration with a gated
handoff checklist. The selected pinball prototype keeps mastery, collection and
plays inside one app, with a Stern-inspired charcoal/red treatment, explicit score
confirmation and corrected target arithmetic. Images are embedded illustrative
cabinet art; Pinside and photo recognition are mocked. These remain bounded
prototypes, not persistent production apps or complete implementations of every
listed workflow.

## Measured generation time

Wall-clock seconds per candidate, including worker startup and review. Each batch
used concurrency 3, a shared 240-second deadline, 18 total model calls and 30 total
tool calls, divided across workers. Two different brief batches ran concurrently.

| Pass | Brief | Gemini | OpenAI | Anthropic |
|---|---|---|---|---|
| 1: generic lenses, defaults | Repairs | 3.7 Flash: **34s**, 3 calls | Sol: failed at 63s (image context) | Sonnet 5: **134s**, 3 calls |
| 1 | Pinball | 3.7 Flash: **40s**, 3 calls | Sol: **75s**, 4 calls | Sonnet 5: **125s**, 5 calls |
| 2: domain lenses, smaller models | Repairs | 3.7 Flash: **27s**, 3 calls | Luna: failed at 48s (image context) | Haiku 4.5: exhausted 6-call budget at 90s |
| 2 | Pinball | 3.7 Flash: **34s**, 3 calls | Luna: failed at 56s (image context) | Haiku 4.5: exhausted 6-call budget at 140s |
| 3: tightened lenses, JPEG review | Repairs | 3.8 Flash: **28s**, 3 calls | Luna: **62s**, 4 calls | Sonnet 5: **119s**, 4 calls |
| 3 | Pinball | 3.8 Flash: **38s**, 5 calls | Luna: **60s**, 3 calls | Sonnet 5: **187s**, 5 calls |

Pass 3 first-result latency was **28s / 38s**; complete batches were **119s / 187s**.
The earlier single-provider pinball exploration took about 412 seconds. This is an
encouraging practical improvement, not an apples-to-apples speedup claim: the new
workers have narrower output scope and publish independently.

Gemini Flash was the fastest finisher in these trials. OpenAI produced the strongest
visual hierarchy in the reviewed samples. Sonnet contributed useful task ideas but
was the slow tail; Haiku did not finish within the six-call allowance. Do not assume
a smaller model lowers end-to-end latency. Leave automatic plans on upstream
provider defaults; callers can pin discovered models and choose two workers when
they value latency over a third perspective. No untested Copilot or ChatGPT OAuth
performance claim is made: neither account was configured here.

## Performance and correctness changes

- Separate processes avoid Agent's process-global engine lock serializing fan-out.
- Shared deadline/call grants prevent three workers multiplying the authorized budget.
- Completed candidates publish progressively; sibling failures remain visible and
  do not discard successes. Cancellation terminates child process groups.
- Host-generated embedded thumbnails replace always-live gallery frames. At most
  two chosen comparison frames load; clear unloads them. Focus mode hides the
  refinement margin. New results do not reset an active comparison.
- A compact status disclosure separates generation details from the prototype.
- Review screenshots use JPEG; a later bounded-quality pass reduces larger payloads.
  Full-quality gallery thumbnails remain PNG. Thumbnail base64 is excluded from
  refinement text prompts. Three exploration context failures disappeared in pass 3;
  a subsequent misrouted continuation still failed, so image-context risk is not
  claimed universally solved.
- Fixed runner environment propagation so an implicit OpenAI default does not override
  a selected concept's actual provider/model. Explicit settings still override it.
  The repairs continuation was retried explicitly on Gemini and completed in 7.5s.
- Single-concept workers must provide all six task-model fields and a verified central
  interaction. Prompts now require consistent derived quantities and concise simulation labels.
- CSS external-asset scanning is scoped to actual CSS; JavaScript `createObjectURL`
  no longer produces a false positive. Visible embedded images must decode.
- Added provider-model discovery through Amplifier, in CLI/library/dashboard. Discovery
  returns catalog information, not a guarantee of model/account compatibility.

## End-to-end validation

Pinball make-interactive took 34s and the visual/numeric refinement 67s. Repairs
make-interactive on its selected Gemini model took 7.5s and the handoff refinement
54s, followed by a 70s focused copy pass. These are real provider measurements; the
older runners used the implicit OpenAI default for the recorded pinball continuation
before the provider-inheritance fix was loaded.

Both exports were byte-identical to their reviewed artifact hashes. Offline replay
covered all retained interaction assertions at 1280×900 and 390×844, in light and
dark mode. Final verification replayed 20 flows and found no script errors, blocked resource
requests, broken visible images or horizontal overflow. Export took 0.005s / 0.004s.
Checks validate demonstrated flows; they do not prove every visible control, real
Pinside access, OCR, persistence or comprehensive accessibility.

Local retained evidence (ignored by git):

- `examples/generated/diversity/measurements.json`
- `examples/generated/diversity/round1`, `round2`, `round3`: stores, checkpoints and diagnostics
- `examples/generated/diversity/round3/repairs/export`
- `examples/generated/diversity/round3/pinball/export`

Reproduction: `examples/diversity_trial.py`, `diversity_continue.py`, and
`diversity_verify.py`. Generation scripts require explicitly configured environment
providers and spend model calls. Verification/export needs no provider.

## Remaining opportunities

1. Keep a stable evaluation corpus and rotate models across identical lenses before
   claiming a model winner. Score task distinctness, scope coverage, task correctness,
   visual quality and latency separately.
2. Test more task families (coordination, reconciliation, decisions under uncertainty),
   beyond these two personal tracking/planning examples.
3. Add stronger model-independent numeric/state consistency checks where the task has
   a known invariant; browser assertions chosen by the generating model can miss semantic bugs.
4. Fine-grained worker checkpoint recovery could salvage an otherwise complete failed
   concept. Current batch behavior retains completed siblings; normal single-operation
   finalization remains deterministic and never invents missing review evidence.

Final automated validation: 60 tests, 16/16 smart-tool conformance checks, Ruff,
and the offline Amplifier screenshot/submission probe. All six trial explorations
were closed; both final selected revisions completed export → finish → cleanup.
