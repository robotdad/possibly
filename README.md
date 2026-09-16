# Possibly

**Explore the experience before you build the app.**

![An idea branching into a journal, a map, and a planner, with one direction brought forward for refinement.](docs/images/possibly-possibilities.png)

Possibly helps you and your coding agent try different ways an app could work.
Start with an idea, compare visual concepts, choose a direction, and refine a
clickable prototype before committing to implementation.

The interesting difference is the **task**, not just the theme. A household repairs
app might start with “What can we finish this weekend?” or “What needs to be ready
before someone can fix this?” A pinball log might center on tonight’s session,
beating a personal best, or discovering an unplayed machine.

## Try it with your coding agent

Give your agent the project link and an idea—no checkout needed:

> Use [Possibly](https://github.com/robotdad/possibly) to explore an app for tracking
> household repairs. Follow its README to install the tool, then read
> `possibly --help`. Show me different
> ways to approach the task, let me choose, then refine a clickable prototype.

Possibly runs as a local CLI or Python library and uses **Amplifier Agent** for its
intelligence. Your coding agent needs permission to run local commands and access
to a configured model provider. Installing an agent skill alone does not provide
model credentials.

Once installed, tell your agent to run `possibly --help`. It returns the current
caller skill, including the interaction model and exact capabilities. You can use
Possibly from your own project directory.

## Quick start

Requires **Python 3.12+**, **Git**, and **uv**. The current release is a local POC,
validated on macOS.

```sh
uv tool install --python 3.12 'possibly @ git+https://github.com/robotdad/possibly'
uv tool run --from 'possibly @ git+https://github.com/robotdad/possibly' playwright install chromium
possibly --help
```

This installs an isolated CLI from the Git source; it does not require you to clone
or maintain a checkout. Git is needed by the installer. If `possibly` is not on your
PATH, run `uv tool update-shell` and open a new terminal. The browser command uses
the tool package’s Playwright dependency.

One installation supports every provider in Amplifier’s catalog; no provider extras
are required. Amplifier downloads each provider module and its dependencies on first
use, then caches them. That first use needs network access and can take longer.

Make `OPENAI_API_KEY` available in the environment that launches your agent or
Possibly. Then check the connection:

```sh
possibly provider-settings
possibly --model-env test-provider
```

OpenAI is the default. Other supported provider options include Anthropic, Gemini,
Azure OpenAI, GitHub Copilot, ChatGPT OAuth, and compatible local endpoints. Set
`POSSIBLY_PROVIDER` and optionally `POSSIBLY_MODEL` to choose; see
[provider setup](src/possibly/docs/providers.md) for environment
variables, login, and which paths have been live-tested. The dashboard also offers
session settings, model discovery, and connection tests.

Once setup works, hand the exploration to your agent. You do not need to learn the
JSON API to try an idea.

## What the loop looks like

1. **Explore.** Your agent supplies the brief. Possibly generates two or three
   concepts, optionally using different configured providers and models.
2. **Compare.** Browse thumbnail cards, open two live previews side by side, and
   try their screen navigation. Design rationale stays separate from the mockup.
3. **Choose and refine.** Each selected direction gets a focused workspace with
   version history and feedback. Keep exploring more than one if useful.
4. **Export.** Take a self-contained HTML prototype and a JSON handoff containing
   the brief, choices, assumptions, and mocked behavior to your implementation agent.

Tell your agent when you leave dashboard feedback. The dashboard saves submitted
feedback and drafts, but it does **not** wake the calling agent automatically.
Closing the browser tab also does not end a session; ask your agent to finish or stop it.

## What to expect

This is an exploration tool, not a production app builder. Prototypes simulate
behavior; exports need no network or companion assets, but generating them needs a
provider and Chromium. A passing interaction check is useful evidence, not proof
that every control or product assumption is correct.

Generation time and quality vary by model and brief. In our latest household and
pinball trials, the first concepts arrived in 28–38 seconds and full three-concept
batches took about 2–3 minutes. Earlier attempts failed too. The
[trial report](docs/DIVERSITY-EVALUATION.md) records timings, critiques, and limits
rather than promising a fixed wait. The illustration above is conceptual artwork,
not a product screenshot.

## Developing or contributing?

Clone the repository only when you want to work on Possibly itself.
[`AGENTS.md`](AGENTS.md#develop-from-this-checkout) covers checkout setup, tests,
architecture boundaries, and the contribution workflow.

## Go deeper

- [Agent usage and development workflow](AGENTS.md)
- [Library and CLI caller guide](src/possibly/docs/caller-guide.md)
- [Providers and settings](src/possibly/docs/providers.md)
- [Vision](docs/VISION.md) and [draft interaction contracts](contracts/interaction-api.v1.md)
- [Implementation notes](docs/IMPLEMENTATION.md) and [validation](docs/VALIDATION.md)

Bring an app idea and challenge whether the alternatives reveal something you
hadn’t considered. That is the most useful test of Possibly.
