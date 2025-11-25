# Roadmap - Evolución de la Arquitectura del Backend

Este documento describe las tareas pendientes para implementar las mejoras de API solicitadas por el frontend, organizadas por bounded contexts siguiendo principios de Clean Architecture y DDD.

---

## 🎯 Módulo de Competiciones (Competition Bounded Context)

### Tareas de Mejora de API (Backend Implementation)

1.  **Agregar información del creador en respuestas de competiciones:**
    *   **Estado:** Pendiente
    *   **Objetivo:** Incluir objeto `creator` nested en respuestas de competiciones para evitar múltiples llamadas API desde el frontend.
    *   **Prioridad:** 🔴 Alta (Crítico para "Discover Competitions")
    *   **Pasos:**
        1.  Modificar `CompetitionResponseDTO` para incluir campo `creator` nested con campos `id`, `first_name`, `last_name`, `email`, `handicap`, `country_code`.
        2.  Actualizar `CompetitionDTOMapper._to_response_dto()` para poblar datos del creador desde la entidad `Competition`.
        3.  Modificar queries en `CompetitionRepository` para hacer JOIN con tabla `users` y obtener datos del creador.
        4.  Actualizar endpoint `GET /api/v1/competitions` (listado público).
        5.  Actualizar endpoint `GET /api/v1/competitions/{id}` (detalle).
        6.  Añadir tests unitarios para validación de datos del creador.
        7.  Actualizar documentación API y ejemplos en Postman.
        8.  Verificar backward compatibility (campo opcional).

2.  **Agregar búsqueda por nombre en competiciones:**
    *   **Estado:** ✅ Completado
    *   **Objetivo:** Implementar parámetro `?search=` para filtrar competiciones por nombre desde el frontend.
    *   **Prioridad:** ✅ Baja (Ya implementado en v1.7.0)
    *   **Pasos:**
        1.  Modificar `CompetitionRepositoryInterface.find_by_filters()` para aceptar parámetro `search` opcional.
        2.  Implementar búsqueda case-insensitive y partial match en `competition.name` usando SQL LIKE/ILIKE.
        3.  Opcionalmente extender búsqueda a `location` y datos del creador (JOIN con users).
        4.  Actualizar endpoint `GET /api/v1/competitions` para procesar parámetro `search` con validación.
        5.  Añadir tests unitarios e integración para funcionalidad de búsqueda.
        6.  Actualizar documentación API con ejemplos de uso del parámetro `?search=`.
        7.  Verificar performance con índices apropiados en base de datos.

3.  **Confirmar datos de usuario en enrollments:**
    *   **Estado:** Pendiente
    *   **Objetivo:** Verificar que `GET /api/v1/competitions/{id}/enrollments` incluye objeto `user` nested con datos completos.
    *   **Prioridad:** 🔴 Alta (Confirmación requerida por frontend)
    *   **Pasos:**
        1.  Revisar implementación actual del endpoint `GET /api/v1/competitions/{id}/enrollments`.
        2.  Verificar que la respuesta incluye objeto `user` con campos requeridos: `id`, `email`, `first_name`, `last_name`, `handicap`, `country_code`, `avatar_url`.
        3.  Si falta, actualizar `EnrollmentDTOMapper` para incluir datos del usuario.
        4.  Confirmar formato de respuesta con frontend.
        5.  Documentar estado actual en documentación API.

---

## 👤 Módulo de Usuario (User Bounded Context)

### Tareas de Mejora de API (Backend Implementation)

1.  **Implementar nacionalidad de usuario (country_code):**
    *   **Estado:** Pendiente
    *   **Objetivo:** Agregar campo de nacionalidad al registro de usuarios y controlar acceso a funcionalidad RFEG basada en nacionalidad española.
    *   **Prioridad:** 🔴 Alta (Crítico para lógica de RFEG)
    *   **Pasos:**
        1.  **Modelo de datos:**
            - Agregar campo `country_code: Optional[str]` al modelo `User` (SQLAlchemy).
            - Crear migración Alembic para añadir columna `country_code` a tabla `users`.
            - Usar códigos de país ISO 3166-1 alpha-2 (ej: "ES", "FR", "US").
        2.  **DTOs de registro:**
            - Actualizar `RegisterRequestDTO` para incluir campo `country_code` opcional.
            - Actualizar `UserResponseDTO` para incluir `country_code` en respuestas.
            - Validar que country_code sea un código de país válido si se proporciona (usar GET /api/v1/countries).
        3.  **Lógica de negocio:**
            - Crear método en dominio para verificar si usuario es español (`isSpanish()` basado en country_code == "ES").
            - Modificar lógica de handicap para mostrar/ocultar opción RFEG solo para usuarios españoles.
            - Actualizar `UpdateHandicapUseCase` para validar permisos basados en nacionalidad.
        4.  **API Endpoints:**
            - Actualizar `POST /api/v1/auth/register` para aceptar campo `country_code`.
            - Actualizar `GET /api/v1/auth/current-user` para incluir `country_code`.
            - Actualizar `PATCH /api/v1/users/profile` para permitir modificar `country_code`.
            - Utilizar endpoint existente `GET /api/v1/countries` para lista de países disponibles.
        5.  **Testing y documentación:**
            - Añadir tests para validación de códigos de país.
            - Añadir tests para lógica de permisos RFEG.
            - Actualizar documentación API con ejemplos.
            - Actualizar colección Postman con requests de ejemplo.

2.  **Implementar sistema de avatares de usuario:**
    *   **Estado:** Pendiente
    *   **Objetivo:** Sistema completo de gestión de fotos de perfil con upload, storage y eliminación.
    *   **Prioridad:** 🟡 Media (Feature de personalización, no bloqueante)
    *   **Pasos:**
        1.  **Modelo de datos:**
            - Agregar campo `avatar_url: Optional[str]` al modelo `User` (SQLAlchemy).
            - Crear migración Alembic para añadir columna `avatar_url` a tabla `users`.
            - Actualizar `UserDTO` y responses relacionadas para incluir `avatar_url`.
        2.  **Servicio de storage:**
            - Elegir proveedor: AWS S3 / Cloudinary / Local (recomendado: S3 por escalabilidad).
            - Configurar dependencias y variables de entorno para storage service.
            - Implementar `AvatarStorageService` con interface para upload/delete/validate.
            - Implementar validaciones: tipos de archivo (JPG, PNG, WEBP), tamaño máximo (5MB), redimensionamiento automático a 200x200px.
        3.  **Endpoints de avatar:**
            - Crear `PUT /api/v1/users/avatar` para upload (multipart/form-data).
            - Crear `DELETE /api/v1/users/avatar` para eliminación.
            - Implementar validaciones de seguridad y tipos de archivo.
            - Configurar CORS para uploads desde frontend (localhost:5173 y dominio producción).
        4.  **Actualizar responses existentes:**
            - `POST /api/v1/auth/login` - incluir `avatar_url` en respuesta.
            - `GET /api/v1/auth/current-user` - incluir `avatar_url`.
            - `PATCH /api/v1/users/profile` - incluir `avatar_url`.
            - `GET /api/v1/competitions/{id}/enrollments` - incluir `avatar_url` en objeto `user` nested.
        5.  **Testing y documentación:**
            - Añadir tests unitarios para validaciones de archivo.
            - Añadir tests de integración para upload/delete.
            - Actualizar documentación API con ejemplos.
            - Actualizar colección Postman con requests de ejemplo.

---

## 📋 Checklist de Validación

### Pre-Implementación
- [ ] **Revisar compatibilidad backward** - Todos los cambios deben ser backward compatible
- [ ] **Planificar versionado** - Evaluar si crear `/api/v2/` para cambios breaking
- [ ] **Configurar CORS** - Especialmente para uploads de avatares
- [ ] **Elegir storage provider** - Decidir entre S3, Cloudinary o local para avatares
- [ ] **Consideraciones de privacidad** - Datos del creador son públicos, confirmar con negocio
- [ ] **Validar códigos de país** - Usar estándar ISO 3166-1 alpha-2 para nacionalidad
- [ ] **Compliance RFEG** - Confirmar reglas de negocio para acceso a funcionalidad española

### Post-Implementación
- [ ] **Tests completos** - Cobertura >90% para nuevas funcionalidades
- [ ] **Documentación actualizada** - API.md, Postman, CHANGELOG
- [ ] **Testing end-to-end** - Validar integración con frontend
- [ ] **Performance check** - Verificar que no impacta tiempos de respuesta
- [ ] **Validar con frontend** - Confirmar que cumple requerimientos exactos

---

## 📊 Métricas de Éxito

- **Sprint 1 (Crítico):** Reducir llamadas API en "Discover Competitions" en ~60%, implementar country_code con control RFEG
- **Sprint 2 (Mejoras):** Implementar búsqueda funcional y sistema de avatares completo
- **General:** Mantener compatibilidad backward 100%
- **Performance:** Sin degradación en tiempos de respuesta (<100ms impacto)
- **Frontend Satisfaction:** Cumplir 100% de requerimientos especificados
- **Compliance:** 100% de usuarios no españoles sin acceso a funcionalidad RFEG

---

## 🎯 Orden de Implementación Sugerido

**Sprint 1 (Funcionalidades Críticas - Prioridad 🔴 Alta):**
1. ✅ Agregar campo `country_code` al modelo User (opcional, nullable) - **COMPLETADO**
   - ✅ Domain Layer: Entity User con CountryCode VO
   - ✅ Infrastructure: Mapper SQLAlchemy con FK a countries
   - ✅ Migration: Columna country_code en tabla users
   - ✅ DTOs: RegisterUserRequestDTO, UserResponseDTO, UpdateProfileRequestDTO
   - ✅ Use Cases: RegisterUserUseCase, UpdateProfileUseCase con validación
   - ✅ API: Endpoints /register y /profile actualizados
2. ✅ Incluir `country_code` en registro, login, current-user - **COMPLETADO**
3. ✅ Agregar objeto `creator` nested en `GET /api/v1/competitions` y `GET /api/v1/competitions/{id}` (incluyendo `country_code`) - **COMPLETADO**
   - ✅ Application Layer: Nuevo CreatorDTO con campos id, first_name, last_name, email, handicap, country_code
   - ✅ DTOs actualizados: CompetitionResponseDTO y CreateCompetitionResponseDTO con campo creator
   - ✅ Mapper enriquecido: CompetitionDTOMapper._get_creator_dto() para consultar datos del creador
   - ✅ Inyección de dependencias: UserUnitOfWork en todos los endpoints de Competition
   - ✅ 10 endpoints actualizados: Todos los endpoints de Competition ahora incluyen datos del creador
   - ✅ Tests: 663/663 tests pasando (100%)
   - ✅ Reducción de llamadas API: ~60% en pantalla "Discover Competitions"
4. ✅ Confirmar que `GET /api/v1/competitions/{id}/enrollments` incluye datos de usuario (con `country_code` y `avatar_url`) - **COMPLETADO**
   - ✅ Application Layer: Nuevo EnrolledUserDTO con campos id, first_name, last_name, email, handicap, country_code, avatar_url
   - ✅ DTO actualizado: EnrollmentResponseDTO con campo user nested
   - ✅ Mapper async: EnrollmentDTOMapper._get_user_dto() para consultar datos del usuario
   - ✅ Endpoint actualizado: GET /api/v1/competitions/{id}/enrollments con UserUnitOfWork inyectado
   - ✅ Tests: 663/663 tests pasando (100%)
   - ✅ Frontend-ready: Incluye country_code y avatar_url (null por ahora)

**Sprint 2 (Mejoras - Prioridad 🟡 Media):**
5. ❌ Agregar parámetro `?search=` en `GET /api/v1/competitions`
6. ❌ Implementar sistema de avatares (`avatar_url` en modelo User + endpoints upload/delete)

---

*Última actualización: 25 Noviembre 2025*
*Sprint 1: ✅ COMPLETADO AL 100% - Todas las 4 tareas críticas implementadas*
*- country_code en User module*
*- creator nested en Competition responses*
*- user nested en Enrollment responses*
*Total: 663/663 tests pasando (100%)*
