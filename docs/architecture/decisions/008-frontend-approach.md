# ADR-008: Frontend Approach

## Status
Accepted

## Date
2026-08-06

## Context
The Architecture Manual (VOLET_02, chapter 02, *Frontend Architecture*) requires
user-facing applications for web, mobile, desktop and PWA, built on
component-based architecture, responsive and accessible by default, with an API
client, file upload, notifications, offline support and error handling. Its final
directive: *"The frontend must remain independent from backend implementation
details through clean APIs."*

Today nothing exists. The platform exposes 40 REST routes and has no face: to
know whether email is configured, which keys are active or whether an engine is
healthy, one must hold an API key and craft HTTP requests by hand. The people who
will operate this platform in Senegal are not all going to do that.

The chapter names no technology, so the stack is an open decision — which is why
it needs an ADR rather than a default chosen by whoever writes the first page.

Two constraints shape it, and neither is technical:

- **The project is maintained by one person, often from a phone, on a connection
  that drops.** A toolchain that must be installed, updated and debugged before a
  single line renders is a real cost, paid repeatedly.
- **The platform targets Senegal first** (VOLET_01, chapter 01). Bandwidth and
  devices cannot be assumed generous. A first load measured in megabytes is a
  design decision about who can use the product.

## Decision
The web client starts **buildless**: standard HTML, CSS and JavaScript modules
served directly by the existing FastAPI application under `/ui`, with no bundler,
no package manager and no compilation step.

- **Component-based without a framework.** ES modules and custom elements provide
  the composition the chapter asks for. A component is a file exporting a render
  function; there is no hidden runtime.
- **One shared API client** (`api-client.js`) is the only module that knows the
  routes exist. Pages never call `fetch` directly, which is how the chapter's
  final directive is honoured concretely rather than by intention.
- **Themes and responsiveness through CSS**: `prefers-color-scheme` and fluid
  layout, no JavaScript required to render a readable page.
- **Progressive enhancement toward PWA**: a manifest and a service worker can be
  added to this structure without rewriting it, which is what covers the offline
  support the chapter requires.

This is a starting point, not a ceiling. When the interface outgrows it — shared
state across many pages, complex forms, a component library — a framework becomes
justified, and the API client survives the migration untouched because it depends
on nothing but `fetch`.

## Consequences

### Positive
- Nothing to install: `uvicorn src.api.server:app` serves the interface. A
  contributor with a browser and Python is productive immediately.
- The CI stays a single `pytest` run; no second toolchain to keep green.
- First load is a few kilobytes, which matters more than developer comfort for
  the intended users.
- The API client is portable: a future mobile or desktop client reuses the same
  contract.

### Negative
- **No JavaScript unit tests.** The Python suite verifies that the interface is
  served and that its pages carry what they must, but the browser-side logic is
  not covered. This is stated plainly rather than dressed up: it is the real cost
  of this choice, and it grows with the interface. Introducing a JS test runner
  is the trigger to revisit this ADR.
- No type checking, no JSX, no ecosystem of ready-made components.
- Hand-written DOM manipulation becomes unpleasant past a certain complexity —
  and that unpleasantness is the intended signal to move to a framework.

### Neutral
- Node is available in the environment; it is simply not required to run or
  build the interface today.

## Alternatives Considered

**React with Vite.** Rejected for now, not on merit: it is the right answer for a
large interface, and it will likely be the answer later. It is wrong as a *first*
step because it adds a package manager, a build step, a lockfile and a second CI
job before the first page displays anything — costs paid immediately against
benefits that only appear at a scale this interface has not reached.

**Server-rendered templates (Jinja2).** Rejected because it would put presentation
logic back inside the API application, contradicting the chapter's directive that
the frontend stay independent through clean APIs, and because it makes the future
mobile and desktop clients second-class citizens.

**No frontend, documentation only.** Rejected: `/docs` describes routes to
developers, which is not the same as letting an operator see that the mail server
is unreachable. That was the state before this ADR, and it is what made the
platform invisible to everyone but its author.
