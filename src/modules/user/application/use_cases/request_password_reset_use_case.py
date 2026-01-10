"""
Request Password Reset Use Case

Caso de uso para solicitar el reseteo de contraseña (flujo "Olvidé mi contraseña").
Este endpoint es público y NO requiere autenticación.

Security Features:
- Timing attack prevention: Siempre retorna 200 OK con mensaje genérico
- Rate limiting: 3 intentos/hora por email (configurado en SlowAPI)
- Email injection prevention: Validación con Pydantic EmailStr
- Security logging: Registra todas las solicitudes (exitosas y fallidas)
"""

import asyncio

from src.config.settings import Settings
from src.modules.user.application.dto.user_dto import (
    RequestPasswordResetRequestDTO,
    RequestPasswordResetResponseDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.shared.infrastructure.logging.security_logger import get_security_logger


class RequestPasswordResetUseCase:
    """
    Caso de uso para solicitar el reseteo de contraseña.

    Responsabilidades:
    - Buscar usuario por email (sin revelar si existe)
    - Generar token de reseteo con expiración 24h
    - Enviar email con enlace de reseteo
    - Registrar evento de dominio para auditoría
    - Aplicar timing attack prevention

    Security (OWASP A01, A07):
    - Usuario no autenticado (endpoint público)
    - Mensaje genérico para prevenir enumeración de usuarios
    - Delay artificial si el email NO existe (evita timing attacks)
    - Token de 256 bits criptográficamente seguro
    - Expiración automática en 24 horas
    """

    # Delay en segundos para simular envío de email si el usuario no existe
    # Previene timing attacks que podrían revelar si el email existe
    FAKE_EMAIL_DELAY_SECONDS = 0.5

    def __init__(self, uow: UserUnitOfWorkInterface, email_service: IEmailService):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorio de usuarios
            email_service: Servicio para envío de emails (Mailgun)
        """
        self._uow = uow
        self._email_service = email_service

    async def execute(
        self, request: RequestPasswordResetRequestDTO
    ) -> RequestPasswordResetResponseDTO:
        """
        Ejecuta el caso de uso de solicitud de reseteo de contraseña.

        Args:
            request: DTO con email y contexto de seguridad (IP, User-Agent)

        Returns:
            RequestPasswordResetResponseDTO con mensaje genérico
            SIEMPRE retorna 200 OK, sin importar si el email existe

        Security Flow:
            1. Busca usuario por email
            2. Si NO existe → Delay artificial + mensaje genérico + log + return
            3. Si existe → Genera token + envía email + guarda + log + return
            4. Ambos casos retornan el MISMO mensaje (previene enumeración)

        Example:
            >>> request = RequestPasswordResetRequestDTO(
            ...     email="user@example.com",
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request)
            >>> print(response.message)
            "Si el email existe en nuestro sistema, recibirás un enlace..."
        """
        # Obtener security logger
        security_logger = get_security_logger()

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        # Buscar usuario por email
        email_vo = Email(request.email)
        user = await self._uow.users.find_by_email(email_vo)

        # CASO 1: Email NO existe en el sistema
        if not user:
            # Delay artificial para prevenir timing attacks
            # (simula tiempo de envío de email)
            await asyncio.sleep(self.FAKE_EMAIL_DELAY_SECONDS)

            # Security Logging: Solicitud fallida (email no existe)
            security_logger.log_password_reset_requested(
                user_id=None,
                email=request.email,
                success=False,
                failure_reason="Email not found (not revealed to client)",
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Retornar mensaje genérico (NO revelar que el email no existe)
            return RequestPasswordResetResponseDTO(
                message="Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña.",
                email=request.email,
            )

        # CASO 2: Email existe → Generar token y enviar email
        # Generar token de reseteo (expiración 24h)
        token = user.generate_password_reset_token(
            ip_address=ip_address, user_agent=user_agent
        )

        # Guardar usuario con token de reseteo
        async with self._uow:
            await self._uow.users.save(user)
            # Commit automático al salir del contexto

        # Enviar email con enlace de reseteo (Mailgun)
        reset_link = self._build_reset_link(token)
        await self._email_service.send_password_reset_email(
            to_email=request.email,
            reset_link=reset_link,
            user_name=user.get_full_name(),
        )

        # Security Logging: Solicitud exitosa
        security_logger.log_password_reset_requested(
            user_id=str(user.id.value),
            email=request.email,
            success=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Retornar el MISMO mensaje genérico (previene enumeración)
        return RequestPasswordResetResponseDTO(
            message="Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña.",
            email=request.email,
        )

    def _build_reset_link(self, token: str) -> str:
        """
        Construye el enlace de reseteo para incluir en el email.

        El enlace apunta al frontend, que mostrará el formulario de nueva contraseña.

        Args:
            token: Token de reseteo generado

        Returns:
            URL completa: {FRONTEND_URL}/reset-password/{token}

        Example:
            >>> link = self._build_reset_link("abc123...")
            >>> print(link)
            "http://localhost:5173/reset-password/abc123..."
        """
        settings = Settings()
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        return f"{frontend_url}/reset-password/{token}"
