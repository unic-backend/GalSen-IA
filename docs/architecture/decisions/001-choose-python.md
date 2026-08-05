# ADR-001: Choose Python as the primary implementation language

## Status
Accepted

## Date
2026-08-04

## Context
We are building the GalSen IA platform, which includes multiple engines (Router, Agent Runtime, Tool Engine, Memory Engine, Model Engine, Knowledge Engine, Document Intelligence Engine, Vision Intelligence Engine, etc.). We need to choose a programming language that is suitable for AI development, has good library support, and is accessible for developers in Africa and globally.

We have already started implementing components in Python (as seen in the vision_intelligence_engine package and test files). Python is a popular choice for AI and data engineering due to its rich ecosystem (TensorFlow, PyTorch, scikit-learn, spaCy, etc.), readability, and large community.

## Decision
We will use Python 3.9+ as the primary implementation language for all backend components of the GalSen IA platform. This includes:
- All engines (Router, Agent Runtime, Tool Engine, Memory Engine, Model Engine, Knowledge Engine, etc.)
- APIs and web services (if any)
- Data processing pipelines
- Agent implementations

We may use other languages for specific components where justified (e.g., JavaScript/TypeScript for frontend, Rust for performance-critical parts), but the core will be Python.

## Consequences
### Positive
- Leverages existing Python expertise in the team and community.
- Access to a vast ecosystem of AI/ML libraries.
- Readability and maintainability align with our coding standards.
- Easy integration with various APIs and services.

### Negative
- Python may not be the fastest for performance-critical sections; we may need to use extensions or alternative languages for those parts.
- Global Interpreter Lock (GIL) may limit true parallelism in CPU-bound tasks, but we can use multiprocessing or asyncio for I/O-bound tasks.

### Mitigations
- For performance-critical components, we can consider using C/C++ extensions or Rust via PyO3.
- Use multiprocessing or asyncio to circumvent GIL limitations where appropriate.
- Profile and optimize critical paths.

## Notes
This decision is based on the existing codebase and the suitability of Python for AI applications. We will revisit this decision if we encounter significant limitations that cannot be mitigated.