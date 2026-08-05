# Testing Rules — GalSen IA

## Principles
- Write tests for important logic.
- Prefer simple and readable tests.
- Tests should be deterministic (same result every time).

## Testing Stack
Now that we have chosen Python as our primary implementation language (ADR-001), we use the following testing tools:

- **Unit Testing**: pytest for writing and running tests
- **Async Testing**: pytest-asyncio for asynchronous code testing
- **Coverage**: pytest-cov for coverage reporting
- **Mocking**: unittest.mock from standard library for mocking dependencies
- **Fixture Management**: pytest fixtures for test setup and teardown

## Writing Tests
- Create test files in the `tests/` directory or alongside the code they test
- Name test files with `test_` prefix or `_test.py` suffix
- Name test functions with `test_` prefix
- Use descriptive test names that explain what is being tested
- Follow the Arrange-Act-Assert pattern for test structure
- Keep tests focused on a single unit of behavior
- Use fixtures for common setup tasks
- Mock external dependencies to isolate unit tests

## Test Organization
- Unit tests: Test individual functions, methods, and classes
- Integration tests: Test interaction between components
- End-to-end tests: Test complete user workflows (when applicable)

## Running Tests
- Run all tests: `pytest`
- Run tests with coverage: `pytest --cov=./src`
- Run specific test file: `pytest tests/test_specific_feature.py`
- Run tests matching pattern: `pytest -k "pattern"`
- Run tests in verbose mode: `pytest -v`

## Coverage Requirements
- Aim for minimum 80% code coverage for new code
- Critical paths (authentication, security, data validation) should aim for 95%+
- Regularly review coverage reports to identify undertested areas

## Best Practices
- Write tests before or alongside implementation (TDD/TDD-like approach)
- Don't test implementation details, test behavior
- Keep tests fast and independent
- Use parametrized tests for similar test cases with different inputs
- Test edge cases and error conditions
- Continuously run tests during development