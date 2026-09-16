---
name: possibly
description: Explore visual alternatives for an app, choose an experience, and refine a standalone prototype before production development.
---
Install with `uv tool install --python 3.12 'possibly @ git+https://github.com/robotdad/possibly'`.
No checkout is needed. Install Chromium with `uv tool run --from 'possibly @ git+https://github.com/robotdad/possibly' playwright install chromium`.
Run `possibly --help` and follow the skill it returns.

If `possibly` is not on PATH after installation, run `uv tool update-shell` and
start a new terminal. Python 3.12+, Git, and uv are prerequisites. The standard install includes
the OpenAI, Anthropic, and Google GenAI SDKs; no provider extras are needed.
Amplifier may still download provider modules on first use, requiring network
access. Do not rely on runtime loading to install missing SDKs.

Before generation, read `possibly provider-settings` and help for `test-provider`.
Help the user configure native environment credentials or explicitly requested
provider sign-in, then test with their authorization. OpenAI is the default;
`POSSIBLY_PROVIDER` and `POSSIBLY_MODEL` select alternatives. See
[provider setup](../../src/possibly/docs/providers.md) for details and
[the caller guide](../../src/possibly/docs/caller-guide.md) for the interaction flow.
