# Ryder Cup Manager

Aplicación para crear y gestionar competiciones tipo Ryder Cup entre amigos.

## 🎯 Visión del Proyecto

Una plataforma que permite a grupos de amigos organizar torneos de golf al estilo Ryder Cup, con equipos, emparejamientos, diferentes formatos de juego y seguimiento de puntuaciones.

## 🏗️ Arquitectura

**Monolito Modular con Clean Architecture**

### Principios Arquitectónicos

- **Independencia de Frameworks**: La lógica de negocio no depende de frameworks específicos
- **Testeable**: La lógica de negocio puede testearse sin UI, BD, o servicios externos
- **Independencia de UI**: La UI puede cambiar sin modificar la lógica de negocio
- **Independencia de Base de Datos**: Podemos cambiar la BD sin afectar las reglas de negocio
- **Independencia de Agentes Externos**: La lógica de negocio no conoce el mundo exterior

### Capas de la Arquitectura

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│    (Schemas, Validators, Mappers)       │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│        Application Layer                │
│  (Use Cases, Application Services)      │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│           Domain Layer                  │
│   (Entities, Value Objects, Rules)      │
└─────────────────────────────────────────┘
                  ↑
┌─────────────────────────────────────────┐
│       Infrastructure Layer              │
│  (DB, External APIs, Implementations)   │
└─────────────────────────────────────────┘
```

## 📦 Módulos del Sistema

### Módulo: User Management
Gestión de usuarios, autenticación y autorización.

**Casos de Uso Fase 1:**
- ✅ Registro de usuario
- ✅ Login de usuario

### Módulo: Competition Management (Futuro)
Creación y gestión de competiciones.

### Módulo: Team Management (Futuro)
Gestión de equipos y jugadores.

### Módulo: Match Management (Futuro)
Gestión de partidos y formatos de juego.

### Módulo: Scoring (Futuro)
Sistema de puntuación y resultados.

## 🚀 Roadmap

### Fase 1: Fundamentos ✨ (Actual)
- [x] Estructura del proyecto
- [x] Módulo de usuarios
- [ ] Caso de uso: Registro de usuario
- [ ] Caso de uso: Login de usuario

### Fase 2: Gestión de Competiciones
- [ ] Crear competición
- [ ] Configurar formato
- [ ] Invitar participantes

### Fase 3: Gestión de Equipos
- [ ] Crear equipos
- [ ] Asignar jugadores
- [ ] Capitanes de equipo

### Fase 4: Gestión de Partidos
- [ ] Crear emparejamientos
- [ ] Formatos de juego (Foursome, Fourball, Singles)
- [ ] Calendario de partidos

### Fase 5: Sistema de Puntuación
- [ ] Registro de resultados
- [ ] Cálculo de puntos
- [ ] Clasificación en tiempo real

## 🛠️ Stack Tecnológico

- **Backend**: Python 3.11+ con FastAPI
- **ORM**: SQLAlchemy 2.0
- **Base de Datos**: PostgreSQL
- **Migraciones**: Alembic
- **Autenticación**: JWT (python-jose)
- **Hashing**: bcrypt (passlib)
- **Validación**: Pydantic v2
- **Testing**: pytest + pytest-asyncio
- **Linting**: ruff + black
- **Type Checking**: mypy

## 📋 Requisitos

- Python 3.11 o superior
- PostgreSQL 14 o superior
- pip o poetry para gestión de dependencias

## 🚀 Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd ryder-cup-manager
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Para desarrollo
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 5. Configurar base de datos

```bash
# Crear base de datos
createdb ryder_cup_manager

# Ejecutar migraciones
alembic upgrade head
```

### 6. Ejecutar la aplicación

```bash
uvicorn src.main:app --reload
```

La API estará disponible en `http://localhost:8000`
Documentación interactiva en `http://localhost:8000/docs`

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Tests con cobertura
pytest --cov=src --cov-report=html

# Tests específicos
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

## 🔍 Linting y Formateo

```bash
# Formatear código
black src tests

# Linting
ruff check src tests

# Type checking
mypy src
```

## 📝 Convenciones de Código

- **Estilo**: PEP 8
- **Nombres de clases**: PascalCase
- **Nombres de funciones/variables**: snake_case
- **Nombres de constantes**: UPPER_SNAKE_CASE
- **Idioma del código**: Inglés
- **Idioma de documentación**: Español
- **Line length**: 100 caracteres

## 🗂️ Estructura del Proyecto

```
src/
├── modules/          # Módulos de negocio
│   └── user/        # Módulo de usuarios
│       ├── domain/          # Lógica de negocio
│       ├── application/     # Casos de uso
│       ├── infrastructure/  # Implementaciones
│       └── presentation/    # Schemas y mappers
├── shared/          # Código compartido
├── config/          # Configuración
└── main.py          # Punto de entrada
```

## 📚 Documentación Adicional

- [Estructura del Proyecto](docs/project-structure.md)
- [Módulo User Management](docs/modules/user-management.md)
- [Guía de Contribución](docs/contributing.md)

## 🔐 Variables de Entorno

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ryder_cup_manager

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Application
DEBUG=True
ENVIRONMENT=development
```

## 📊 API Endpoints

### Autenticación

- `POST /api/users/register` - Registro de usuario
- `POST /api/users/login` - Login de usuario

Documentación completa en `/docs` (Swagger UI)

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de uso privado.

## 👥 Autores

Tu equipo de desarrollo