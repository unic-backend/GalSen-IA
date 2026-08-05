# GalSen IA - Core Development Rules

## Mission

Build GalSen IA as a world-class AI platform.

The objective is to deliver an AI experience comparable to the best AI assistants while remaining modular, scalable, maintainable and cost-efficient.

Always think long-term.

---

# Autonomous Development

Work autonomously.

Do not wait for the user to create files or folders.

If a required directory, file, configuration, dependency, documentation, module or resource is missing, create it automatically.

Reuse the existing architecture whenever possible.

Only create what is actually required.

Avoid unnecessary files.

---

# Code Quality

Write production-ready code.

Never generate placeholder implementations.

Never leave TODOs.

Never leave unfinished classes.

Document every public class and function.

Follow clean architecture.

Follow SOLID principles.

Avoid duplicated code.

Always refactor when necessary.

---

# Scalability

Every component must be extensible.

Never hardcode business logic.

Use configuration files whenever possible.

Design everything for long-term evolution.

Future AI providers must be integrated without rewriting the project.

---

# Cross Platform

The backend must power:

- Web
- Windows
- macOS
- Linux
- Android
- iOS
- Public API

Never tightly couple business logic to a single platform.

---

# AI Architecture

Always think as an AI architect.

Prefer modular systems.

Separate:

- Agents
- Memory
- Models
- Tools
- Workflows
- API
- Runtime
- UI

Every component must be replaceable.

---

# Cost Optimization

Optimize operational costs.

Reduce unnecessary API calls.

Reuse computations whenever possible.

Support local models when appropriate.

Cache intelligently.

---

# Reliability

Handle every error.

Validate inputs.

Retry recoverable failures.

Generate useful logs.

Never crash because of a single component.

---

# Security

Never expose secrets.

Validate permissions.

Protect user data.

Follow secure coding practices.

---

# Documentation

Update documentation whenever architecture changes.

Keep configuration synchronized.

Generate useful developer documentation.

---

# Final Rule

Your objective is not simply to write code.

Your objective is to build GalSen IA into a world-class AI platform through clean architecture, autonomous implementation, continuous improvement and production-quality engineering.

Execution Strategy

Full cadence rules, the 25-minute check-in and token economy → `.claude/rules/work-cadence.md`

For any implementation estimated to exceed 8 minutes of work:

- Split the work into logical phases.
- Complete one phase at a time.
- Validate and test each phase before continuing.
- Never restart completed phases.
- Always resume from the last completed state after interruption or timeout.
- Prefer incremental implementation over monolithic execution.