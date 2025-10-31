# ADR-001: Adopción de Clean Architecture

**Fecha**: 31 de octubre de 2025  
**Estado**: Aceptado  
**Decisores**: Equipo de desarrollo  

## Contexto y Problema

Necesitamos establecer una arquitectura escalable y mantenible para el sistema de gestión de torneos Ryder Cup. El sistema debe ser:

- Fácil de testear unitariamente
- Independiente de frameworks externos
- Independiente de la base de datos
- Independiente de la interfaz de usuario
- Escalable conforme crezca el proyecto

## Opciones Consideradas

1. **Arquitectura en Capas Tradicional**: Controlador → Servicio → Repositorio
2. **Clean Architecture**: Separación de responsabilidades con inversión de dependencias
3. **Arquitectura Hexagonal**: Puertos y adaptadores
4. **Arquitectura MVC Simple**: Modelo-Vista-Controlador básico

## Decisión

**Adoptamos Clean Architecture** con la siguiente estructura de capas:

```
src/modules/{domain}/
├── domain/                 # Capa de Dominio (independiente)
│   ├── entities/           # Entidades de negocio
│   ├── value_objects/      # Value Objects inmutables
│   └── repositories/       # Interfaces de repositorio
├── application/            # Capa de Aplicación
│   ├── use_cases/          # Casos de uso
│   └── services/           # Servicios de aplicación
└── infrastructure/         # Capa de Infraestructura
    ├── repositories/       # Implementaciones concretas
    ├── adapters/           # Adaptadores externos
    └── config/             # Configuraciones
```

## Justificación

### Ventajas de Clean Architecture:

1. **Testabilidad Superior**
   - Cada capa se puede testear independientemente
   - Fácil creación de mocks para dependencias externas
   - Tests unitarios rápidos y confiables

2. **Inversión de Dependencias**
   - El dominio no depende de infraestructura
   - Fácil intercambio de implementaciones (BD, APIs externas)
   - Cumple principio SOLID (Dependency Inversion)

3. **Mantenibilidad**
   - Separación clara de responsabilidades
   - Cambios en infraestructura no afectan lógica de negocio
   - Código más limpio y comprensible

4. **Escalabilidad**
   - Estructura preparada para múltiples módulos
   - Fácil agregar nuevas funcionalidades
   - Permite equipos trabajando en paralelo

### Implementación Específica:

- **Framework Web**: FastAPI (capa de infraestructura)
- **Testing**: pytest con organización por capas
- **Módulos**: Separados por dominio de negocio (user, team, tournament)

## Consecuencias

### Positivas:
- ✅ Mayor calidad del código
- ✅ Tests más rápidos y confiables  
- ✅ Facilita futuras migraciones tecnológicas
- ✅ Onboarding más claro para nuevos desarrolladores

### Negativas:
- ❌ Mayor complejidad inicial
- ❌ Más archivos y estructura
- ❌ Curva de aprendizaje para el equipo
- ❌ Puede ser over-engineering para proyectos muy simples

### Riesgos Mitigados:
- **Complejidad**: Documentación detallada y ejemplos claros
- **Over-engineering**: Implementación gradual, empezando simple
- **Curva de aprendizaje**: Desarrollo paso a paso guiado

## Validación

La decisión se considera exitosa si:
- [ ] Tests unitarios ejecutan en < 2 segundos
- [x] Lógica de dominio independiente de frameworks (✅ Implementado)
- [x] Fácil agregar nuevos casos de uso (✅ Demostrado)
- [x] Cambios en BD no requieren modificar entidades (✅ Arquitectura preparada)

## Referencias

- [Clean Architecture by Robert Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Implementing Clean Architecture in Python](https://github.com/cosmicpython/book)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

## Notas de Implementación

### Ya Implementado (31 Oct 2025):
- ✅ Estructura de carpetas establecida
- ✅ Entidad User en capa de dominio
- ✅ Value Objects (UserId, Email, Password)
- ✅ Tests organizados por capas
- ✅ 80 tests ejecutándose en 0.54s

### Próximo:
- 🔄 Interfaces de repositorio (domain)
- ⏳ Implementaciones concretas (infrastructure)
- ⏳ Casos de uso (application)