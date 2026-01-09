"""
Application Settings

Configuración centralizada de la aplicación usando variables de entorno.
"""

import os

from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()


class Settings:
    """
    Configuración de la aplicación.

    Todas las configuraciones se cargan desde variables de entorno
    con valores por defecto razonables para desarrollo.
    """

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    # Session Timeout (v1.8.0)
    # Access Token: Corto (15 min) para operaciones frecuentes
    # Refresh Token: Largo (7 días) para renovación sin re-login
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )  # Reducido de 60 a 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Swagger/Docs HTTP Basic Auth (sin defaults - DEBE estar en .env)
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD")

    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ryderclub"
    )

    # Mailgun Configuration
    MAILGUN_API_KEY: str = os.getenv("MAILGUN_API_KEY", "")
    MAILGUN_DOMAIN: str = os.getenv("MAILGUN_DOMAIN", "rydercupfriends.com")
    MAILGUN_FROM_EMAIL: str = os.getenv(
        "MAILGUN_FROM_EMAIL", "Ryder Cup Friends <noreply@rydercupfriends.com>"
    )
    MAILGUN_API_URL: str = os.getenv("MAILGUN_API_URL", "https://api.eu.mailgun.net/v3")
    # Frontend URL - Cambia según el entorno:
    # - Local (directo): http://localhost:5173 (Vite default)
    # - Local (K8s): http://localhost:8080 (port-forward)
    # - Producción: https://rydercupfriends.com (Render.com)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Sentry Configuration (v1.8.0 - Task 10)
    # Error tracking y performance monitoring
    # Configuración:
    # - SENTRY_DSN: URL de proyecto Sentry (obligatorio para habilitar Sentry)
    # - SENTRY_ENVIRONMENT: Entorno actual (development, staging, production)
    # - SENTRY_TRACES_SAMPLE_RATE: % de transacciones a capturar (0.0-1.0)
    # - SENTRY_PROFILES_SAMPLE_RATE: % de perfiles a capturar (0.0-1.0)
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SENTRY_TRACES_SAMPLE_RATE: float = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    SENTRY_PROFILES_SAMPLE_RATE: float = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))


settings = Settings()
