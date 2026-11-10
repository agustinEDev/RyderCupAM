"""
Rotación del refresh token con detección de robo (F-02 de la auditoría).

Tabla aprobada por Agustín (la de caminos completa, en el informe):
  A1 refresco normal: access nuevo Y refresh nuevo; el viejo queda sustituido (no se
     borra); el nuevo conserva la caducidad absoluta y el dispositivo
  A2 el sustituido llega dentro de 60 s desde su sustitución: access nuevo, SIN otro
     refresh y sin robo (dos pestañas a la vez)
  A3 el sustituido llega fuera del margen y su sustituto NUNCA se usó (respuesta
     perdida): se vuelve a rotar desde el viejo y se anula el sustituto
  A4 robo: sustituido fuera del margen con el sustituto ya usado → se revocan TODOS
     los tokens del dispositivo, SESSION_REJECTED, evento HIGH y correo al usuario (que
     no bloquea ni rompe la respuesta)
  A5 cookie vieja con el navegador ya en una sesión más nueva → SESSION_REPLACED, como
     hoy; el robo gana a A5; A5 gana a A2/A3 (no se emite nada de la sesión vieja)
  A7 un token de antes (sin datos de rotación) es vigente y se rota en su primer uso
"""

from datetime import datetime, timedelta
from itertools import count
from unittest.mock import AsyncMock, Mock

import pytest

from src.modules.user.application.dto.device_dto import AvisoDeSesionCerradaRequestDTO
from src.modules.user.application.dto.user_dto import RefreshAccessTokenRequestDTO
from src.modules.user.application.ports.aviso_de_sesion_cerrada_port import (
    IAvisoDeSesionCerrada,
)
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    SESSION_REJECTED,
    RefreshAccessTokenUseCase,
    RefreshRejectedError,
    RefreshRejection,
    codigo_publico,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) Version/18.1 Safari/604.1"
ORIGINAL = "refresco-del-login"


class _Escena:
    """Un usuario con su dispositivo y el token de su login, y el caso de uso."""

    async def monta(self, verificado: bool = True) -> "_Escena":
        self.uow = InMemoryUnitOfWork()
        self.usuario = User.create(
            first_name="Ana",
            last_name="Pérez",
            email_str="ana@example.com",
            plain_password="SecureP@ssw0rd123!",
        )
        if verificado:
            self.usuario._email_verified = True
        await self.uow.users.save(self.usuario)
        self.dispositivo = UserDevice.create(
            self.usuario.id, DeviceFingerprint.create(IPHONE, "203.0.113.7")
        )
        await self.uow.user_devices.save(self.dispositivo)
        self.original = RefreshToken.create(
            user_id=self.usuario.id, token=ORIGINAL, device_id=self.dispositivo.id
        )
        # El login fue hace una hora
        self.original._created_at = datetime.now() - timedelta(hours=1)
        await self.uow.refresh_tokens.save(self.original)
        numeros = count(1)
        self.tokens = Mock()
        self.tokens.verify_refresh_token.return_value = {
            "sub": str(self.usuario.id.value),
            "type": "refresh",
        }
        self.tokens.refresh_token_expired.return_value = False
        self.tokens.create_access_token.return_value = "acceso"
        self.tokens.create_csrf_token.return_value = "csrf"
        self.tokens.create_refresh_token.side_effect = lambda **_: f"refresco-{next(numeros)}"
        self.auditoria = Mock(spec=ISecurityAuditLogger)
        self.aviso = AsyncMock(spec=IAvisoDeSesionCerrada)
        self.caso = RefreshAccessTokenUseCase(
            self.uow, self.tokens, security_audit=self.auditoria, aviso_de_cierre=self.aviso
        )
        return self

    async def refresca(self, jwt: str, navegador: tuple[str, ...] = ()):
        return await self.caso.execute(
            RefreshAccessTokenRequestDTO(
                user_agent=IPHONE, dispositivos_del_navegador=list(navegador)
            ),
            jwt,
        )

    async def rechazo(self, jwt: str, navegador: tuple[str, ...] = ()) -> RefreshRejectedError:
        with pytest.raises(RefreshRejectedError) as error:
            await self.refresca(jwt, navegador)
        return error.value

    async def token(self, jwt: str) -> RefreshToken:
        encontrado = await self.uow.refresh_tokens.find_by_token_hash(jwt)
        assert encontrado is not None
        return encontrado

    async def del_dispositivo(self, dispositivo=None) -> list[RefreshToken]:
        dispositivo = dispositivo or self.dispositivo
        return [
            t
            for t in await self.uow.refresh_tokens.find_all_by_user(self.usuario.id)
            if t.device_id == dispositivo.id
        ]

    async def vivos(self, dispositivo=None) -> list[RefreshToken]:
        return [
            t
            for t in await self.del_dispositivo(dispositivo)
            if not t.revoked and not t.is_replaced and not t.is_expired()
        ]

    async def hace(self, jwt: str, tiempo: timedelta) -> None:
        """Mueve atrás la sustitución del token: ya pasó `tiempo` desde ella."""
        token = await self.token(jwt)
        assert token.replaced_at is not None
        token._replaced_at = datetime.now() - tiempo

    async def otra_sesion_nueva(self, dispositivo=None) -> RefreshToken:
        """Un login más nuevo y vivo (hace 10 s) en ese dispositivo."""
        nueva = RefreshToken.create(
            user_id=self.usuario.id,
            token=f"otro-login-{datetime.now().timestamp()}",
            device_id=(dispositivo or self.dispositivo).id,
        )
        nueva._created_at = datetime.now() - timedelta(seconds=10)
        await self.uow.refresh_tokens.save(nueva)
        return nueva


async def _escena(**kwargs) -> _Escena:
    escena = _Escena()
    return await escena.monta(**kwargs)


# ---------------------------------------------------------------------------- A1


async def test_a1_a_normal_refresh_issues_a_new_access_and_a_new_refresh():
    """
    Given: El token del login, vigente
    When: Refresca
    Then: Access nuevo y refresh nuevo; el viejo queda sustituido por él (no borrado ni
          revocado) y el nuevo es el único vivo del dispositivo
    """
    e = await _escena()

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.access_token == "acceso"
    assert respuesta.refresh_token == "refresco-1"
    viejo, nuevo = await e.token(ORIGINAL), await e.token("refresco-1")
    assert viejo.is_replaced and not viejo.revoked
    assert viejo.replaced_by_id == nuevo.id
    assert await e.vivos() == [nuevo]


async def test_a1_the_new_one_keeps_the_absolute_expiry_and_the_device():
    """
    Given: Un token al que le quedan 2 días de sus 7 desde el login
    When: Refresca
    Then: El nuevo caduca a la vez que el viejo (no se alarga), en el JWT y en la BD,
          es del mismo dispositivo, y la cookie dura lo que le queda
    """
    e = await _escena()
    e.original._expires_at = datetime.now() + timedelta(days=2)

    respuesta = await e.refresca(ORIGINAL)

    nuevo = await e.token("refresco-1")
    assert nuevo.expires_at == e.original.expires_at
    assert nuevo.device_id == e.dispositivo.id
    assert nuevo.created_at == e.original.created_at
    pedido = e.tokens.create_refresh_token.call_args.kwargs
    assert pedido["data"] == {"sub": str(e.usuario.id.value)}
    assert timedelta(days=2) - timedelta(seconds=5) < pedido["expires_delta"] <= timedelta(days=2)
    dos_dias = 2 * 24 * 3600
    assert respuesta.refresh_token_max_age is not None
    assert dos_dias - 5 <= respuesta.refresh_token_max_age <= dos_dias


async def test_a1_the_new_refresh_is_never_in_the_response_body():
    """
    Given: Un refresco normal
    Then: El refresh nuevo va solo a la cookie: no sale en el JSON de la respuesta
    """
    e = await _escena()

    respuesta = await e.refresca(ORIGINAL)

    cuerpo = respuesta.model_dump()
    assert "refresh_token" not in cuerpo
    assert "refresh_token_max_age" not in cuerpo


async def test_a1_the_new_one_rotates_in_turn():
    """
    Given: Un refresco hecho
    When: Refresca con el nuevo
    Then: Rota otra vez: la cadena sigue, siempre un solo vivo
    """
    e = await _escena()
    await e.refresca(ORIGINAL)

    respuesta = await e.refresca("refresco-1")

    assert respuesta.refresh_token == "refresco-2"
    assert (await e.token("refresco-1")).is_replaced
    assert [t.token_hash for t in await e.vivos()] == [(await e.token("refresco-2")).token_hash]


async def test_a1_a_current_token_rotates_even_with_a_newer_session_in_the_browser():
    """
    Given: El token vigente y, en el navegador, otro login más nuevo
    When: Refresca con el vigente
    Then: Se acepta y rota, como hoy se aceptaba (la cookie vigente no es «vieja»)
    """
    e = await _escena()
    await e.otra_sesion_nueva()

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.refresh_token == "refresco-1"


# ---------------------------------------------------------------------------- A2


@pytest.mark.parametrize("sustituto_usado", [False, True])
async def test_a2_within_the_margin_access_without_a_new_refresh(sustituto_usado):
    """
    Given: El token sustituido hace 10 s (otra pestaña refrescó con la misma cookie),
           con su sustituto usado o no
    When: Llega el refresco con la cookie vieja
    Then: Access nuevo, SIN refresh nuevo, sin anular nada ni tratarlo como robo
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    if sustituto_usado:
        await e.refresca("refresco-1")
    await e.hace(ORIGINAL, timedelta(seconds=10))
    antes = len(await e.del_dispositivo())

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.access_token == "acceso"
    assert respuesta.refresh_token is None
    assert respuesta.refresh_token_max_age is None
    assert len(await e.del_dispositivo()) == antes
    assert not any(t.revoked for t in await e.del_dispositivo())
    e.auditoria.log_refresh_token_reuse_detected.assert_not_called()
    e.aviso.avisa.assert_not_awaited()


async def test_a2_the_margin_ends_at_sixty_seconds():
    """
    Given: El sustituido hace 59 s con el sustituto usado
    Then: Aún es el margen (A2), no un robo
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.refresca("refresco-1")
    await e.hace(ORIGINAL, timedelta(seconds=59))

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.refresh_token is None


# ---------------------------------------------------------------------------- A3


async def test_a3_a_lost_response_rotates_again_from_the_old_one():
    """
    Given: El token sustituido hace 2 min y su sustituto nunca se usó (la respuesta con la
           cookie nueva se perdió)
    When: Llega otra vez la cookie vieja
    Then: Se acepta: refresh nuevo desde el viejo, el sustituto sin usar queda anulado y
          el viejo apunta al último; un solo vivo
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(minutes=2))

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.refresh_token == "refresco-2"
    perdido, ultimo = await e.token("refresco-1"), await e.token("refresco-2")
    assert perdido.revoked
    assert (await e.token(ORIGINAL)).replaced_by_id == ultimo.id
    assert ultimo.expires_at == e.original.expires_at
    assert await e.vivos() == [ultimo]
    e.auditoria.log_refresh_token_reuse_detected.assert_not_called()


async def test_a3_at_sixty_one_seconds_it_is_already_a3():
    """
    Given: El sustituido hace 61 s, sustituto sin usar
    Then: Fuera del margen: se rota otra vez (A3), no se da solo el access (A2)
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(seconds=61))

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.refresh_token == "refresco-2"


# ---------------------------------------------------------------------------- A4


async def _robo(e: _Escena) -> RefreshRejectedError:
    """El viejo, sustituido hace 2 min, con su sustituto ya usado: llega el viejo."""
    await e.refresca(ORIGINAL)
    await e.refresca("refresco-1")
    await e.hace(ORIGINAL, timedelta(minutes=2))
    return await e.rechazo(ORIGINAL)


async def test_a4_reuse_revokes_the_whole_chain_of_the_device():
    """
    Given: El viejo fuera del margen y su sustituto ya usado (alguien tiene la cookie)
    When: Llega el viejo
    Then: SESSION_REJECTED y TODOS los tokens del dispositivo revocados, también el
          vigente; la cookie se borra
    """
    e = await _escena()

    rechazo = await _robo(e)

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REUSED
    assert codigo_publico(rechazo.motivo) == SESSION_REJECTED
    assert rechazo.conserva_la_cookie is False
    assert all(t.revoked for t in await e.del_dispositivo())
    assert len(await e.del_dispositivo()) == 3


async def test_a4_after_the_theft_the_current_one_is_rejected_too():
    """
    Given: Un robo detectado
    When: Quien tenga el vigente refresca
    Then: Rechazado (SESSION_REJECTED)
    """
    e = await _escena()
    await _robo(e)

    rechazo = await e.rechazo("refresco-2")

    assert codigo_publico(rechazo.motivo) == SESSION_REJECTED


async def test_a4_other_devices_of_the_user_keep_their_session():
    """
    Given: El usuario tiene otra sesión en su Mac
    When: Se detecta el robo en el iPhone
    Then: La del Mac sigue viva
    """
    e = await _escena()
    mac = UserDevice.create(e.usuario.id, DeviceFingerprint.create("Mac", "198.51.100.1"))
    await e.uow.user_devices.save(mac)
    del_mac = RefreshToken.create(user_id=e.usuario.id, token="del-mac", device_id=mac.id)
    await e.uow.refresh_tokens.save(del_mac)

    await _robo(e)

    assert await e.vivos(mac) == [del_mac]


async def test_a4_logs_a_high_security_event():
    """
    Given: Un robo detectado
    Then: Al log de seguridad, con el usuario, el dispositivo y cuántos se revocaron
    """
    e = await _escena()

    await _robo(e)

    e.auditoria.log_refresh_token_reuse_detected.assert_called_once()
    datos = e.auditoria.log_refresh_token_reuse_detected.call_args.kwargs
    assert datos["user_id"] == str(e.usuario.id.value)
    assert datos["device_id"] == str(e.dispositivo.id.value)
    assert datos["tokens_revoked_count"] == 3
    assert datos["user_agent"] == IPHONE


async def test_a4_warns_the_user_by_email():
    """
    Given: Un robo detectado
    Then: Se pide el aviso por correo (en segundo plano), con su correo, nombre y el
          dispositivo de la sesión cerrada
    """
    e = await _escena()

    await _robo(e)

    e.aviso.avisa.assert_awaited_once_with(
        AvisoDeSesionCerradaRequestDTO(
            user_id=str(e.usuario.id.value),
            email="ana@example.com",
            nombre="Ana",
            device_id=str(e.dispositivo.id.value),
            verificado=True,
        )
    )


async def test_a4_a_failing_email_or_log_does_not_change_the_answer():
    """
    Given: El aviso por correo y el log fallan
    When: Se detecta el robo
    Then: El rechazo es el mismo y la cadena queda revocada igual
    """
    e = await _escena()
    e.aviso.avisa.side_effect = RuntimeError("proveedor caído")
    e.auditoria.log_refresh_token_reuse_detected.side_effect = RuntimeError("log caído")

    rechazo = await _robo(e)

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REUSED
    assert all(t.revoked for t in await e.del_dispositivo())


async def test_a4_the_theft_wins_over_a_newer_session_in_the_browser():
    """
    Given: Un robo y, en la cookie de dispositivo del navegador, otra cuenta con un login
           de hace 10 s
    When: Llega el viejo
    Then: Sigue siendo el robo: SESSION_REJECTED, se borra la cookie y se revoca todo
    """
    e = await _escena()
    otra = UserDevice.create(e.usuario.id, DeviceFingerprint.create("Otra", "198.51.100.2"))
    await e.uow.user_devices.save(otra)
    await e.otra_sesion_nueva(otra)
    await e.refresca(ORIGINAL)
    await e.refresca("refresco-1")
    await e.hace(ORIGINAL, timedelta(minutes=2))

    rechazo = await e.rechazo(ORIGINAL, navegador=(str(otra.id.value),))

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REUSED
    assert rechazo.conserva_la_cookie is False
    assert all(t.revoked for t in await e.del_dispositivo())


# ---------------------------------------------------------------------------- A5


async def test_a5_within_the_margin_a_newer_login_answers_replaced():
    """
    Given: El viejo sustituido hace 10 s y, en ese dispositivo, un login más nuevo
    When: Llega el viejo
    Then: SESSION_REPLACED (conserva la cookie), sin emitir nada de la sesión vieja
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(seconds=10))
    await e.otra_sesion_nueva()
    e.tokens.create_access_token.reset_mock()

    rechazo = await e.rechazo(ORIGINAL)

    assert rechazo.conserva_la_cookie is True
    e.tokens.create_access_token.assert_not_called()


async def test_a5_outside_the_margin_a_newer_login_neither_rotates_nor_annuls():
    """
    Given: El viejo sustituido hace 2 min, sustituto sin usar, y un login más nuevo
    When: Llega el viejo
    Then: SESSION_REPLACED; ni se rota otra vez ni se anula el sustituto
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(minutes=2))
    await e.otra_sesion_nueva()

    rechazo = await e.rechazo(ORIGINAL)

    assert rechazo.conserva_la_cookie is True
    assert not (await e.token("refresco-1")).revoked
    assert e.tokens.create_refresh_token.call_count == 1


async def test_a5_its_own_chain_is_not_a_newer_session():
    """
    Given: El viejo sustituido hace 10 s por su propio sucesor (creado ahora mismo)
    When: Llega el viejo
    Then: A2, no SESSION_REPLACED: la propia cadena no es «una sesión más nueva»
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(seconds=10))

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.access_token == "acceso"


async def test_a5_a_revoked_one_with_a_newer_login_is_still_replaced():
    """
    Given: Toda la cadena revocada (cerró sesión) y un login nuevo en el dispositivo
    When: Llega una cookie de la cadena vieja
    Then: SESSION_REPLACED, como hoy (BE #734)
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.uow.refresh_tokens.revoke_all_for_device(e.dispositivo.id)
    await e.otra_sesion_nueva()

    rechazo = await e.rechazo(ORIGINAL)

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REVOKED
    assert rechazo.conserva_la_cookie is True


# ---------------------------------------------------------------------------- otros


async def test_a_substitute_revoked_by_another_way_rejects_the_old_one():
    """
    Given: El viejo sustituido y su sustituto revocado por otra vía (no la cadena)
    When: Llega el viejo
    Then: Rechazado como revocado; no se reanuda la sesión desde el viejo
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    sustituto = await e.token("refresco-1")
    sustituto.revoke()
    await e.hace(ORIGINAL, timedelta(minutes=2))

    rechazo = await e.rechazo(ORIGINAL)

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REVOKED
    assert e.tokens.create_refresh_token.call_count == 1


async def test_a6_logout_after_rotating_revokes_the_whole_chain():
    """
    Given: Un refresco hecho (viejo sustituido, nuevo vigente)
    When: Se revocan los tokens del dispositivo (cerrar sesión o revocar el dispositivo)
    Then: El viejo y el nuevo dan rechazo
    """
    e = await _escena()
    await e.refresca(ORIGINAL)

    await e.uow.refresh_tokens.revoke_all_for_device(e.dispositivo.id)

    assert (await e.rechazo(ORIGINAL)).motivo is RefreshRejection.REFRESH_TOKEN_REVOKED
    assert (await e.rechazo("refresco-1")).motivo is RefreshRejection.REFRESH_TOKEN_REVOKED


async def test_a7_a_token_from_before_the_rotation_is_rotated_on_first_use():
    """
    Given: Un token de antes del despliegue (sin datos de sustitución)
    When: Refresca
    Then: Vale, y se rota
    """
    e = await _escena()
    e.original._replaced_at = None
    e.original._replaced_by_id = None

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.refresh_token == "refresco-1"


# ------------------------------------------------- tras la revisión (Agustín, 10 nov)


async def test_a4_the_theft_also_revokes_the_device():
    """
    Given: Un robo detectado
    Then: El dispositivo queda revocado: el access del atacante deja de valer al
          instante y un sustituto que se cuele choca con el dispositivo revocado
    """
    e = await _escena()

    await _robo(e)

    assert not (await e.uow.user_devices.find_by_id(e.dispositivo.id)).is_active


async def test_a3_an_annulled_substitute_that_comes_back_is_a_theft():
    """
    Given: Un A3 que anuló el sustituto sin usar (no llegó al navegador)
    When: Alguien llega después con ese sustituto anulado
    Then: Robo: SESSION_REJECTED, dispositivo y tokens revocados, log HIGH y correo
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(minutes=2))
    await e.refresca(ORIGINAL)

    rechazo = await e.rechazo("refresco-1")

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REUSED
    assert all(t.revoked for t in await e.del_dispositivo())
    assert not (await e.uow.user_devices.find_by_id(e.dispositivo.id)).is_active
    e.auditoria.log_refresh_token_reuse_detected.assert_called_once()
    e.aviso.avisa.assert_awaited_once()


async def test_a3_only_within_one_hour_of_the_replacement():
    """
    Given: El viejo sustituido hace 61 minutos con el sustituto sin usar
    When: Llega el viejo
    Then: Robo, no A3: una respuesta perdida no tarda una hora en reintentarse
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(minutes=61))

    rechazo = await e.rechazo(ORIGINAL)

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REUSED
    assert not (await e.uow.user_devices.find_by_id(e.dispositivo.id)).is_active


async def test_a3_at_fifty_nine_minutes_it_still_resumes():
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.hace(ORIGINAL, timedelta(minutes=59))

    respuesta = await e.refresca(ORIGINAL)

    assert respuesta.refresh_token == "refresco-2"


async def test_review_attacker_first_then_victim_then_attacker_again():
    """
    El escenario de la revisión: el atacante usa T0 antes que la víctima.

    Given: El atacante refresca con T0 robado y se queda con T1
    When: La víctima llega con T0 (2 min después, T1 sin usar: parece una respuesta
          perdida, A3) y luego el atacante usa T1
    Then: Al volver T1 (anulado) salta la alarma y toda la cadena muere, también la
          de la víctima (T2): los dos tienen que volver a entrar
    """
    e = await _escena()
    await e.refresca(ORIGINAL)  # el atacante: T1
    await e.hace(ORIGINAL, timedelta(minutes=2))
    victima = await e.refresca(ORIGINAL)  # la víctima: A3, T2
    assert victima.refresh_token == "refresco-2"

    rechazo = await e.rechazo("refresco-1")  # el atacante vuelve con T1

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REUSED
    assert await e.vivos() == []
    assert codigo_publico((await e.rechazo("refresco-2")).motivo) == SESSION_REJECTED


async def test_review_attacker_keeps_rotating_and_the_victim_sets_off_the_alarm():
    """
    Given: El atacante refrescó con T0 robado (T1) y luego con T1 (T2)
    When: La víctima llega con T0
    Then: Robo: la cadena del atacante muere (T2 rechazado) y el dispositivo, revocado
    """
    e = await _escena()
    await e.refresca(ORIGINAL)
    await e.refresca("refresco-1")
    await e.hace(ORIGINAL, timedelta(minutes=2))

    rechazo = await e.rechazo(ORIGINAL)

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_REUSED
    assert codigo_publico((await e.rechazo("refresco-2")).motivo) == SESSION_REJECTED


async def test_a_rejection_releases_its_locks():
    """
    Given: Un token revocado (el rechazo deja abierta la transacción del FOR UPDATE)
    When: Se rechaza
    Then: Se hace rollback explícito: los bloqueos no esperan al cierre de la sesión
    """
    e = await _escena()
    e.original.revoke()
    e.uow.rollback = AsyncMock(wraps=e.uow.rollback)

    await e.rechazo(ORIGINAL)

    e.uow.rollback.assert_awaited()
