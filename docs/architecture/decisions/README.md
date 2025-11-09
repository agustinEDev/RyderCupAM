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
| [ADR-011](./ADR-011-application-layer-use-cases.md) | Capa de Aplicación con Casos de Uso | ✅ Aceptado | 5 Nov 2025 | 🔥 Alto |
| [ADR-012](./ADR-012-composition-root.md) | Patrón Composition Root | ✅ Aceptado | 5 Nov 2025 | 🔥 Alto |
| [ADR-013](./ADR-013-external-services-pattern.md) | External Services Pattern | ✅ Aceptado | 9 Nov 2025 | 🔥 Alto |
| [ADR-014](./ADR-014-handicap-management-system.md) | Handicap Management System | ✅ Aceptado | 9 Nov 2025 | 🔥 Alto |

## 📊 Resumen de Decisiones por Área

### 🏗️ **Arquitectura y Diseño**
- **[ADR-001](./ADR-001-clean-architecture.md)**: Clean Architecture con separación en capas.
- **[ADR-002](./ADR-002-value-objects.md)**: Value Objects inmutables para conceptos de dominio.
- **[ADR-005](./ADR-005-repository-pattern.md)**: Repository Pattern para abstracción de datos.
- **[ADR-006](./ADR-006-unit-of-work-pattern.md)**: Unit of Work para gestión transaccional.
- **[ADR-007](./ADR-007-domain-events-pattern.md)**: Domain Events para arquitectura event-driven.
- **[ADR-011](./ADR-011-application-layer-use-cases.md)**: Casos de Uso para orquestar la lógica de aplicación.
- **[ADR-012](./ADR-012-composition-root.md)**: Composition Root para inyección de dependencias.

### 🔧 **Tecnología y Herramientas**  
- **[ADR-004](./ADR-004-tech-stack.md)**: Python 3.12 + FastAPI + bcrypt + pytest como stack principal.
- **[ADR-008](./ADR-008-logging-system.md)**: Sistema de logging modular con formatters múltiples.
- **[ADR-009](./ADR-009-docker-for-development-environment.md)**: Docker y Docker Compose para un entorno de desarrollo consistente.
- **[ADR-010](./ADR-010-alembic-for-database-migrations.md)**: Alembic para la gestión versionada del esquema de la base de datos.

### 🧪 **Testing y Calidad**
- **[ADR-003](./ADR-003-testing-strategy.md)**: pytest con paralelización, aislamiento de BD por worker y organización por capas.

### 🔄 **Integraciones Externas**
- **[ADR-013](./ADR-013-external-services-pattern.md)**: External Services Pattern para integración con servicios externos (RFEG).
- **[ADR-014](./ADR-014-handicap-management-system.md)**: Sistema de gestión de hándicaps con Value Objects, Domain Events y servicios externos.