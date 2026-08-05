# ADR-002: Choose initial technology stack

## Status
Accepted

## Date
2026-08-04

## Context
Having chosen Python as the primary language (ADR-001), we need to select the rest of the technology stack for the GalSen IA platform. The stack should support building a scalable AI platform with microservices, APIs, data storage, and machine learning capabilities. We aim for a balance between development speed, performance, and community support.

## Decision
We select the following technologies for the initial stack:

- **Language**: Python 3.9+ (as per ADR-001)
- **Web Framework**: FastAPI for building high-performance APIs with automatic OpenAPI documentation.
- **API Gateway**: Kong or AWS API Gateway (to be decided later based on deployment environment).
- **Service Communication**: REST/JSON for synchronous communication, Apache Kafka or RabbitMQ for asynchronous event-driven communication.
- **Data Storage**:
  - Primary Relational Database: PostgreSQL for its reliability, features, and strong community.
  - Caching: Redis for fast caching and pub/sub.
  - Object Storage: Amazon S3 or MinIO for storing large binary files (images, documents).
  - Search: Elasticsearch for full-text search capabilities (if needed beyond basic search).
- **Machine Learning Libraries**:
  - Core: PyTorch for deep learning research and production.
  - Traditional ML: scikit-learn for traditional machine learning algorithms.
  - NLP: spaCy for industrial-strength natural language processing.
  - Computer Vision: OpenCV for real-time computer vision and Pillow for image processing.
- **Configuration Management**: Pydantic for settings management and data validation.
- **Dependency Management**: Poetry for dependency resolution and packaging.
- **Testing**: Pytest for unit and integration testing, with pytest-asyncio for asynchronous tests.
- **Documentation**: MkDocs with Material theme for project documentation.
- **Observability**:
  - Logging: Structlog for structured logging.
  - Metrics: Prometheus client for Python.
  - Tracing: OpenTelemetry for distributed tracing.
- **Containerization**: Docker for containerizing services.
- **Orchestration**: Kubernetes (K8s) for orchestration in production; Docker Compose for local development.
- **CI/CD**: GitHub Actions for continuous integration and deployment.
- **Security**: OWASP guidelines, using libraries like passlib for hashing, and cryptography for encryption needs.

## Consequences
### Positive
- Provides a robust, scalable foundation for building AI services.
- Leverages mature, well-supported technologies with large communities.
- Enables rapid development with FastAPI and Pydantic.
- Facilitates deployment and scaling with Docker and Kubernetes.
- Meets enterprise requirements for security and observability.

### Negative
- Some technologies (like Kubernetes) have a steep learning curve.
- Licensing considerations for certain libraries (though all chosen are open-source with permissive licenses).
- Initial setup complexity may be higher than a minimal stack.

### Mitigations
- Start with a minimal viable product-specifications
  - Use the same set of technologies across services to reduce cognitive overhead.
  - Provide internal documentation and templates for new services.
  - Use managed services where possible (e.g., AWS RDS for PostgreSQL, Elasticache for Redis) to reduce operational overhead.
- For learning, invest in training and documentation.
- We can start with a simpler setup (e.g., SQLite for development) and migrate to PostgreSQL as needed.

## Notes
This stack is subject to evolution as the project grows and requirements change. We will review and update the stack periodically through new ADRs.