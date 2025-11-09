# ADR-015: Session Management Strategy - Progressive Implementation

**Estado**: ✅ Aceptado
**Fecha**: 9 Nov 2025

---

## Contexto

Necesitamos definir la estrategia de logout para tokens JWT: **invalidación inmediata vs. expiración natural**.

**Alternativas**:
1. **Token Blacklist**: Invalidación inmediata real (alta complejidad)
2. **Client-side Logout**: Token válido hasta expiración (baja complejidad) 
3. **Progressive Approach**: Implementación en fases

---

## Decisión

**Implementación progresiva en 2 fases** para balancear time-to-market y seguridad.

### Fase 1: Logout Simple (IMPLEMENTADO)
- **Enfoque**: Cliente elimina token localmente
- **Servidor**: Solo auditoría con `UserLoggedOutEvent`
- **Limitación**: Token técnicamente válido hasta expiración (24h)
- **Beneficio**: Logout funcional inmediato, arquitectura preparada

### Fase 2: Token Blacklist (FUTURO)
- **Enfoque**: Invalidación inmediata con blacklist persistente
- **Componentes**: `TokenBlacklistService`, middleware update
- **Trigger**: Cuando tengamos >1000 usuarios o requerimientos enterprise

---

## Justificación

**¿Por qué no blacklist inmediata?**
- Complejidad innecesaria para MVP
- 99% casos cubiertos con Fase 1
- Validación real de necesidades antes de over-engineering

**¿Por qué implementación progresiva?**
- Time-to-market inmediato
- Arquitectura extensible sin desperdicio
- Risk mitigation incremental

---

## Consecuencias

### Positivas
- ✅ Logout funcional inmediato
- ✅ Arquitectura preparada para evolución
- ✅ Balance óptimo complejidad/beneficio

### Negativas  
- ⚠️ Gap de seguridad temporal (tokens válidos post-logout)
- ⚠️ Requiere planificación de Fase 2

---

## Criterios de Migración a Fase 2

Migrar cuando se cumpla **cualquiera**:
- Incidentes de seguridad reportados
- Demanda de "logout all devices"
- Requerimientos de compliance
- +1000 usuarios activos

---

## Referencias

- [ADR-007: Domain Events Pattern](./ADR-007-domain-events-pattern.md)
- [ADR-006: Unit of Work Pattern](./ADR-006-unit-of-work-pattern.md)