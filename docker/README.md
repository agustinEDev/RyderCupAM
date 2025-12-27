# Docker Configuration - Ryder Cup AM

Este directorio contiene toda la configuración relacionada con Docker para el proyecto Ryder Cup Amateur Manager.

## 📂 Estructura

```plaintext
docker/
├── Dockerfile              # Imagen de la aplicación FastAPI
├── docker-compose.yml      # Orquestación de servicios (app + PostgreSQL)
├── .dockerignore          # Archivos excluidos del build
├── scripts/               # Scripts de validación y utilidades
│   ├── validate-postgres-env.sh   # Validación de variables PostgreSQL
│   ├── validate-app-env.sh        # Validación de variables de la app
│   ├── test-validation.sh         # Tests automatizados
│   └── README.md                  # Documentación de scripts
└── README.md              # Este archivo
```

## 🚀 Uso Rápido

### Iniciar servicios

```bash
# Desde el directorio docker/
cd docker/
docker-compose up -d

# O desde la raíz del proyecto
docker-compose -f docker/docker-compose.yml up -d
```

### Ver logs

```bash
cd docker/
docker-compose logs -f app
```

### Detener servicios

```bash
cd docker/
docker-compose down
```

### Rebuild y restart

```bash
cd docker/
docker-compose down && docker-compose up -d --build
```

## 🐳 Servicios

### 1. PostgreSQL (`db`)
- **Imagen:** `postgres:15-alpine`
- **Puerto:** `5432` (interno), configurable externamente con `DATABASE_PORT`
- **Volumen persistente:** `postgres_data`
- **Health check:** Verifica que PostgreSQL está listo antes de iniciar la app

### 2. FastAPI Application (`app`)
- **Build:** `docker/Dockerfile`
- **Puerto:** `8000` (configurable con `PORT`)
- **Hot reload:** Habilitado con `--reload`
- **Dependencias:** Espera a que PostgreSQL esté healthy

## ⚡ Fail-Fast Validation

Los servicios incluyen validación automática de variables de entorno **antes de iniciar**:

### PostgreSQL
- Valida: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Si falta alguna: **fallo instantáneo con mensaje claro**

### Application
- **Requeridas:** `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `SECRET_KEY`
- **Opcionales:** `MAILGUN_API_KEY`, `DOCS_USERNAME`, `DOCS_PASSWORD`
- Si faltan variables críticas: **fallo instantáneo**

Ver `scripts/README.md` para detalles completos sobre la validación.

## 📝 Variables de Entorno

Crea un archivo `.env` en la **raíz del proyecto** (no en `docker/`) con:

```bash
# Database Configuration (REQUIRED)
POSTGRES_USER=rydercupam_adminuser
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=rydercupam_db
DATABASE_PORT=5432

# Security Configuration (REQUIRED)
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Application
PORT=8000
ENVIRONMENT=development

# Swagger/Docs Protection
DOCS_USERNAME=admin
DOCS_PASSWORD=secure_password

# Mailgun (Email Verification)
MAILGUN_API_KEY=your_api_key
MAILGUN_DOMAIN=your_domain.com
MAILGUN_FROM_EMAIL=noreply@your_domain.com
MAILGUN_API_URL=https://api.eu.mailgun.net/v3

# Frontend URL
FRONTEND_URL=http://localhost:5173
```

💡 **Tip:** Copia `.env.example` a `.env` y edita los valores.

## 🛠️ Comandos Útiles

### Acceder al contenedor de la aplicación

```bash
docker exec -it docker-app-1 bash
```

### Acceder a PostgreSQL

```bash
docker exec -it docker-db-1 psql -U rydercupam_adminuser -d rydercupam_db
```

### Ejecutar migraciones Alembic

```bash
docker exec docker-app-1 alembic upgrade head
```

### Ver estado de los contenedores

```bash
docker ps | grep docker-
```

### Ver uso de recursos

```bash
docker stats docker-app-1 docker-db-1
```

### Limpiar volúmenes (¡CUIDADO! Borra datos)

```bash
cd docker/
docker-compose down -v
```

## 🔧 Build Personalizado

### Build solo la imagen de la app

```bash
# Desde la raíz del proyecto
docker build -f docker/Dockerfile -t rydercupam-app:latest .
```

### Build con caché disabled

```bash
cd docker/
docker-compose build --no-cache
```

## 🐛 Troubleshooting

### Error: "No se encontró Dockerfile"
- Verifica que estás ejecutando desde `docker/`
- O usa `-f docker/docker-compose.yml`

### Error: "port is already allocated"
- Cambia el puerto en `.env`: `DATABASE_PORT=5433` o `PORT=8001`
- O detén el servicio que está usando el puerto

### Error: "connection to server failed"
- Verifica que PostgreSQL está healthy: `docker ps`
- Revisa logs: `docker logs docker-db-1`
- Verifica variables `.env`

### Error: variables de entorno faltantes
- Revisa el mensaje de error (indica exactamente qué falta)
- Verifica que `.env` existe en la raíz del proyecto
- Verifica que las variables están configuradas correctamente

## 🔗 Referencias

- **Dockerfile:** Configuración de la imagen FastAPI
- **docker-compose.yml:** Orquestación de servicios
- **scripts/README.md:** Documentación de scripts de validación
- **../CLAUDE.md:** Documentación completa del proyecto
