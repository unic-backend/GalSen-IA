
# Security Rules — GalSen IA

## Hard Rules (never break these)

- NEVER commit secrets, API keys, passwords or tokens.
- NEVER commit `.env` files.
- NEVER hardcode credentials in the source code.
- NEVER push directly to the `main` branch.
- Always assume that user input can be malicious.

## Good Practices

- Use environment variables for all secrets.
- Validate and sanitize all external inputs.
- Prefer the principle of least privilege.
- Keep dependencies up to date.
- Log security-relevant events (without logging secrets).

## When in doubt
Ask the user before doing anything that could affect security (permissions, authentication, data access, etc.).