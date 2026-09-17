# Future exploration mode: generate A2UI prototypes

Recorded 2026-09-16. Explicitly endorsed by the user. Idea for later exploration;
not a commitment to implement during the first host-integration experiment.

Possibly could offer a separate mode that generates A2UI prototypes against a
chosen component catalog, alongside its existing self-contained HTML prototypes.

Keep two uses of A2UI distinct:

- **Possibly's review experience:** reusable concept comparison, selection,
  feedback, revision history, and preview controls. Its descriptions can be
  produced deterministically from library state.
- **The experience being explored:** model-generated A2UI structures, data, and
  interactions, rendered using a target application's components and design system.

The second mode could let a team explore how an application might work using its
actual available components before implementing the application. The catalog
would be an explicit design constraint, not an invisible restriction on every
Possibly exploration. Preserve the existing emphasis on different task models,
organizing objects, and overlooked user needs.

Questions for a later experiment:

1. Does catalog-constrained generation improve implementation relevance while
   retaining meaningful task diversity? Compare against HTML on the same briefs.
2. How do we model simulated behavior and state transitions without accidentally
   invoking real host actions? Use a bounded mock action environment.
3. What makes a revision reproducible? Likely the protocol version, catalog
   identity/version, UI messages, initial data, mock action behavior, renderer
   version, and review evidence together.
4. What is exported? A structured implementation handoff and reproducible A2UI
   artifact bundle; an HTML viewer could be an additional export, but native A2UI
   artifacts should not be advertised as standalone HTML.
5. Can reviewers compare an HTML concept and an A2UI concept fairly, with the
   constraints of each made explicit?

First establish a shared review presenter and a second host. Evaluate this mode
afterward as its own product/design experiment.
