# Coding Standards — GalSen IA

## Language Rules
- Code comments → French
- User-facing text → French
- Technical documentation → English
- File names, folder names, commit messages → English

## General Principles
- Prefer simple solutions over complex ones.
- Write code that is easy to read and maintain.
- Keep functions and modules focused on a single responsibility.
- Avoid premature optimization.
- Never hardcode secrets.

## Python-Specific Standards
- Follow PEP 8 for code style, with a line length limit of 88 characters (or 79 for strict compatibility).
- Use `ruff` or `flake8` for linting.
- Use `black` for code formatting.
- Use `mypy` for static type checking.
- Use `pytest` for testing.
- Use `tox` for testing across multiple Python versions.
- Use `pip` and `virtualenv` or `pipenv`/`poetry` for dependency management.
- Structure projects with a `src` layout (as we have).
- Use absolute imports within the project.
- Use type hints as per PEP 484 and gradually add them to the codebase.
- Write docstrings for all public modules, functions, classes, and methods following PEP 257.
- Use `asyncio` for asynchronous I/O-bound operations.
- Use `dataclasses` for simple data-holding classes.
- Use `enum.Enum` for enumerations.
- Use `pathlib.Path` for file system operations.
- Avoid mutable default arguments; use `None` and create a new object inside the function if needed.
- Prefer `is` for comparing to `None` and singletons.
- Use context managers (`with` statement) for resource management.
- Handle exceptions specifically; avoid bare `except:` clauses.
- Use logging module for logging, avoiding `print` in production code.
- Follow the principle of least astonishment; make code predictable and readable.