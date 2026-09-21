# Product screenshot

`possibly-comparison.png` is a Chromium screenshot of the shipping Possibly
side-by-side comparison dialog at commit `8e75d95`, captured on 2026-09-20.
It shows two retained, model-generated concepts for **Repair Together**, a fictional
repair café: **Guided intake** and **Station board**. Both cover item intake,
reviewing the item, its assigned next step, and the station board. The difference
is the organizing task and flow. Names and repair items are fictional demo data.

The capture uses the unchanged dashboard HTML and original retained prototype
HTML. There are no CSS overrides, rewritten UI labels, composited screens, or
image-generation edits. The image is cropped to the actual comparison dialog by
Playwright's element screenshot: 3136 × 1448 pixels, captured at a 1600 × 1000
browser viewport and 2× device scale in light mode. Each sandboxed prototype keeps
the dashboard's 1280 × 900 simulated viewport and native fit-to-panel behavior.

`examples/capture_readme.py` replays public-library snapshots and artifacts through
a local read-only browser transport. It does not call a model or modify the source
exploration. Stores, capability tokens, and private viewer URLs are not published.
To recapture from the retained demo:

```sh
uv run python examples/capture_readme.py /path/to/comparison-store \
  exp_5827a67429044201829d256643bff162 docs/images/possibly-comparison.png
```

Original artifact SHA-256 values:

- Guided intake: `efd14792d41e6f8b4d2f5cd6299e7a6e957dd983392b39a16614ae1a9e3ab27b`
- Station board: `c175b8e2db22e5d9a8cc5e75dafe61de35266b05133fbc7f3aa60bd866051ecc`

## Demo brief

Create two meaningfully different complete interactive experiences for Repair
Together, a fictional repair café. Same scope and sample data: Alex brings a
wobbly chair, Jo brings a bag with a loose handle, and Sam brings a torn jacket.
Stations: Welcome, Repair tables, Next steps. Both experiences allow item intake,
reviewing the item, seeing its assigned next step, and inspecting the station
board. Change organization and task flow, not only colors or missing features.
Use cream, plum, mint, and coral, clear labels, and a visible simulated-data notice.
No network, backend, booking, or safety advice.

## Previous conceptual illustration

`possibly-possibilities.png` was generated with the built-in image generation tool on 2026-09-15 and reviewed for use as conceptual README artwork. It is not a screenshot or a claim about automatic production development. The generated image includes short explanatory labels; these describe possible interface approaches.

## Prompt

Use case: stylized-concept. Asset type: wide landscape GitHub README editorial illustration for Possibly, a tool for exploring app experiences before building them. Primary request: evoke the practical act of discovering several useful ways to approach one app idea, comparing them, and refining one into a clickable prototype. Scene: a carefully composed design worktable viewed at a gentle overhead angle. One simple handwritten idea card branches into three tangible paper interface studies: a chronological activity journal, a place/object map, and a goal/progress planner. Their structure is visibly different, not just their colors. One study is pulled forward, with a small annotation and a polished but clearly provisional screen beside it. Style: elegant tactile paper-cut editorial illustration with subtle pencil marks, quiet dimensional shadows and natural paper grain. Wide composition about 2:1, balanced and readable at README width, warm cream paper and muted forest green with restrained amber accents. Mood: thoughtful, curious, grounded craft. No legible text, no logos, no robot, no magic sparkles, no futuristic holograms, no claims of production deployment, no charts implying performance benchmarks. This is conceptual artwork, not a screenshot of the product. Keep visual complexity moderate and leave breathing room.

## Product demo loop

`possibly-demo.mp4`, `possibly-demo.gif`, and `possibly-demo-poster.png` show the
same retained Repair Together concepts in the real Possibly comparison dialog.
The 14-second silent edit was prepared on 2026-09-20 from the successful Showrun
capture `possibly-experience-comparison-02`. The original capture SHA-256 is
`c43340e6d9114360590475635d31d5e54dd65a77fb4378bb31371da297da35e8`.
It is previously recorded footage, not a claim that generation or the current
application was exercised again for this edit. All sample people and items are
fictional. The interaction is with sandboxed prototypes, not a production app.

The shot plan is deliberately small:

| Output time | Source range | Action / caption |
| --- | --- | --- |
| 0–3s | 25–28s | Compare both concepts: “One idea. Two ways to work.” |
| 3–6s | 34.5–37.5s | Review the existing sample intake: “Try the guided intake.” |
| 6–10s | 42.2–46.2s | Confirm and see the assignment: “See the next step.” |
| 10–14s | 51.3–55.3s | Inspect the chair in the other concept: “Explore the station board.” |

Vid's public library compiles the trims, audio removal and burned captions.
The delivery graph crops the original 1600×1000 capture to the real 1568×724
comparison dialog at (16, 138), then adds a 60-pixel cream caption strip.
There are no rewritten product labels, synthetic interactions, or speed changes;
waiting time between interactions is cut. The ending cuts back to the opening
comparison on repeat. The MP4 is 1568×784, 25 fps, H.264 CRF18, silent, with
fast-start metadata. The poster is its first decoded frame.

Outtake's public `plan` and `render` operations convert that MP4 to the README
GIF: range 0–14 seconds, `format="gif"`, `audio="mute"`, `max_width=1200`,
`fps=12`, `captions_enabled=False`. The GIF is 1200×600 and approximately 542 KB;
the MP4 is approximately 194 KB. Both retain the same burned captions.
Outtake export ID: `export_a851ac3c8321416cb0e7069627d72d7d`.

The site uses the MP4 with native playback controls, a full-size link and a
shared pause-motion button. Reduced-motion preferences start with the poster;
without JavaScript the native player remains usable and does not autoplay.
The README links its GIF to that controllable player. Original source footage,
local edit plans, receipts, private stores and viewer URLs are not published.

### Extended selection ending

`possibly-demo-selection.mp4` and `possibly-demo-selection.gif` retain the first
14-second edit and add a four-second ending: cut from the comparison to the concept cards, choose Guided
intake, and hold on its real refinement workspace. The caption reads “Choose a
direction. Keep developing it.” The original `possibly-demo.mp4` and
`possibly-demo.gif` remain unchanged for comparison and reuse.

The added footage was captured with Playwright from the unchanged shipping
dashboard using a local transport backed by public Possibly library operations.
The original retained SQLite store was copied with SQLite's backup API; all
review-state updates and the selection were written only to that isolated copy.
`record_decision` accepted the selection of
`rev_1015d03fdabe4aec9c5389f5340791ce`; its receipt reported no follow-up operation.
No generation or refinement was run. This ending demonstrates the selection and
workspace, not a generated refinement. The source exploration remains unchanged.

Vid trims the new capture from 1.15–5.15 seconds and appends it to the preserved
edit. The complete viewport is fitted without stretching into the same frame,
so the actual selection button and refinement controls remain visible. Outtake
exports the full 0–18 second edit at 1200 pixels wide and 12 fps. The MP4 is
approximately 593 KB and the GIF 2.9 MB. Both decode successfully; browser checks
cover duration, looping, pause/resume, mobile width, reduced motion and no-JS
playback. The branded local preview and README now use this extended version.

The selection shot begins after the comparison dialog closes, removing the brief
rescaled-dialog flash at the edit boundary. The previous extended edit is retained
locally, and the original 14-second MP4 and GIF remain unchanged.

### Direct transition to the chosen workspace

The current extended edit omits the concept-card selection detour. At 13.6 seconds
it crossfades for 0.4 seconds directly from comparison into the actual selected
Guided intake workspace, captioned “Carry your chosen direction forward.” The
ending uses source time 2.65–6.4 seconds with a 0.65-second final-frame hold;
total duration remains 18 seconds. This shows the selection result, not the click.
Earlier extended cuts and their edit scripts are retained locally.

The final crossfade delivery is approximately 444 KB (MP4) and 2.2 MB (GIF).
Both are 18 seconds; the README embeds `possibly-demo-selection.gif`, and the
website plays `possibly-demo-selection.mp4` with the original opening poster.
