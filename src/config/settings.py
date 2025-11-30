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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # Swagger/Docs HTTP Basic Auth (sin defaults - DEBE estar en .env)
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD")

    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ryderclub"
    )

    # Mailgun Configuration
    MAILGUN_API_KEY: str = os.getenv("MAILGUN_API_KEY", "")
    MAILGUN_DOMAIN: str = os.getenv("MAILGUN_DOMAIN", "rydercupfriends.com")
    MAILGUN_FROM_EMAIL: str = os.getenv("MAILGUN_FROM_EMAIL", "Ryder Cup Friends <noreply@rydercupfriends.com>")
    MAILGUN_API_URL: str = os.getenv("MAILGUN_API_URL", "https://api.eu.mailgun.net/v3")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")


settings = Settings()
