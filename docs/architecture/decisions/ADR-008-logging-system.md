# ADR-008: Advanced Logging System

## Status
**ACCEPTED** - November 3, 2025

## Context

The Ryder Cup Manager needs a robust logging system that provides:
- **Complete observability** of the system in production
- **Traceability** of requests and operations
- **Efficient debugging** during development
- **Auditing** of critical domain events
- **Correlation** between events and operations
- **Flexible formatting** for different environments

### Identified Problems

1. **Basic logging**: Python's standard logging is insufficient for complex systems
2. **Lack of context**: Difficult to correlate related logs
3. **Inconsistent formats**: Different parts of the system log in different ways
4. **No integration**: No connection between Domain Events and logging
5. **Rigid configuration**: Difficult to adapt to different environments

## Decision

We implement an **Advanced Logging System** based on Clean Architecture with the following components:

### System Architecture

**Application Layer**: LoggerFactory (Singleton), get_logger() convenience function
**Domain Layer**: Logger interface, LogConfig configuration
**Infrastructure Layer**: PythonLogger implementation, Formatters (Text/JSON/Structured), EventHandlers

### Main Components

**1. Logger Interface**
- Methods: debug, info, warning, error, critical
- Context management: set_context(), with_correlation_id()
- Thread-safe by design

**2. Flexible Configuration**
- Predefined configs: development(), production(), testing()
- Customizable per environment
- Multiple handlers support

**3. Specialized Formatters**
- TextFormatter: Readable for development
- JsonFormatter: Structured for production
- StructuredFormatter: Hybrid with tree-view

**4. Integration with Domain Events**
- EventLoggingHandler: Automatic logging of domain events
- Enriched metadata and complete context
- Filtering by event type

### Implemented Patterns

1. **Dependency Inversion**: Logger interface + concrete implementations
2. **Factory Pattern**: LoggerFactory for centralized creation
3. **Singleton Pattern**: Global configuration management
4. **Strategy Pattern**: Different interchangeable formatters
5. **Observer Pattern**: Event handlers for automatic logging

## Alternatives Considered

### Option 1: Python Standard Logging
**Decision**: Rejected - Limited features, no context, basic formats

### Option 2: External Libraries (loguru, structlog)
**Decision**: Rejected - External dependencies, less control

### Option 3: Custom System (CHOSEN)
**Decision**: Accepted - Full control, perfect integration, no extra dependencies

## Consequences

### Positive ✅

1. **Complete Observability**: Structured JSON logs, correlation IDs, enriched context
2. **Configuration Flexibility**: Different configs per environment, multiple handlers
3. **Perfect Integration**: Automatic Domain Events logging, shared context
4. **Developer Experience**: Simple APIs, context managers, robust error handling
5. **Production Ready**: Thread-safe, file rotation, environment variables

### Negative ⚠️

1. **Additional Maintenance**: More custom code to maintain
2. **Learning Curve**: Project-specific APIs

### Mitigations 🛡️

- Complete documentation with examples
- Exhaustive test coverage
- Predefined configurations per environment

## Implementation

**Location**: `src/shared/infrastructure/logging/`

**Configuration per Environment**:
- Development: DEBUG level, console text format
- Production: INFO level, rotating file + JSON format (50MB rotation)
- Testing: WARNING level, null handler (silent)

**Usage**: `get_logger("module.name")` with context managers for correlation

## Success Metrics

### Functional ✅
- 100% test coverage
- 3 formatters working (Text, JSON, Structured)
- Domain Events automatically logged

### Non-Functional ✅
- Performance: <1ms overhead per log
- Thread Safety: Thread-local context
- Memory: No leaks in long tests
- Configuration: 3 predefined environments

## References

- [Clean Architecture Logging Patterns](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [12-Factor App Logging](https://12factor.net/logs)