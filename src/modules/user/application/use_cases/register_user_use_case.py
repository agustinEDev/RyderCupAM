import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from src.modules.user.application.dto.user_dto import (
    RegisterUserRequestDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.correo_en_segundo_plano_port import (
    ICorreoEnSegundoPlano,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.handicap_errors import HandicapServiceError
from src.modules.user.domain.errors.user_errors import (
    EmailTakenConcurrentlyError,
    TermsAcceptanceRequiredError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.terms_of_service import current_terms_version
from src.shared.application.concurrencia.bcrypt_executor import run_bcrypt
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

logger = logging.getLogger(__name__)


class RegisterUserUseCase:
    """
    Caso de uso para registrar un nuevo usuario en el sistema.
    Orquesta la creación, validación y persistencia de un usuario.

    Opcionalmente, puede buscar el hándicap inicial del usuario
    si se proporciona un HandicapService.

    No dice si el correo ya tiene cuenta (fase 3, F-01): con un correo ocupado responde
    lo mismo que con uno nuevo, con el mismo trabajo (el bcrypt y la RFEG), y la cuenta
    que ya existe no se toca.
    - Correo nuevo (B1): alta y correo de verificación.
    - Cuenta activa, verificada (B2) o no (B3): aviso al buzón del correo, como mucho uno
      al día. Sin verificar no se reenvía el enlace de verificación: verificaría una
      cuenta con la contraseña de quien la creó; el aviso lleva a «Olvidé mi contraseña»,
      que se la queda (ADR-045).
    - Cuenta desactivada: nada más.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        country_repository: CountryRepositoryInterface,
        handicap_service: HandicapService | None = None,
        email_service: IEmailService | None = None,
        *,
        security_audit: ISecurityAuditLogger,
        correo_en_segundo_plano: ICorreoEnSegundoPlano | None = None,
    ):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        self._country_repository = country_repository
        self._handicap_service = handicap_service
        self._email_service = email_service
        self._security_audit = security_audit
        # Sin él (tests de antes), los correos se esperan aquí mismo
        self._correo_en_segundo_plano = correo_en_segundo_plano

    async def _comprueba_lo_barato(self, request: RegisterUserRequestDTO) -> Email:
        """El país, en su propia transacción ya cerrada al volver (BE #283). El correo
        ocupado ya no corta aquí: se gasta el mismo bcrypt que con uno libre (fase 3)."""
        async with self._uow:
            email_vo = Email(request.email)
            if request.country_code:
                country_code_vo = CountryCode(request.country_code)
                if not await self._country_repository.exists(country_code_vo):
                    raise ValueError(f"El código de país '{request.country_code}' no es válido.")
        return email_vo

    async def execute(self, request: RegisterUserRequestDTO) -> UserResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: DTO con la información para el registro.

        Returns:
            DTO con la información del usuario recién creado. Con el correo ocupado, el
            mismo DTO con los datos enviados y un id que no se guarda: la misma forma y
            los mismos datos que un alta nueva.

        Raises:
            TermsAcceptanceRequiredError: Si no trae accept_terms exactamente True.
        """
        # Sin consentimiento explícito no hay alta. La API ya da 422, pero el
        # caso de uso no se fía de que el request llegue validado (p. ej. uno
        # construido con model_construct): solo vale el booleano True
        if getattr(request, "accept_terms", None) is not True:
            raise TermsAcceptanceRequiredError(
                "Para registrarse hay que aceptar los Términos de uso vigentes."
            )

        # Fase 1, lo barato y en su propia transacción (BE #283)
        email_vo = await self._comprueba_lo_barato(request)

        # Fase 2, sin transacción: el bcrypt y la búsqueda del hándicap en la RFEG (red)
        # no retienen una conexión del pool (BE #283)
        # 2. Crear la entidad de dominio User
        gender = Gender(request.gender) if request.gender else None
        new_user = await run_bcrypt(
            User.create,
            email_str=request.email,
            plain_password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            country_code_str=request.country_code,
            gender=gender,
        )

        # 2.1 Los Términos: se guarda la versión vigente con la fecha de
        # ahora, y la aceptación va al historial con la IP y el navegador
        terms_version = current_terms_version()
        new_user.accept_terms(terms_version)
        accepted_at = new_user.terms_accepted_at
        if accepted_at is None:  # accept_terms acaba de ponerla
            raise RuntimeError("accept_terms no dejó fecha de aceptación")
        terms_acceptance = TermsAcceptance.record(
            user_id=new_user.id,
            user_email=new_user.email.value,
            terms_version=terms_version,
            accepted_at=accepted_at,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
        )

        # 2.5 Intentar buscar hándicap inicial (solo para usuarios españoles)
        handicap_value = None
        if self._handicap_service and new_user.country_code and new_user.country_code.value == "ES":
            try:
                handicap_value = await self._handicap_service.search_handicap(
                    new_user.get_full_name()
                )
            except HandicapServiceError as e:
                # No falla el registro si no se encuentra el hándicap
                logger.warning(
                    "No se pudo obtener hándicap inicial para %s: %s",
                    new_user.get_full_name(),
                    e,
                )

        # 2.6 Si no se encontró en RFEG, usar hándicap manual si fue proporcionado
        if handicap_value is None and request.manual_handicap is not None:
            handicap_value = request.manual_handicap

        # 2.7 Actualizar hándicap si se obtuvo uno (de RFEG o manual)
        if handicap_value is not None:
            new_user.update_handicap(handicap_value)

        # 2.8 Generar token de verificación de email
        verification_token = new_user.generate_verification_token()

        # Fase 3, en otra transacción: el correo, otra vez (alguien pudo registrarlo
        # entretanto), y se guarda solo si sigue libre
        try:
            guardado, avisa_a = await self._guarda_o_mira_el_ocupado(
                email_vo, new_user, terms_acceptance
            )
        except EmailTakenConcurrentlyError:
            # Dos altas a la vez: las dos lo vieron libre y la base de datos paró a esta.
            # Lo mismo que si hubiera llegado después, aviso incluido. Otro error sube
            logger.info("Sign-up with an email already registered (concurrent)")
            async with self._uow:
                guardado, avisa_a = False, await self._reserva_el_aviso(email_vo)

        if not guardado:
            # Correo ocupado: ni alta ni verificación. Al buzón, su aviso si toca (B2/B3)
            if avisa_a is not None and self._email_service is not None:
                dueno_email, dueno_nombre = avisa_a
                email_service = self._email_service
                await self._envia(
                    "aviso-de-intento-de-registro",
                    lambda: email_service.send_register_attempt_notice(
                        to_email=dueno_email, user_name=dueno_nombre
                    ),
                )
            logger.info("Sign-up with an email already registered")
            return UserResponseDTO.model_validate(new_user)

        # 3.5 Auditoría de seguridad: la aceptación de los Términos
        registra_sin_romper(
            "Register user",
            lambda: self._security_audit.log_terms_accepted(
                user_id=str(new_user.id.value),
                ip_address=request.ip_address or "unknown",
                user_agent=request.user_agent or "unknown",
                terms_version=terms_acceptance.terms_version,
            ),
        )

        # 4. Enviar email de verificación (en segundo plano: la respuesta no lo espera,
        # como el aviso de un correo ocupado)
        if self._email_service:
            email_service = self._email_service
            nuevo_id = new_user.id.value
            nombre = new_user.first_name

            async def verificacion() -> bool:
                enviado = await email_service.send_verification_email(
                    to_email=request.email,
                    user_name=nombre,
                    verification_token=verification_token,
                )
                if not enviado:
                    logger.warning(
                        "No se pudo enviar el email de verificación para el usuario %s",
                        nuevo_id,
                    )
                return enviado

            await self._envia("verificacion-del-registro", verificacion)

        # 5. Devolver la respuesta como DTO
        return UserResponseDTO.model_validate(new_user)

    async def _guarda_o_mira_el_ocupado(
        self, email_vo: Email, new_user: User, terms_acceptance: TermsAcceptance
    ) -> tuple[bool, tuple[str, str] | None]:
        """
        Guarda el alta si el correo sigue libre. Si no, no toca la cuenta que lo tiene
        salvo para apuntar su aviso (B2), con la fila bloqueada.

        Returns:
            (guardado, aviso): si se guardó el alta, y el (correo, nombre) del dueño si
            toca avisarle (None si no: desactivada, o ya avisada en las 24 h)
        """
        async with self._uow:
            ocupado = await self._user_finder.by_email(email_vo)
            if ocupado is None:
                # 3. Guardar el usuario en el repositorio, y después su aceptación
                # (la fila apunta al usuario: tiene que existir antes)
                await self._uow.users.save(new_user)
                await self._uow.flush()
                await self._uow.terms_acceptances.save(terms_acceptance)
                # El context manager (__aexit__) hace commit automático
                return True, None
            return False, await self._reserva_el_aviso(email_vo)

    async def _reserva_el_aviso(self, email_vo: Email) -> tuple[str, str] | None:
        """
        Con el correo ocupado, reserva el aviso a su buzón (B2/B3) con la fila bloqueada,
        dentro de la transacción en curso. Verificada o no (decidido por Agustín); a una
        desactivada, no: no puede iniciar sesión.

        Returns:
            (correo, nombre) del dueño si toca avisarle; None si no (desactivada, ya
            avisada en las 24 h, o sin servicio de correo)
        """
        ocupado = await self._user_finder.by_email(email_vo)
        if ocupado is None or not ocupado.is_active or self._email_service is None:
            return None
        dueno = await self._uow.users.find_by_id_for_update(ocupado.id)
        if dueno is None or not dueno.reserva_el_aviso_de_registro(datetime.now()):
            return None
        await self._uow.users.save(dueno)
        return str(dueno.email.value), dueno.first_name

    async def _envia(self, nombre: str, envio: Callable[[], Awaitable[object]]) -> None:
        """Lanza un correo sin que la respuesta lo espere; sin el lanzador, lo espera aquí
        (tests de antes). Un fallo del envío nunca rompe el registro."""

        async def sin_romper() -> None:
            try:
                await envio()
            except Exception as e:
                # Solo el tipo: el mensaje puede llevar la dirección (OWASP A09)
                logger.error("Sign-up email %s failed: %s", nombre, type(e).__name__)

        if self._correo_en_segundo_plano is not None:
            self._correo_en_segundo_plano.lanza(nombre, sin_romper)
            return
        await sin_romper()
