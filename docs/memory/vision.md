# GalSen IA — Vision

## Mission
GalSen IA is a long-term artificial intelligence platform designed first for Senegal,
then Africa, then the rest of the world.

The goal is to build practical, useful, and culturally relevant AI systems that solve real
problems for people and businesses in Senegal and across Africa.

## Core Principles
- Start local (Senegal) before going global
- Prefer practical solutions over theoretical research
- Keep systems simple, maintainable and low-cost
- Always prioritize African data, languages and use cases when possible
- Build for long-term sustainability (years, not months)

## What decides a roadmap choice
When two directions compete, these settle it (VOLET_04 ch. 01, VOLET_01 ch. 05):

- **Long-term alignment beats opportunity.** A feature that is easy now and wrong later
  is not a shortcut, it is a debt with interest.
- **Validate before expanding.** One thing working end to end is worth more than four
  half-built ones — the mistake this project has already made once.
- **Deliver incrementally, and measure it.** Progress that cannot be observed is a claim.
- **Never invent facts.** Applies to the platform's output and to its own reporting:
  unavailability is stated, not filled with something plausible.

## Long-term Ambition
Become a reference AI platform for African contexts while remaining competitive
internationally, evolving for decades without the core being rebuilt.

## Current Phase
**Core platform.** The foundation phase is over: fourteen engines and services run behind
a REST API with authentication and RBAC, a buildless dashboard is served at `/ui`,
persistence is decided and wired (ADR-005), and the suite holds 1410 tests. VOLET 02 is
complete.

What the platform still lacks is a *user*: no model provider is configured, so its first
real feature — *Conseil agricole* — answers 503 until a key exists in the environment.
Every adoption or satisfaction indicator is therefore unmeasurable today, and saying so
is more useful than reporting zero.

## Where the authoritative text lives
This file is the project's working vision. It does not restate the manuals:

| Subject | Source |
|---------|--------|
| Mission, values, ethical principles | `docs/architecture/VOLET_01.md` ch. 01–02 |
| Long-term direction, country expansion | `docs/architecture/VOLET_01.md` ch. 05 |
| Product vision, roadmap principles | `docs/architecture/VOLET_04.md` ch. 01 |
| Technical decisions | `docs/architecture/decisions/` |
