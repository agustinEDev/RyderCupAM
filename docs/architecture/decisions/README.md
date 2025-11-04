# Architecture Decision Records (ADRs)

Este directorio contiene las decisiones arquitectónicas importantes tomadas durante el desarrollo del sistema de gestión de torneos Ryder Cup.

**📍 Ubicación**: `docs/architecture/decisions/`  
**Propósito**: Documentar decisiones técnicas y arquitectónicas con impacto a largo plazo

## 📋 Índice de ADRs

| ADR | Título | Estado | Fecha | Impacto |
|-----|--------|--------|-------|---------|
| [ADR-001](./ADR-001-clean-architecture.md) | Adopción de Clean Architecture | ✅ Aceptado | 31 Oct 2025 | 🔥 Alto |
| [ADR-002](./ADR-002-value-objects.md) | Implementación de Value Objects | ✅ Aceptado | 31 Oct 2025 | 🔥 Alto |
| [ADR-003](./ADR-003-testing-strategy.md) | Estrategia de Testing y Optimización | ✅ Aceptado | 31 Oct 2025 | 🟡 Medio |
| [ADR-004](./ADR-004-tech-stack.md) | Stack Tecnológico y Herramientas | ✅ Aceptado | 31 Oct 2025 | 🔥 Alto |
| [ADR-005](./ADR-005-repository-pattern.md) | Repository Pattern Implementation | ✅ Aceptado | 1 Nov 2025 | 🔥 Alto |
| [ADR-006](./ADR-006-unit-of-work-pattern.md) | Unit of Work for Transaction Management | ✅ Aceptado | 1 Nov 2025 | 🔥 Alto |
| [ADR-007](./ADR-007-domain-events-pattern.md) | Domain Events for Event-Driven Architecture | ✅ Aceptado | 1 Nov 2025 | 🔥 Alto |
| [ADR-008](./ADR-008-logging-system.md) | Sistema de Logging Avanzado | ✅ Aceptado | 3 Nov 2025 | 🟡 Medio |
| [ADR-009](./ADR-009-docker-for-development-environment.md) | Uso de Docker para el Entorno de Desarrollo | ✅ Aceptado | 4 Nov 2025 | 🔥 Alto |
| [ADR-010](./ADR-010-alembic-for-database-migrations.md) | Uso de Alembic para Migraciones de BD | ✅ Aceptado | 4 Nov 2025 | 🔥 Alto |

## 📊 Resumen de Decisiones por Área

### 🏗️ **Arquitectura y Diseño**
- **[ADR-001](./ADR-001-clean-architecture.md)**: Clean Architecture con separación en capas.
- **[ADR-002](./ADR-002-value-objects.md)**: Value Objects inmutables para conceptos de dominio.
- **[ADR-005](./ADR-005-repository-pattern.md)**: Repository Pattern para abstracción de datos.
- **[ADR-006](./ADR-006-unit-of-work-pattern.md)**: Unit of Work para gestión transaccional.
- **[ADR-007](./ADR-007-domain-events-pattern.md)**: Domain Events para arquitectura event-driven.

### 🔧 **Tecnología y Herramientas**  
- **[ADR-004](./ADR-004-tech-stack.md)**: Python 3.12 + FastAPI + bcrypt + pytest como stack principal.
- **[ADR-008](./ADR-008-logging-system.md)**: Sistema de logging modular con formatters múltiples.
- **[ADR-009](./ADR-009-docker-for-development-environment.md)**: Docker y Docker Compose para un entorno de desarrollo consistente.
- **[ADR-010](./ADR-010-alembic-for-database-migrations.md)**: Alembic para la gestión versionada del esquema de la base de datos.

### 🧪 **Testing y Calidad**
- **[ADR-003](./ADR-003-testing-strategy.md)**: pytest con paralelización y organización por capas.