"""
Integration Tests - Quién cuenta en cada límite (RyderCupAM#273)

En producción todas las peticiones llegan con la IP del proxy de Render (ADR-038),
así que un límite por IP es un límite para toda la app. Aquí se comprueba lo que lo
sustituye:

- con sesión, cada usuario tiene su contador, y cambiar de red no le da otro;
- el login cuenta por email (antes de saber si existe) y, por red, solo los fallos;
- forgot-password y resend-verification cuentan por email.

En los tests, X-Test-Client-ID hace de red: el fixture client pone uno por test.

OWASP: A04 (Insecure Design), A07 (Identification and Authentication Failures)
"""

import uuid

import pytest
from httpx import AsyncClient

from main import app
from src.config.dependencies import get_handicap_service
from src.config.rate_limit import limiter
from src.modules.user.infrastructure.external.mock_handicap_service import (
    MockHandicapService,
)
from tests.conftest import create_authenticated_user

PASSWORD = "P@ssw0rd123!"


def _network(name: str) -> dict:
    return {"X-Test-Client-ID": name}


def _as(client: AsyncClient, user: dict, network: str) -> dict:
    """
    Cabeceras de un usuario desde una red.

    get_current_user prefiere la cookie al Bearer, y el client guarda la del último
    que inició sesión: sin vaciarla, todas las peticiones irían como él.
    """
    client.cookies.clear()
    return {"Authorization": f"Bearer {user['token']}", **_network(network)}


async def _login(client: AsyncClient, email: str, password: str, network: str):
    client.cookies.clear()
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers=_network(network),
    )


def _email() -> str:
    return f"player-{uuid.uuid4().hex[:10]}@test.com"


@pytest.mark.integration
class TestSessionTrafficCountsPerUser:
    """Rutas con sesión: el contador es del usuario, no de la red."""

    def setup_method(self):
        mock = MockHandicapService(handicaps={}, default=None)
        app.dependency_overrides[get_handicap_service] = lambda: mock

    def teardown_method(self):
        app.dependency_overrides.pop(get_handicap_service, None)

    async def _update_own_handicap(self, client, user, network):
        return await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user["user"]["id"], "manual_handicap": 15.5},
            headers=_as(client, user, network),
        )

    @pytest.mark.asyncio
    async def test_two_players_on_the_same_network_have_their_own_limit(self, client: AsyncClient):
        """
        Given: A y B en la misma red, y /handicaps/update con 5/hora
        When: A agota su límite
        Then: A recibe 429 y B sigue pudiendo
        """
        a = await create_authenticated_user(client, _email(), PASSWORD, "Ana", "Uno")
        b = await create_authenticated_user(client, _email(), PASSWORD, "Bea", "Dos")

        for _ in range(5):
            assert (await self._update_own_handicap(client, a, "club-wifi")).status_code == 200

        assert (await self._update_own_handicap(client, a, "club-wifi")).status_code == 429
        assert (await self._update_own_handicap(client, b, "club-wifi")).status_code == 200

    @pytest.mark.asyncio
    async def test_changing_network_does_not_give_a_player_a_new_limit(self, client: AsyncClient):
        """
        Given: A con su límite agotado
        When: Repite desde otra red
        Then: Sigue con 429: el contador es suyo, no de la red
        """
        a = await create_authenticated_user(client, _email(), PASSWORD, "Ana", "Uno")
        for _ in range(5):
            await self._update_own_handicap(client, a, "club-wifi")

        response = await self._update_own_handicap(client, a, "mobile-data")

        assert response.status_code == 429


@pytest.mark.integration
class TestLoginCountsPerEmailAndFailuresPerNetwork:
    """Login: 5/min por email, y por red solo los intentos fallidos."""

    @pytest.mark.asyncio
    async def test_sixth_attempt_on_one_email_is_refused_from_any_network(
        self, client: AsyncClient
    ):
        """
        Given: Un email que no existe
        When: Se intenta 6 veces, cada vez desde una red distinta
        Then: Las 5 primeras dan 401 y la 6.ª 429
        """
        email = _email()

        statuses = [
            (await _login(client, email, "Wrong123!", f"net-{i}")).status_code for i in range(6)
        ]

        assert statuses == [401] * 5 + [429]

    @pytest.mark.asyncio
    async def test_the_same_email_written_differently_counts_together(self, client: AsyncClient):
        """
        Given: Un email
        When: Se intenta con mayúsculas y espacios alternos, 6 veces
        Then: Cuenta como el mismo: la 6.ª da 429
        """
        email = _email()
        variants = [email, email.upper(), f"  {email}", email.title(), email, email.upper()]

        statuses = [
            (await _login(client, v, "Wrong123!", f"net-{i}")).status_code
            for i, v in enumerate(variants)
        ]

        assert statuses[-1] == 429

    @pytest.mark.asyncio
    async def test_an_existing_email_is_limited_exactly_like_an_unknown_one(
        self, client: AsyncClient
    ):
        """
        Given: Un email registrado y otro que no existe
        When: Se intenta 6 veces cada uno con contraseña errónea
        Then: Los dos dan 401 cinco veces y 429 la sexta: el límite no delata cuál existe
        """
        real = _email()
        await create_authenticated_user(client, real, PASSWORD, "Real", "Player")
        unknown = _email()
        limiter.reset()  # el registro ya inició sesión una vez con ese email

        real_statuses = [
            (await _login(client, real, "Wrong123!", f"r-{i}")).status_code for i in range(6)
        ]
        unknown_statuses = [
            (await _login(client, unknown, "Wrong123!", f"u-{i}")).status_code for i in range(6)
        ]

        assert real_statuses == unknown_statuses == [401] * 5 + [429]

    @pytest.mark.asyncio
    async def test_failures_from_one_network_close_login_for_that_network(
        self, client: AsyncClient
    ):
        """
        Given: 29 fallos con emails inexistentes y 1 con contraseña errónea, desde una red
        When: Alguien de esa red entra con su contraseña correcta
        Then: 429: el tope de 30 fallos por minuto se ha agotado, y el fallo con
              contraseña errónea cuenta igual que el de un email inexistente
        """
        player = _email()
        await create_authenticated_user(client, player, PASSWORD, "Club", "Member")

        for _ in range(29):
            assert (await _login(client, _email(), "Wrong123!", "venue")).status_code == 401
        assert (await _login(client, player, "Wrong123!", "venue")).status_code == 401

        response = await _login(client, player, PASSWORD, "venue")

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_twenty_nine_failures_do_not_close_login(self, client: AsyncClient):
        """
        Given: 29 fallos desde una red
        When: Alguien de esa red entra con su contraseña correcta
        Then: 200: el tope está en 30, no antes
        """
        player = _email()
        await create_authenticated_user(client, player, PASSWORD, "Club", "Member")

        for _ in range(29):
            await _login(client, _email(), "Wrong123!", "venue")

        assert (await _login(client, player, PASSWORD, "venue")).status_code == 200

    @pytest.mark.asyncio
    async def test_successful_logins_do_not_use_up_the_failure_limit(self, client: AsyncClient):
        """
        Given: 7 jugadores de un club en la misma red
        When: Entran 5 veces cada uno (35 logins correctos, más que el tope de fallos)
        Then: Ninguno recibe 429
        """
        players = [_email() for _ in range(7)]
        for email in players:
            await create_authenticated_user(client, email, PASSWORD, "Club", "Member")
        limiter.reset()  # el registro ya inició sesión una vez con cada email

        statuses = [
            (await _login(client, email, PASSWORD, "venue")).status_code
            for email in players
            for _ in range(5)
        ]

        assert statuses == [200] * 35


@pytest.mark.integration
class TestEmailSendingCountsPerEmail:
    """forgot-password y resend-verification: 3/hora por email, desde cualquier red."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path", ["/api/v1/auth/forgot-password", "/api/v1/auth/resend-verification"]
    )
    async def test_fourth_request_for_one_email_is_refused_from_any_network(
        self, client: AsyncClient, path: str
    ):
        """
        Given: Un email
        When: Se pide 4 veces, cada vez desde una red distinta
        Then: La 4.ª da 429
        """
        email = _email()

        statuses = [
            (await client.post(path, json={"email": email}, headers=_network(f"n-{i}"))).status_code
            for i in range(4)
        ]

        assert statuses[:3].count(429) == 0
        assert statuses[3] == 429

    @pytest.mark.asyncio
    async def test_different_emails_from_one_network_are_not_limited_at_three(
        self, client: AsyncClient
    ):
        """
        Given: Una red
        When: Pide forgot-password para 5 emails distintos
        Then: Ninguno da 429: el tope por red es 30/hora
        """
        statuses = [
            (
                await client.post(
                    "/api/v1/auth/forgot-password",
                    json={"email": _email()},
                    headers=_network("venue"),
                )
            ).status_code
            for _ in range(5)
        ]

        assert 429 not in statuses
