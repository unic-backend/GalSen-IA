# GalSen IA - Coding Standards

## General Principles

Always write clean, readable and maintainable code.

Every line of code must have a purpose.

Prefer simplicity over unnecessary complexity.

Never sacrifice quality for speed.

---

# File Organization

Keep files small and focused.

One responsibility per module.

Group related functionality together.

Avoid large monolithic files.

---

# Naming

Use clear and descriptive names.

Avoid abbreviations unless universally recognized.

Functions should describe actions.

Classes should describe entities.

Variables should clearly express their purpose.

---

# Functions

Keep functions short.

One responsibility per function.

Avoid deep nesting.

Return early whenever possible.

Document public functions.

---

# Classes

Each class must have one responsibility.

Favor composition over inheritance.

Avoid God Objects.

Keep constructors simple.

---

# Architecture

Respect the existing project architecture.

Never bypass layers.

Separate:

- UI
- API
- Services
- Agents
- Memory
- Models
- Tools
- Storage
- Configuration

Never mix responsibilities.

---

# Configuration

Never hardcode:

- API Keys
- URLs
- Ports
- Tokens
- Secrets
- Environment-specific values

Always use configuration files or environment variables.

---

# Error Handling

Never ignore exceptions.

Provide meaningful error messages.

Retry recoverable failures.

Log important events.

---

# Performance

Avoid unnecessary API calls.

Avoid duplicated computations.

Use caching where appropriate.

Optimize memory usage.

Optimize execution speed without reducing readability.

---

# Security

Validate all inputs.

Sanitize external data.

Never expose secrets.

Follow secure coding practices.

Protect user privacy.

---

# Testing

Create or update tests for new features.

Ensure existing functionality is not broken.

Fix failing tests before completing tasks.

---

# Documentation

Update documentation when behavior changes.

Keep comments useful.

Do not comment obvious code.

Document architecture decisions.

---

# Git

Make logical, atomic changes.

Never introduce unrelated modifications.

Keep commits clean and focused.

---

# AI Development

Before implementing a feature:

- Understand the objective.
- Analyze the existing architecture.
- Reuse existing components whenever possible.
- Avoid duplicate implementations.

Always improve the project instead of simply adding more code.

---

# Final Rule

Every contribution must leave GalSen IA better than before.

Think like a senior software architect building a world-class AI platform.