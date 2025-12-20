# ADR-021: GitHub Actions para CI/CD Pipeline

**Fecha**: 30 de noviembre de 2025
**Estado**: Aceptado
**Decisores**: Equipo de desarrollo

## Contexto y Problema

El proyecto necesita un sistema de CI/CD que ejecute tests automáticamente, valide calidad de código, verifique migraciones de base de datos y soporte múltiples versiones de Python. Debe ser fácil de mantener, proporcionar feedback rápido y ser gratuito o de bajo costo.

## Opciones Consideradas

1. **GitHub Actions**: Integrado con GitHub, 2000 min/mes gratis (ilimitado para repos públicos)
2. **GitLab CI/CD**: 400 min/mes gratis, requiere migrar repositorio
3. **CircleCI**: 6000 min/mes gratis, requiere integración externa
4. **Jenkins (self-hosted)**: Control total, requiere servidor dedicado

## Decisión

**Adoptamos GitHub Actions** con la siguiente estructura:

```yaml
Pipeline Jobs:
├── preparation (setup Python + cache)
├── unit_tests (Python 3.11, 3.12 matrix)
├── integration_tests (con PostgreSQL service)
├── security_scan (Gitleaks)
├── code_quality (Ruff)
├── type_checking (Mypy)
└── database_migrations (Alembic validation)
```

### Configuración:
- **Matrix strategy**: Python 3.11 y 3.12
- **Caché de dependencias**: pip cache
- **PostgreSQL service**: Para integration tests
- **Paralelización**: Jobs independientes en paralelo

## Justificación

### Ventajas:

1. **Integración Nativa**
   - Workflow triggers automáticos (push, PR)
   - Secrets management integrado
   - Status checks visibles en PRs

2. **Costo y Performance**
   - Gratuito para repositorio público
   - Caché de dependencias reduce builds
   - Ejecución rápida (~3 minutos)

3. **Ecosystem**
   - Actions pre-construidas (setup-python, gitleaks)
   - Configuración YAML declarativa
   - Logs detallados

4. **Developer Experience**
   - Feedback rápido en PRs
   - Re-run de jobs individuales
   - Zero-config para contribuidores

## Consecuencias

### Positivas:
- ✅ Tests ejecutándose automáticamente en ~3 minutos
- ✅ Detección temprana de errores (types, linting, security)
- ✅ Validación de migraciones antes de merge
- ✅ Soporte multi-version Python

### Negativas:
- ❌ Vendor lock-in con GitHub (mitigado: YAML portable)
- ❌ Runners compartidos (performance variable)
- ❌ Logs borrados después de 90 días

### Riesgos Mitigados:
- **Límite de minutos**: Repo público = minutos ilimitados
- **Performance**: Caché reduce tiempo de build
- **Secrets exposure**: Gitleaks valida commits

## Validación

La decisión se considera exitosa si:
- [x] Pipeline ejecuta en < 5 minutos (✅ ~3 min)
- [x] Tests en Python 3.11 y 3.12 (✅ Matrix strategy)
- [x] Integration tests con PostgreSQL (✅ Service container)
- [x] Security scanning activo (✅ Gitleaks)
- [x] Code quality checks (✅ Ruff + Mypy)

## Referencias

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Python CI/CD Best Practices](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python)
- [Gitleaks Action](https://github.com/gitleaks/gitleaks-action)

## Notas de Implementación

### Implementado (30 Nov 2025):
- ✅ Pipeline completo en `.github/workflows/ci_cd_pipeline.yml`
- ✅ 7 jobs paralelos con dependencias optimizadas
- ✅ Mypy configurado pragmáticamente (SQLAlchemy imperative mapping)
- ✅ Gitleaks con `.gitleaksignore` para false positives
- ✅ Suite de tests completa ejecutándose en CI

### Lecciones Aprendidas:
- **Python compatibility**: PEP 695 syntax requiere 3.12+, usar `Generic[TypeVar]` para compatibilidad
- **Mypy strictness**: Balance pragmático por módulo (domain, infrastructure)
- **Gitleaks**: Whitelist específico con fingerprints, no glob patterns
- **Alembic**: `override=False` en `load_dotenv()` para precedencia de env vars
