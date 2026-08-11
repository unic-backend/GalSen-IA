# ADR-012: TLS Termination Belongs to the Deployment, Not the Application

## Status
Accepted

## Date
2026-08-11

## Context
Exit criterion **C4** asks for a platform reachable over a network. Nothing stood in front
of the application: `docker-compose.yml` published port 8000 on the host, in clear, and the
application does not terminate TLS.

Two things had to be decided together, and the deployment audit
(`docs/deployment/audit-2026-08-11.md`, D2) is the reason:

1. **Where TLS is terminated.**
2. **Whether the application may believe `X-Forwarded-For`.** It did, unconditionally.
   With no proxy in front — the state the platform was in — any caller could send that
   header, change identity on every request, and thereby obtain an unlimited quota *and*
   invisibility from the threat detector, which counts authentication failures per source.
   Adding a proxy without fixing this would have left the hole open; fixing it without a
   proxy would have made a legitimate deployment lose the real client address. Neither is
   correct alone.

## Decision

**TLS is terminated by Caddy, in front of the application.** The application never handles
certificates.

Reasons, in order of weight:

- A Python process terminating its own TLS would reimplement certificate issuance, renewal
  and the ACME challenge — work every deployment already has a better answer for.
- Caddy obtains and renews certificates automatically, and redirects HTTP to HTTPS without
  being asked. The configuration that does this is eight lines.
- The application keeps its own security headers. Caddy does not duplicate them: two values
  for one header let the most permissive win, depending on the client.

**The application no longer publishes a port on the host.** `expose` replaces `ports`, so
the only way in is through the proxy. A published 8000 would be a clear-text route around
TLS, around the proxy's access log, and around whatever the proxy enforces.

**A forwarding header is believed only when it comes from a declared proxy.**
`GALSEN_TRUSTED_PROXIES` lists addresses, CIDR blocks or exact peer names. Empty — the
default — means no forwarding header is believed, and the address used is the connection's
own. That default is correct for a deployment with no proxy, and becomes correct for one
with a proxy as soon as the operator declares it.

Three details of that rule are deliberate:

- **The chain is read right to left.** Each proxy appends its predecessor, so the leftmost
  entry is exactly the one a caller controls. Walking from the right past declared proxies
  and stopping at the first host that is not one gives the real client.
- **A malformed address is reported, not treated as a hostname.** `10.0.0.300` is a typo,
  and silently accepting it as a name would let an operator believe they declared a proxy
  they did not.
- **`X-Forwarded-Proto` follows the same gate.** Believed unconditionally, it makes the
  application send a two-year HSTS header on a response that was never encrypted.

**Certificate storage is persistent.** `caddy_data` holds certificates and private keys;
without it every restart requests a new certificate and runs into Let's Encrypt's rate
limits.

**The development service moved behind a Compose profile.** It ran alongside the production
service with `restart: unless-stopped` and a published port — a second instance of the
platform, which ADR-009 forbids, and an auto-reloading service with rate limiting disabled
exposed on the host. `docker compose --profile dev up api-dev` still starts it.

## Consequences

Positive:

- HTTPS, certificate renewal and the HTTP redirect require no application code.
- The rate limiter and the threat detector see real addresses again, and cannot be fooled
  by a header.
- One way in, one access log.

Negative, and accepted:

- Caddy is one more container to run and update.
- A deployment behind a proxy that does **not** set `X-Forwarded-For` will see every request
  as coming from the proxy, so the unauthenticated per-address limit becomes global. That
  is visible and safe — it restricts rather than opens — and Caddy sets the header.
- Certificate issuance needs port 80 reachable and DNS pointing at the host. Until then
  Caddy retries and the application stays reachable on the internal network only.

## Alternatives considered

- **TLS in Uvicorn** — possible (`--ssl-certfile`), and it leaves certificate renewal to
  the operator, which is the part that actually fails at 3 a.m.
- **nginx** — capable, but the certificate lifecycle needs certbot and a renewal hook. The
  configuration that Caddy expresses in eight lines takes considerably more.
- **Trust `X-Forwarded-For` only from private ranges, without configuration** — looks
  convenient and is wrong: a deployment where the application is directly reachable from a
  private network would trust every client on it.

*Caddy is Apache-2.0. Only the configuration pattern is used — a site block with
`reverse_proxy` and the two data volumes. No code is copied.*
