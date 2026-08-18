# OpenHands — third-party notice

| | |
|---|---|
| Upstream | `https://github.com/OpenHands/OpenHands` |
| Agent server | `ghcr.io/openhands/agent-server` (from `OpenHands/software-agent-sdk`) |
| Licence | MIT |
| Copyright | © 2025 OpenHands contributors |
| Inspected | 2026-08-09 |
| What was taken | **Nothing.** No source code, no file, no fragment. |

## How GalSen IA uses it

`src/coding_engine/adapters/openhands_adapter.py` is an HTTP client. The
operator runs the OpenHands agent server as a container; GalSen IA talks to it
over the REST paths that server exposes. Nothing is imported, nothing is
vendored, and no OpenHands package is a dependency of this project.

The endpoints used were read from the agent server's own source
(`openhands-agent-server/openhands/agent_server/`) so the adapter targets real
paths rather than guessed ones:

    GET  /health
    POST /api/conversations
    POST /api/conversations/{id}/run
    GET  /api/conversations/{id}
    GET  /api/conversations/{id}/agent_final_response

Authentication, when enabled, uses the `X-Session-API-Key` header.

## Why the integration is HTTP and not a library

`OpenHands/OpenHands` is today a TypeScript application (agent-canvas). The
engine that performs the work is a separate Python service distributed as a
container image. Importing the SDK would add a large Python tree in order to
write a REST client, and would give up the container isolation that is the main
reason to prefer OpenHands for autonomous work — the isolation
`src/coding_engine/workspace.py` cannot give a local subprocess.

## Licence position

MIT permits use, modification and redistribution, and requires the copyright
notice to be preserved in copies of the software. **No copy is made here**, so
that obligation is not triggered; this notice exists for traceability, and is
where the attribution would go if any code were ever vendored.

Calling a program over a network creates no derivative work and imposes no
licence obligation of its own.

## Availability

If the container is not running, the adapter reports `unreachable` with the
`docker run` command that starts it. Everything else in GalSen IA keeps working.
