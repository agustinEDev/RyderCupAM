"""Version de la aplicacion — fuente unica de verdad.

A diferencia del frontend, el backend no tiene `package.json`, asi que la
version vive aqui. Debe subirse en el commit de preparacion de cada release
(`CHORE(RELEASE): PREPARE VX.Y.Z`), junto al CHANGELOG.

`GET /health` la expone junto al commit desplegado para poder verificar que
una release ha llegado realmente a produccion.
"""

import os

APP_VERSION = "2.10.0"


def get_deployed_commit() -> str:
    """SHA del commit desplegado.

    Render inyecta `RENDER_GIT_COMMIT` automaticamente en cada deploy, asi que
    identifica el despliegue sin necesidad de mantener nada a mano. Fuera de
    Render (local, Docker, k8s) no existe y devolvemos "unknown".
    """
    return os.getenv("RENDER_GIT_COMMIT", "unknown")


def get_deployed_branch() -> str:
    """Rama desde la que se desplego, inyectada por Render igual que el commit."""
    return os.getenv("RENDER_GIT_BRANCH", "unknown")


def get_environment() -> str:
    """Entorno de ejecucion (development, staging, production)."""
    return os.getenv("ENVIRONMENT", "development")
