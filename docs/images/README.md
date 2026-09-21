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
