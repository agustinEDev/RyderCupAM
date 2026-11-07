"""
La pieza que manda los correos: Mailgun, Brevo y Resend de respaldo, y Mailpit (7 nov 2026).

Tabla del bloque 1 (BE #148, #563), aprobada por Agustín:

  E1  mailgun: POST a Mailgun con remitente, destinatario, asunto, texto y HTML; 200 → enviado
  E2  sin clave: no llama a nadie, no enviado
  E3  Mailgun lo rechaza: no enviado, en el log solo el código (sin el cuerpo)
  E4  429 de Mailgun: un error propio («Mailgun quota or rate limit reached»)
  E5  red o espera de 10 s: no enviado, en el log solo el tipo del error
  E8  mailpit: a la API de Mailpit, con «Responder a», nunca a Mailgun
  E9  en producción solo mailgun; un valor desconocido no arranca en ningún sitio
  E13 429 con clave de Brevo: sale por Brevo (con HTML y «Responder a»)
  E14 429 sin clave de Brevo: no enviado
  E15 los dos fallan: no enviado y un error propio
  E16 Brevo con 429 o 5xx de Mailgun; NO con espera agotada o red (pudo salir ya)
  E17 con mailpit, Brevo nunca

  Tras la prueba real (Brevo reescribe los enlaces y no deja quitarlo), Agustín:
  E13b cada correo dice si puede ir por Brevo; por defecto, que no (con token o aviso
       de seguridad: nunca, Agustín tras las revisiones)
  E13c con token: solo Resend; si falla, no enviado y error propio
  E13d sin token: Resend, y Brevo solo si fallan los dos (Agustín, tras la prueba
       real de Resend: sin reescribir enlaces ni «Anular suscripción»)
"""

import json
import logging
from dataclasses import replace

import httpx
import pytest

from src.shared.infrastructure.email.envio_de_correo import (
    CUPO_AGOTADO,
    FALLAN_LOS_RESPALDOS,
    BrevoTransport,
    CorreoSaliente,
    EnvioConRespaldo,
    MailgunTransport,
    MailpitTransport,
    ResendTransport,
    comprueba_el_envio_de_correo,
    crea_el_envio,
)

CORREO = CorreoSaliente(
    to="ana@example.com",
    subject="Verifica tu correo",
    text="Texto",
    html="<p>HTML</p>",
    reply_to="pepe@example.com",
)
REMITENTE = "Ryder Cup Friends <noreply@rydercupfriends.com>"
# Un aviso que puede ir por Brevo (ni token ni seguridad)
SIN_TOKEN = replace(CORREO, puede_ir_por_brevo=True)


class _Servidor:
    """Un servidor HTTP falso: apunta cada petición y responde lo que se le diga."""

    def __init__(self, estado=200, error=None):
        self.estado = estado
        self.error = error
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        if self.error:
            raise self.error
        return httpx.Response(self.estado, text='{"message":"datos del correo"}')

    @property
    def transporte(self):
        return httpx.MockTransport(self)


def _mailgun(servidor, api_key="clave-mg"):
    return MailgunTransport(
        api_key=api_key,
        api_url="https://api.eu.mailgun.net/v3",
        domain="rydercupfriends.com",
        from_email=REMITENTE,
        transporte_http=servidor.transporte,
    )


def _brevo(servidor, api_key="clave-brevo"):
    return BrevoTransport(
        api_key=api_key,
        api_url="https://api.brevo.com/v3",
        from_email=REMITENTE,
        transporte_http=servidor.transporte,
    )


def _formulario(peticion: httpx.Request) -> dict[str, str]:
    return dict(httpx.QueryParams(peticion.content.decode()))


# --- Mailgun -------------------------------------------------------------------


async def test_e1_mailgun_sends_everything_and_200_means_sent():
    servidor = _Servidor(200)

    enviado = await EnvioConRespaldo(_mailgun(servidor)).send(CORREO)

    assert enviado is True
    (peticion,) = servidor.peticiones
    assert str(peticion.url) == "https://api.eu.mailgun.net/v3/rydercupfriends.com/messages"
    assert peticion.headers["authorization"].startswith("Basic ")
    datos = _formulario(peticion)
    assert datos == {
        "from": REMITENTE,
        "to": "ana@example.com",
        "subject": "Verifica tu correo",
        "text": "Texto",
        "html": "<p>HTML</p>",
        "h:Reply-To": "pepe@example.com",
    }


async def test_e1_without_html_or_reply_to_they_are_not_sent():
    servidor = _Servidor(200)

    await EnvioConRespaldo(_mailgun(servidor)).send(
        CorreoSaliente(to="ana@example.com", subject="S", text="T")
    )

    assert set(_formulario(servidor.peticiones[0])) == {"from", "to", "subject", "text"}


async def test_e1_it_waits_at_most_ten_seconds_per_step():
    servidor = _Servidor(200)

    await EnvioConRespaldo(_mailgun(servidor)).send(CORREO)

    assert servidor.peticiones[0].extensions["timeout"]["read"] == 10.0


async def test_e2_without_key_nobody_is_called(caplog):
    servidor = _Servidor(200)

    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(_mailgun(servidor, api_key="")).send(CORREO)

    assert enviado is False
    assert servidor.peticiones == []
    assert "MAILGUN_API_KEY" in caplog.text


async def test_e2_without_mailgun_key_the_backups_are_used():
    """Como una clave rechazada (/code-review): sin clave de Mailgun, Resend."""
    resend = _Servidor(200)

    enviado = await EnvioConRespaldo(
        _mailgun(_Servidor(200), api_key=""), resend=_resend(resend)
    ).send(CORREO)

    assert enviado is True
    assert len(resend.peticiones) == 1


async def test_e3_a_refusal_logs_only_the_status(caplog):
    servidor = _Servidor(400)

    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(_mailgun(servidor)).send(CORREO)

    assert enviado is False
    assert "400" in caplog.text
    assert "datos del correo" not in caplog.text
    assert "ana@example.com" not in caplog.text


async def test_e4_a_429_is_its_own_error(caplog):
    servidor = _Servidor(429)

    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(_mailgun(servidor)).send(CORREO)

    assert enviado is False
    errores = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert [r.getMessage() for r in errores] == [CUPO_AGOTADO % "Mailgun"]
    assert CUPO_AGOTADO % "Mailgun" == "Mailgun quota or rate limit reached (429)"


@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout("lento"), httpx.ConnectError("sin red https://secreto"), ValueError("x")],
)
async def test_e5_network_or_timeout_logs_only_the_type(caplog, error):
    servidor = _Servidor(error=error)

    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(_mailgun(servidor)).send(CORREO)

    assert enviado is False
    assert type(error).__name__ in caplog.text
    assert "secreto" not in caplog.text


# --- Brevo de respaldo -----------------------------------------------------------


@pytest.mark.parametrize("estado", [429, 500, 503])
async def test_e13_e16_a_429_500_or_503_goes_out_through_brevo(estado):
    mailgun, brevo = _Servidor(estado), _Servidor(201)

    enviado = await EnvioConRespaldo(_mailgun(mailgun), _brevo(brevo)).send(SIN_TOKEN)

    assert enviado is True
    (peticion,) = brevo.peticiones
    assert str(peticion.url) == "https://api.brevo.com/v3/smtp/email"
    assert peticion.headers["api-key"] == "clave-brevo"
    assert json.loads(peticion.content) == {
        "sender": {"name": "Ryder Cup Friends", "email": "noreply@rydercupfriends.com"},
        "to": [{"email": "ana@example.com"}],
        "subject": "Verifica tu correo",
        "textContent": "Texto",
        "htmlContent": "<p>HTML</p>",
        "replyTo": {"email": "pepe@example.com"},
    }


async def test_e13_the_quota_error_still_fires_when_brevo_sends(caplog):
    with caplog.at_level(logging.ERROR):
        await EnvioConRespaldo(_mailgun(_Servidor(429)), _brevo(_Servidor(201))).send(SIN_TOKEN)

    assert CUPO_AGOTADO % "Mailgun" in caplog.text


async def test_e14_a_429_without_brevo_key_is_not_sent():
    brevo = _Servidor(201)

    enviado = await EnvioConRespaldo(_mailgun(_Servidor(429)), _brevo(brevo, api_key="")).send(
        SIN_TOKEN
    )

    assert enviado is False
    assert brevo.peticiones == []


@pytest.mark.parametrize(
    "fallo_de_brevo", [_Servidor(400), _Servidor(error=httpx.ConnectError("x"))]
)
async def test_e15_both_failing_is_its_own_error(caplog, fallo_de_brevo):
    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(_mailgun(_Servidor(503)), _brevo(fallo_de_brevo)).send(
            SIN_TOKEN
        )

    assert enviado is False
    assert FALLAN_LOS_RESPALDOS in caplog.text
    assert FALLAN_LOS_RESPALDOS == "Mailgun and its backups all failed"


@pytest.mark.parametrize(
    "mailgun",
    [
        _Servidor(error=httpx.ReadTimeout("lento")),
        _Servidor(error=httpx.ConnectError("x")),
        _Servidor(400),
    ],
)
async def test_e16_timeout_network_or_refusal_do_not_go_to_brevo(mailgun):
    brevo = _Servidor(201)

    enviado = await EnvioConRespaldo(_mailgun(mailgun), _brevo(brevo)).send(SIN_TOKEN)

    assert enviado is False
    assert brevo.peticiones == []


async def test_e16_mailgun_ok_does_not_touch_brevo():
    brevo = _Servidor(201)

    assert await EnvioConRespaldo(_mailgun(_Servidor(200)), _brevo(brevo)).send(SIN_TOKEN) is True
    assert brevo.peticiones == []


# --- Mailpit ---------------------------------------------------------------------


async def test_e8_mailpit_gets_the_whole_email():
    servidor = _Servidor(200)
    mailpit = MailpitTransport(
        url="http://mailpit:8025", from_email=REMITENTE, transporte_http=servidor.transporte
    )

    enviado = await EnvioConRespaldo(mailpit).send(CORREO)

    assert enviado is True
    (peticion,) = servidor.peticiones
    assert str(peticion.url) == "http://mailpit:8025/api/v1/send"
    assert json.loads(peticion.content) == {
        "From": {"Name": "Ryder Cup Friends", "Email": "noreply@rydercupfriends.com"},
        "To": [{"Email": "ana@example.com"}],
        "Subject": "Verifica tu correo",
        "Text": "Texto",
        "HTML": "<p>HTML</p>",
        "ReplyTo": [{"Email": "pepe@example.com"}],
    }


async def test_e8_mailpit_refusing_is_not_sent():
    mailpit = MailpitTransport(
        url="http://mailpit:8025", from_email=REMITENTE, transporte_http=_Servidor(500).transporte
    )

    assert await EnvioConRespaldo(mailpit).send(CORREO) is False


# --- Qué envío se monta y cuándo no arranca --------------------------------------


def _entorno(**valores):
    base = {
        "EMAIL_TRANSPORT": "mailgun",
        "MAILGUN_API_KEY": "mg",
        "MAILGUN_API_URL": "https://api.eu.mailgun.net/v3",
        "MAILGUN_DOMAIN": "rydercupfriends.com",
        "MAILGUN_FROM_EMAIL": REMITENTE,
        "BREVO_API_KEY": "",
        "RESEND_API_KEY": "",
        "MAILPIT_URL": "http://mailpit:8025",
    }
    base.update(valores)
    return base


def test_e8_e17_mailpit_mounts_only_mailpit():
    envio = crea_el_envio(
        _entorno(EMAIL_TRANSPORT="mailpit", BREVO_API_KEY="br", RESEND_API_KEY="re")
    )

    assert isinstance(envio.primario, MailpitTransport)
    assert envio.brevo is None and envio.resend is None


def test_mailgun_mounts_brevo_as_backup_only_with_its_key():
    con = crea_el_envio(_entorno(BREVO_API_KEY="br"))
    sin = crea_el_envio(_entorno())

    assert isinstance(con.primario, MailgunTransport)
    assert isinstance(con.brevo, BrevoTransport)
    assert sin.brevo is None


def test_by_default_it_is_mailgun():
    entorno = _entorno()
    del entorno["EMAIL_TRANSPORT"]

    assert isinstance(crea_el_envio(entorno).primario, MailgunTransport)


@pytest.mark.parametrize(
    ("environment", "transporte"),
    [
        ("production", "mailpit"),
        ("PRODUCTION", "mailpit"),
        ("development", "smtp"),
    ],
)
def test_e9_it_does_not_start(environment, transporte):
    with pytest.raises(RuntimeError, match="EMAIL_TRANSPORT"):
        comprueba_el_envio_de_correo({"ENVIRONMENT": environment, "EMAIL_TRANSPORT": transporte})


@pytest.mark.parametrize(
    "entorno",
    [
        {"ENVIRONMENT": "production", "EMAIL_TRANSPORT": "mailgun", "MAILGUN_API_KEY": "mg"},
        {"ENVIRONMENT": "production", "MAILGUN_API_KEY": "mg"},
        {"ENVIRONMENT": "development", "EMAIL_TRANSPORT": "mailpit"},
        {"EMAIL_TRANSPORT": "MAILPIT"},
        {},
    ],
)
def test_e9_these_start(entorno):
    comprueba_el_envio_de_correo(entorno)


async def test_empty_values_take_their_default():
    """El docker-compose pone las variables vacías: valen sus valores por defecto."""
    servidor = _Servidor(200)
    envio = crea_el_envio(
        _entorno(EMAIL_TRANSPORT="", MAILGUN_DOMAIN="", MAILGUN_FROM_EMAIL="", MAILGUN_API_URL="")
    )
    envio.primario._transporte_http = servidor.transporte

    await envio.send(CORREO)

    peticion = servidor.peticiones[0]
    assert str(peticion.url) == "https://api.eu.mailgun.net/v3/rydercupfriends.com/messages"
    assert _formulario(peticion)["from"] == REMITENTE


def test_an_empty_transport_is_mailgun_also_in_production():
    comprueba_el_envio_de_correo(
        {"ENVIRONMENT": "production", "EMAIL_TRANSPORT": "", "MAILGUN_API_KEY": "mg"}
    )


async def test_a_named_recipient_goes_split_to_brevo_and_mailpit():
    """La verificación va a '"Ana" <ana@…>': Brevo y Mailpit lo quieren por partes."""
    correo = CorreoSaliente(
        to='"Ana López" <ana@example.com>', subject="S", text="T", puede_ir_por_brevo=True
    )
    brevo, mailpit = _Servidor(201), _Servidor(200)

    await EnvioConRespaldo(_mailgun(_Servidor(429)), _brevo(brevo)).send(correo)
    await EnvioConRespaldo(
        MailpitTransport(
            url="http://mailpit:8025", from_email=REMITENTE, transporte_http=mailpit.transporte
        )
    ).send(correo)

    assert json.loads(brevo.peticiones[0].content)["to"] == [
        {"email": "ana@example.com", "name": "Ana López"}
    ]
    assert json.loads(mailpit.peticiones[0].content)["To"] == [
        {"Email": "ana@example.com", "Name": "Ana López"}
    ]


# --- Resend, y qué respaldo según lleve token -------------------------------------


def _resend(servidor, api_key="clave-resend"):
    return ResendTransport(
        api_key=api_key,
        api_url="https://api.resend.com",
        from_email=REMITENTE,
        transporte_http=servidor.transporte,
    )


def test_e13b_by_default_an_email_never_goes_through_brevo():
    assert CorreoSaliente(to="a@b.com", subject="S", text="T").puede_ir_por_brevo is False


async def test_e13c_resend_gets_the_whole_email():
    resend = _Servidor(200)

    enviado = await EnvioConRespaldo(_mailgun(_Servidor(429)), resend=_resend(resend)).send(CORREO)

    assert enviado is True
    (peticion,) = resend.peticiones
    assert str(peticion.url) == "https://api.resend.com/emails"
    assert peticion.headers["authorization"] == "Bearer clave-resend"
    assert json.loads(peticion.content) == {
        "from": REMITENTE,
        "to": ["ana@example.com"],
        "subject": "Verifica tu correo",
        "text": "Texto",
        "html": "<p>HTML</p>",
        "reply_to": "pepe@example.com",
    }


@pytest.mark.parametrize("estado", [429, 503])
async def test_e13c_a_token_email_never_goes_through_brevo(estado):
    brevo, resend = _Servidor(201), _Servidor(200)

    enviado = await EnvioConRespaldo(
        _mailgun(_Servidor(estado)), _brevo(brevo), _resend(resend)
    ).send(CORREO)

    assert enviado is True
    assert brevo.peticiones == []
    assert len(resend.peticiones) == 1


async def test_e13c_a_token_email_without_resend_is_not_sent_even_with_brevo():
    brevo = _Servidor(201)

    enviado = await EnvioConRespaldo(_mailgun(_Servidor(429)), _brevo(brevo)).send(CORREO)

    assert enviado is False
    assert brevo.peticiones == []


@pytest.mark.parametrize("fallo", [_Servidor(422), _Servidor(error=httpx.ConnectError("x"))])
async def test_e13c_resend_failing_is_the_backups_error(caplog, fallo):
    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(
            _mailgun(_Servidor(429)), _brevo(_Servidor(201)), _resend(fallo)
        ).send(CORREO)

    assert enviado is False
    assert FALLAN_LOS_RESPALDOS in caplog.text


async def test_e13d_without_token_resend_first_and_brevo_untouched():
    """Agustín, tras la prueba real: Resend antes, Brevo solo si fallan los dos."""
    brevo, resend = _Servidor(201), _Servidor(200)

    await EnvioConRespaldo(_mailgun(_Servidor(429)), _brevo(brevo), _resend(resend)).send(SIN_TOKEN)

    assert len(resend.peticiones) == 1
    assert brevo.peticiones == []


@pytest.mark.parametrize("estado", [429, 500])
async def test_e13d_without_token_resend_429_or_5xx_goes_to_brevo(estado):
    brevo = _Servidor(201)

    enviado = await EnvioConRespaldo(
        _mailgun(_Servidor(429)), _brevo(brevo), _resend(_Servidor(estado))
    ).send(SIN_TOKEN)

    assert enviado is True
    assert len(brevo.peticiones) == 1


@pytest.mark.parametrize(
    "resend", [_Servidor(error=httpx.ReadTimeout("x")), _Servidor(error=httpx.ConnectError("x"))]
)
async def test_e16_resend_timeout_or_network_does_not_go_to_brevo(resend):
    """Como con Mailgun: pudo salir ya, no se repite por otro."""
    brevo = _Servidor(201)

    enviado = await EnvioConRespaldo(_mailgun(_Servidor(429)), _brevo(brevo), _resend(resend)).send(
        SIN_TOKEN
    )

    assert enviado is False
    assert brevo.peticiones == []


async def test_e13d_without_resend_key_it_goes_to_brevo():
    brevo = _Servidor(201)

    enviado = await EnvioConRespaldo(
        _mailgun(_Servidor(429)), _brevo(brevo), _resend(_Servidor(200), api_key="")
    ).send(SIN_TOKEN)

    assert enviado is True
    assert len(brevo.peticiones) == 1


@pytest.mark.parametrize("mailgun", [_Servidor(error=httpx.ReadTimeout("lento")), _Servidor(400)])
async def test_e16_timeout_or_refusal_do_not_go_to_resend(mailgun):
    resend = _Servidor(200)

    assert await EnvioConRespaldo(_mailgun(mailgun), resend=_resend(resend)).send(CORREO) is False
    assert resend.peticiones == []


def test_resend_is_mounted_only_with_its_key():
    assert isinstance(crea_el_envio(_entorno(RESEND_API_KEY="re")).resend, ResendTransport)
    assert crea_el_envio(_entorno()).resend is None


# --- Tras las revisiones (7 nov 2026) ----------------------------------------------


async def test_r1_a_resend_refusal_does_not_go_to_brevo(caplog):
    """La misma regla entre respaldos: tras un rechazo 4xx no se prueba el siguiente."""
    brevo = _Servidor(201)

    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(
            _mailgun(_Servidor(429)), _brevo(brevo), _resend(_Servidor(422))
        ).send(SIN_TOKEN)

    assert enviado is False
    assert brevo.peticiones == []
    assert FALLAN_LOS_RESPALDOS in caplog.text


@pytest.mark.parametrize("estado", [401, 403])
async def test_r2_a_rejected_mailgun_key_uses_the_backups(estado):
    """Agustín: la clave de Mailgun revocada o caducada cuenta como Mailgun caído."""
    resend = _Servidor(200)

    enviado = await EnvioConRespaldo(_mailgun(_Servidor(estado)), resend=_resend(resend)).send(
        CORREO
    )

    assert enviado is True
    assert len(resend.peticiones) == 1


async def test_r3_a_mailpit_429_does_not_say_mailgun(caplog):
    mailpit = MailpitTransport(
        url="http://mailpit:8025", from_email=REMITENTE, transporte_http=_Servidor(429).transporte
    )

    with caplog.at_level(logging.ERROR):
        await EnvioConRespaldo(mailpit).send(CORREO)

    assert "Mailgun" not in caplog.text
    assert "Mailpit quota or rate limit reached (429)" in caplog.text


@pytest.mark.parametrize("estado", [502, 504])
async def test_r4_a_gateway_502_or_504_is_doubtful_and_not_resent(estado):
    """Un 502/504 de pasarela puede llegar con el correo ya aceptado (/code-review): no se
    repite por otro proveedor, o el usuario recibiría dos."""
    resend = _Servidor(200)

    enviado = await EnvioConRespaldo(_mailgun(_Servidor(estado)), resend=_resend(resend)).send(
        CORREO
    )

    assert enviado is False
    assert resend.peticiones == []


async def test_r4_no_backup_starts_without_time_for_a_whole_step(caplog):
    """El tope total no corta un envío a medias (podría haber salido): solo no empieza
    otro proveedor si ya no queda tiempo para un paso entero."""
    from src.shared.infrastructure.email import envio_de_correo

    instantes = iter(
        [0.0, envio_de_correo.PRESUPUESTO_TOTAL - envio_de_correo.TIEMPO_POR_PASO + 0.1]
    )
    resend = _Servidor(200)

    with caplog.at_level(logging.ERROR):
        enviado = await EnvioConRespaldo(
            _mailgun(_Servidor(503)), resend=_resend(resend), reloj=lambda: next(instantes)
        ).send(CORREO)

    assert enviado is False
    assert resend.peticiones == []
    assert envio_de_correo.SIN_TIEMPO in caplog.text


async def test_r4_with_time_left_the_backup_starts():
    from src.shared.infrastructure.email import envio_de_correo

    instantes = iter(
        [0.0, envio_de_correo.PRESUPUESTO_TOTAL - envio_de_correo.TIEMPO_POR_PASO - 0.1]
    )
    resend = _Servidor(200)

    enviado = await EnvioConRespaldo(
        _mailgun(_Servidor(503)), resend=_resend(resend), reloj=lambda: next(instantes)
    ).send(CORREO)

    assert enviado is True


def test_r4_the_budget_and_the_connect_timeout():
    from src.shared.infrastructure.email import envio_de_correo

    assert envio_de_correo.PRESUPUESTO_TOTAL == 25.0
    assert envio_de_correo.TIEMPO_POR_PASO == 15.0
    assert envio_de_correo.ESPERA.connect == 5.0
    assert envio_de_correo.ESPERA.read == 10.0


@pytest.mark.parametrize(
    "clave", ["MAILGUN_API_URL", "RESEND_API_URL", "BREVO_API_URL", "MAILPIT_URL"]
)
def test_r5_production_needs_https_provider_urls(clave):
    entorno = {"ENVIRONMENT": "production", "MAILGUN_API_KEY": "mg", clave: "http://x.com/v3"}

    if clave == "MAILPIT_URL":
        comprueba_el_envio_de_correo(entorno)  # en producción no se usa
    else:
        with pytest.raises(RuntimeError, match=clave):
            comprueba_el_envio_de_correo(entorno)


def test_r5_outside_production_http_is_fine():
    comprueba_el_envio_de_correo({"ENVIRONMENT": "development", "MAILGUN_API_URL": "http://x/v3"})


@pytest.mark.parametrize("valor", ["", "   "])
def test_r5_production_needs_a_mailgun_key(valor):
    with pytest.raises(RuntimeError, match="MAILGUN_API_KEY"):
        comprueba_el_envio_de_correo({"ENVIRONMENT": "production", "MAILGUN_API_KEY": valor})


def test_r7_one_sender_per_process():
    """Un solo envío por proceso (/code-review): no se rehace en cada petición."""
    from src.shared.infrastructure.email.envio_de_correo import envio_de_la_app

    assert envio_de_la_app() is envio_de_la_app()
