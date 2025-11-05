# ADR-003: Estrategia de Testing y Optimización

**Fecha**: 31 de octubre de 2025  
**Estado**: Aceptado  
**Decisores**: Equipo de desarrollo  

## Contexto y Problema

Necesitamos establecer una estrategia de testing que sea:
- **Rápida**: Feedback inmediato durante desarrollo
- **Completa**: Cobertura adecuada de funcionalidad  
- **Mantenible**: Fácil de entender y actualizar
- **Escalable**: Que funcione conforme crezca el proyecto

### Desafíos Específicos:
- Tests de bcrypt lentos (100-200ms por hash)
- Organización confusa por tipos de test
- Feedback visual pobre durante ejecución
- Falta de paralelización en tests

## Opciones Consideradas

1. **Testing Básico**: pytest simple sin optimizaciones
2. **Testing Optimizado**: Paralelización + optimizaciones específicas
3. **Testing Avanzado**: Herramientas complejas (tox, coverage, etc.)
4. **Testing Mínimo**: Solo tests esenciales

## Decisión

**Implementamos Testing Optimizado** con:

### 1. Framework y Herramientas:
- **pytest 8.3.0**: Framework principal
- **pytest-xdist 3.8.0**: Paralelización automática
- **httpx 0.27.0**: Cliente HTTP para tests de API

### 2. Optimizaciones de Performance:
- **bcrypt acelerado**: rounds=4 en tests vs rounds=12 en producción
- **Paralelización**: 7 workers concurrentes (CPU cores - 1)
- **Variable TESTING**: Detección automática de entorno de testing

### 3. Organización por Clean Architecture:
```
tests/
├── unit/                          # Tests unitarios
│   └── modules/user/domain/
│       ├── entities/              # Tests de entidades
│       ├── value_objects/         # Tests de Value Objects
│       └── repositories/          # Tests de interfaces
└── integration/                   # Tests de integración
    └── api/                       # Tests de endpoints
```

### 4. Script de Testing Personalizado:
- **dev_tests.py**: Presentación visual organizada
- **Separación por objetos**: User, Email, Password, etc.
- **Métricas en tiempo real**: Duración y estadísticas

## Justificación

### Optimización bcrypt:
```python
# Configuración inteligente por entorno
rounds = 4 if os.getenv('TESTING') == 'true' else 12

# Resultado:
# Producción: ~100ms (seguro)  
# Testing: ~5ms (16x más rápido)
```

**Justificación de Seguridad**:
- Producción mantiene seguridad completa (rounds=12)
- Tests obtienen funcionalidad completa pero acelerada  
- Variable TESTING solo existe durante pytest
- Cero impacto en seguridad de producción

### Paralelización Inteligente:
```python
# Detección automática de capacidad del sistema
workers = max(1, multiprocessing.cpu_count() - 1)  # 7 workers
cmd.extend(['-n', str(workers)])
```

**Beneficios**:
- Aprovecha todos los CPU cores disponibles
- Reserva 1 core para el sistema
- Fallback automático si xdist no está disponible

### Organización por Arquitectura:
```
🔬 TESTS UNITARIOS
  🏗️ CAPA DE DOMINIO
    📦 ENTIDADES
      👤 User (18/18 tests - 100%)
    💎 VALUE OBJECTS  
      🆔 User ID (12/12 tests - 100%)
      📧 Email (14/14 tests - 100%)
      🔐 Password (23/23 tests - 100%)
```

**Ventajas**:
- Refleja estructura del código fuente
- Fácil identificar qué componente falla
- Escalable para nuevos módulos
- Educativo para entender arquitectura

## Resultados Obtenidos

### Performance Mejorada:
| Métrica | Antes | Después | Mejora |
|---------|--------|---------|--------|
| Tiempo Total | ~5+ segundos | 0.54s | **90% reducción** |
| CPU Usage | ~100% | 319% | **Paralelización** |
| Tests bcrypt | ~100ms cada uno | ~5ms cada uno | **95% reducción** |

### Organización Clara:
- **80 tests** organizados por componente
- **100% pass rate** mantenido  
- **Feedback visual** inmediato y claro
- **Zero configuración** manual requerida

## Implementación Técnica

### 1. Configuración Automática (conftest.py):
```python
# Configuración automática para acelerar bcrypt
os.environ['TESTING'] = 'true'
```

### 2. Script Inteligente (dev_tests.py):
```python
# Paralelización automática con fallback
try:
    if importlib.util.find_spec("xdist") is not None:
        workers = max(1, multiprocessing.cpu_count() - 1)
        cmd.extend(['-n', str(workers)])
except ImportError:
    # Fallback a ejecución secuencial
    pass
```

### 3. Categorización Inteligente:
- Detección automática por rutas de archivos
- Separación por objetos específicos (User, Email, etc.)  
- Presentación solo de secciones con tests reales

## Consecuencias

### Positivas:
- ✅ **Feedback ultra-rápido**: 0.54s para 80 tests
- ✅ **Desarrollo ágil**: Tests no interrumpen el flujo
- ✅ **Organización clara**: Fácil ubicar problemas
- ✅ **Escalabilidad**: Preparado para cientos de tests
- ✅ **Cero configuración**: Funciona out-of-the-box

### Negativas:
- ❌ **Complejidad inicial**: Script personalizado para mantener
- ❌ **Dependencia adicional**: pytest-xdist requerido
- ❌ **Configuración específica**: Lógica de detección de entorno

### Riesgos Mitigados:
- **Seguridad bcrypt**: Solo afecta testing, producción intacta
- **Paralelización**: Fallback automático si no está disponible
- **Mantenimiento**: Script bien documentado y modular

## Aislamiento de la Base de Datos en Tests de Integración

### Problema Adicional Identificado

Durante la implementación de los tests de integración que interactúan con la base de datos, se detectó un problema crítico al ejecutar las pruebas en paralelo con `pytest-xdist`:

-   **Condiciones de Carrera**: Múltiples procesos de prueba intentaban crear y destruir tablas (`metadata.create_all()`, `metadata.drop_all()`) en la **misma base de datos de prueba** simultáneamente.
-   **Errores de Integridad**: Esto provocaba errores `sqlalchemy.exc.IntegrityError` intermitentes y poco predecibles, ya que un proceso intentaba crear un esquema que ya existía o acceder a tablas que otro proceso estaba eliminando.

### Decisión de Aislamiento

Para resolver este problema y garantizar que los tests de integración sean **atómicos, independientes y fiables**, se implementó una estrategia de aislamiento completo a nivel de base de datos.

La fixture `client` en `tests/conftest.py` fue refactorizada para:

1.  **Detectar el Worker ID**: Identifica el ID del proceso trabajador asignado por `pytest-xdist` (ej. `gw0`, `gw1`).
2.  **Crear una Base de Datos Única**: Antes de que se ejecute cada test, se crea una base de datos PostgreSQL completamente nueva con un nombre único que incluye el `worker_id` (ej. `test_db_gw0`).
3.  **Ejecutar el Test**: El test se ejecuta contra esta base de datos temporal y aislada.
4.  **Destruir la Base de Datos**: Una vez que el test finaliza, la base de datos temporal se destruye por completo.

### Justificación

-   **Aislamiento Total**: Elimina cualquier posibilidad de que los tests paralelos interfieran entre sí a nivel de datos.
-   **Fiabilidad**: Los fallos en los tests de integración ahora se deben de manera inequívoca a problemas en el código de la aplicación, no a la configuración del entorno de pruebas.
-   **Estado Limpio Garantizado**: Cada test comienza con un esquema de base de datos limpio, asegurando la reproducibilidad de los resultados.

### Consecuencias

-   **Positivas**:
    -   ✅ **Tests 100% fiables** en entorno paralelo.
    -   ✅ Depuración de tests de integración mucho más sencilla.
-   **Negativas**:
    -   ❌ **Ligero aumento en el tiempo de setup/teardown** de cada test de integración debido a la creación/destrucción de la base de datos. Sin embargo, este coste es marginal comparado con el beneficio de la paralelización y la fiabilidad.

## Validación de Decisión

### Criterios de Éxito:
- [x] **Tests < 2 segundos**: ✅ 0.54s (superado)
- [x] **100% pass rate**: ✅ 80/80 tests passing
- [x] **Feedback claro**: ✅ Organización por arquitectura
- [x] **Fácil debugging**: ✅ Identificación rápida de problemas

### Métricas Actuales (31 Oct 2025):
```
📊 PERFORMANCE
- Ejecución: 0.54s (meta: <2s) ✅
- Paralelización: 7 workers ✅  
- Tests totales: 80 (100% passing) ✅
- Mejora rendimiento: 90% ✅

📈 ORGANIZACIÓN
- Capas arquitectura: Clara separación ✅
- Objetos específicos: User, Email, Password ✅  
- Feedback visual: Iconos y colores ✅
- Solo secciones reales: Sin ruido ✅
```

## Evolución Futura

### Próximas Optimizaciones:
1. **Coverage Reports**: Integrar cobertura de código
2. **Test Fixtures**: Fixtures compartidas más sofisticadas  
3. **Mocking Avanzado**: Para servicios externos
4. **Performance Profiling**: Detectar tests lentos automáticamente

### Escalabilidad Planificada:
- **Tests de integración**: Base de datos, APIs externas
- **Tests E2E**: Flujos completos de usuario
- **Tests de carga**: Performance bajo estrés
- **Tests de contrato**: APIs entre servicios

## Referencias

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-xdist Plugin](https://pytest-xdist.readthedocs.io/)
- [Testing Best Practices](https://testing.googleblog.com/)
- [Clean Architecture Testing](https://blog.cleancoder.com/uncle-bob/2014/05/14/TheLittleMocker.html)

## Notas de Implementación

### Comandos Clave:
```bash
# Ejecución optimizada completa
python dev_tests.py

# Ejecución rápida sin presentación  
python -m pytest --tb=no -q

# Debug específico con duración
python -m pytest tests/unit/modules/user/ -v --durations=10
```

### Archivos Clave:
- `tests/conftest.py`: Configuración global y optimizaciones
- `dev_tests.py`: Script de presentación personalizado  
- `requirements.txt`: Dependencias de testing documentadas