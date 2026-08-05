# ADR-004: Provider Credential Handling

## Status
Accepted

## Date
2026-07-29

## Context
The Model Engine provider architecture (ADR-003) is complete but credential handling was deliberately left out of scope, noted as a follow-up item. Currently, hosted providers (OpenAI, Anthropic, Google) report `UNAVAILABLE` with reason `NO_CREDENTIALS` because credential handling is not implemented.

We need to decide how to handle provider credentials securely while maintaining:
- Security: No credentials in code or version control
- Simplicity: Easy configuration for developers and deployment environments
- Flexibility: Support different deployment environments (local dev, staging, production)
- Compatibility: Work with the existing provider architecture

## Decision
We will handle provider credentials exclusively through environment variables, with the following specifications:

1. **Environment Variable Only Approach**
   - Each hosted provider reads its credentials from a specific environment variable
   - No other credential sources (files, explicit parameters, etc.) are supported
   - This prevents accidental commitment of credentials to version control

2. **Specific Environment Variables**
   - OpenAI Provider: `OPENAI_API_KEY`
   - Anthropic Provider: `ANTHROPIC_API_KEY`
   - Google Provider: `GOOGLE_API_KEY`

3. **Credential Validation**
   - Providers check for the presence of their environment variable during `check_availability()`
   - If the variable is missing or empty, report `UNAVAILABLE` with reason `NO_CREDENTIALS`
   - If the variable is present, attempt to use it for authentication
   - Authentication failures (invalid/expired tokens) result in `UNAVAILABLE` with appropriate reason

4. **Security Considerations**
   - Credentials are never logged or exposed in error messages
   - Environment variables are the standard secure method for configuration in containerized/deployed applications
   - Local development can use .env files (not committed) with tools like python-dotenv if desired, but this is outside the scope of the platform itself

5. **Fallback Behavior**
   - When credentials are missing, providers continue to return `UNAVAILABLE` as before
   - This maintains backward compatibility and allows the model selection logic to work correctly
   - Local providers (like Ollama) remain unaffected and continue to work without credentials

## Consequences

### Positive
- **Security**: Eliminates risk of accidental credential exposure in code repositories
- **Simplicity**: Clear, straightforward credential mechanism
- **Standards Compliance**: Follows 12-factor app principles for configuration
- **Backward Compatibility**: Existing code continues to work unchanged
- **Clear Error Messages**: Users know exactly what to configure when providers are unavailable

### Negative
- **Requires Deployment Configuration**: Deployment environments must set the appropriate environment variables
- **Local Development Setup**: Developers need to set environment variables for local testing
- **No Built-in Secret Management**: Integration with secret managers (AWS Secrets Manager, HashiCorp Vault, etc.) must be done at the deployment level

### Mitigations
- **Documentation**: Clear documentation of required environment variables
- **Development Tooling**: Recommendation to use python-dotenv for local development (documented, not enforced)
- **Error Reporting**: Clear, actionable error messages when credentials are missing
- **Local Provider**: Ollama provider continues to work without credentials for local development/testing

## Implementation Details
1. Modify `HostedProvider.check_availability()` to check for environment variables
2. Update `HostedProvider.generate()` to attempt API calls when credentials are present
3. Implement `_call_api()` methods in each concrete provider (OpenAI, Anthropic, Google)
4. Add proper error handling for authentication failures
5. Ensure credentials are never logged or exposed

## Related Documents
- ADR-003: Model Provider Architecture
- .claude/rules/security.md: Security Rules