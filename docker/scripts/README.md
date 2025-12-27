# Docker Validation Scripts

Este directorio contiene scripts de validación fail-fast para garantizar que las variables de entorno requeridas estén configuradas correctamente antes de que los servicios Docker inicien.

## 📋 Scripts Disponibles

### 1. `validate-postgres-env.sh`

**Propósito:** Valida las variables de entorno requeridas para el servicio PostgreSQL antes de que la base de datos inicie.

**Variables validadas:**
- `POSTGRES_USER` - Usuario de PostgreSQL (requerido)
- `POSTGRES_PASSWORD` - Contraseña del usuario (requerido)
- `POSTGRES_DB` - Nombre de la base de datos (requerido)

**Comportamiento:**
- ✅ **Éxito:** Si todas las variables están configuradas, el script permite que PostgreSQL inicie normalmente
- ❌ **Fallo:** Si alguna variable falta, el script:
  - Imprime un mensaje de error claro y detallado
  - Proporciona ejemplos de configuración
  - Sale con código de error 1 (el contenedor no inicia)

**Ejemplo de salida en caso de error:**
```
🔍 Validating PostgreSQL environment variables...
❌ ERROR: Required environment variable 'POSTGRES_USER' is not set or is empty
✓ POSTGRES_PASSWORD is set
✓ POSTGRES_DB is set

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAIL-FAST VALIDATION FAILED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please ensure your .env file exists and contains:
  - POSTGRES_USER
  - POSTGRES_PASSWORD
  - POSTGRES_DB
```

### 2. `validate-app-env.sh`

**Propósito:** Valida las variables de entorno requeridas para la aplicación FastAPI antes de que inicie.

**Variables requeridas (críticas):**
- `POSTGRES_USER` - Usuario de PostgreSQL
- `POSTGRES_PASSWORD` - Contraseña de PostgreSQL
- `POSTGRES_DB` - Nombre de la base de datos
- `SECRET_KEY` - Clave secreta para JWT

**Variables opcionales (advertencia):**
- `MAILGUN_API_KEY` - API key de Mailgun
- `DOCS_USERNAME` - Usuario para Swagger docs
- `DOCS_PASSWORD` - Contraseña para Swagger docs

**Comportamiento:**
- ✅ **Éxito:** Si todas las variables requeridas están configuradas, permite que la aplicación inicie
- ⚠️  **Advertencia:** Si faltan variables opcionales, muestra advertencias pero continúa
- ❌ **Fallo:** Si falta alguna variable requerida, el script:
  - Imprime un mensaje de error detallado
  - Proporciona ejemplos de configuración
  - Sale con código de error 1 (el contenedor no inicia)

### 3. `test-validation.sh`

**Propósito:** Script de prueba automatizado para verificar que los scripts de validación funcionan correctamente.

**Tests incluidos:**
- Test de variables faltantes (debe fallar)
- Test de variables configuradas (debe pasar)

## 🚀 Uso

Los scripts se ejecutan automáticamente mediante el `docker-compose.yml`:

```yaml
services:
  db:
    volumes:
      - ./docker/scripts/validate-postgres-env.sh:/validate-postgres-env.sh:ro
    entrypoint: ["/bin/sh", "/validate-postgres-env.sh"]

  app:
    volumes:
      - ./docker/scripts/validate-app-env.sh:/validate-app-env.sh:ro
    entrypoint: ["/bin/sh", "/validate-app-env.sh"]
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

## 🧪 Ejecutar Tests

Para probar manualmente los scripts de validación:

```bash
# Ejecutar suite completa de tests
./docker/scripts/test-validation.sh

# Probar script de PostgreSQL manualmente
export POSTGRES_USER="test"
export POSTGRES_PASSWORD="test"
export POSTGRES_DB="test"
./docker/scripts/validate-postgres-env.sh
```

## 🔧 Configuración

### Archivo `.env` Requerido

Los scripts esperan que exista un archivo `.env` en la raíz del proyecto con las siguientes variables:

```bash
# Database Configuration (REQUIRED)
POSTGRES_USER=rydercupam_adminuser
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=rydercupam_db

# Security Configuration (REQUIRED)
SECRET_KEY=your_secret_key_here

# Optional Configuration
MAILGUN_API_KEY=your_mailgun_key
DOCS_USERNAME=admin
DOCS_PASSWORD=secure_password
```

### Crear desde Ejemplo

Si no tienes un archivo `.env`, copia el ejemplo:

```bash
cp .env.example .env
# Edita .env con tus valores
```

## 🎯 Beneficios

1. **Fail-Fast:** Los errores de configuración se detectan inmediatamente, no después de minutos de espera
2. **Mensajes Claros:** Errores descriptivos que indican exactamente qué falta y cómo solucionarlo
3. **Prevención de Problemas:** Evita healthcheck failures y errores confusos de PostgreSQL
4. **Mejora DX:** Desarrollo más rápido al detectar problemas de configuración de inmediato

## 📝 Notas Técnicas

- Los scripts usan **shell POSIX** (`/bin/sh`) para compatibilidad máxima con Alpine Linux
- Los volúmenes están montados en modo **read-only** (`:ro`) por seguridad
- El `docker-compose.yml` marca `env_file` como `required: false` para permitir que nuestros scripts manejen el error
- Los scripts son compatibles con entrypoints estándar de Docker (`docker-entrypoint.sh`)

## 🔗 Referencias

- **docker-compose.yml:** Configuración de servicios
- **.env.example:** Plantilla de variables de entorno
- **CLAUDE.md:** Documentación completa del proyecto
