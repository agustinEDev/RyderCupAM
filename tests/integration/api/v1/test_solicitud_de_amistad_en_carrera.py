"""
Una solicitud de amistad que pierde la carrera contra otra fila de la pareja.

B lee que no hay relación con A y, antes de que su INSERT llegue a la base de
datos, A le bloquea (o le manda su propia solicitud). El índice único
`uq_friendship_pair` rechaza el INSERT de B, y antes ese rechazo salía en el
commit, sin traducir: un 500 (11 de 111 veces en el Kind).

La carrera se reproduce sin depender del reloj: la primera lectura de la pareja
devuelve lo que había (nada) y justo después se confirma la fila de A desde
otra sesión, como haría la petición de A que gana.
"""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient

from main import app as fastapi_app
from src.config.dependencies import get_db_session
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import DuplicateFriendshipViolation
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.sqlalchemy.friendship_repository import (
    SQLAlchemyFriendshipRepository,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.social_unit_of_work import (
    SQLAlchemySocialUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.conftest import create_authenticated_user, set_auth_cookies, sql_en_la_bd_de_test


@pytest_asyncio.fixture(autouse=True)
async def _indice_unico_de_produccion(client: AsyncClient) -> None:
    """El índice de la pareja solo existe en la migración 7cec1e04eb61: se crea igual."""
    await sql_en_la_bd_de_test(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_friendship_pair ON friendships "
        "(LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id))"
    )


async def _dos_usuarios(client: AsyncClient) -> tuple[dict, dict]:
    sufijo = uuid.uuid4().hex[:8]
    a = await create_authenticated_user(
        client, f"carrera_a_{sufijo}@test.com", "P@ssw0rd123!", "Carrera", "Aa"
    )
    b = await create_authenticated_user(
        client, f"carrera_b_{sufijo}@test.com", "P@ssw0rd123!", "Carrera", "Bb"
    )
    return a, b


def _gana_a_mitad(
    monkeypatch,
    *,
    requester_id: str,
    addressee_id: str,
    status: str,
    blocked_by,
    antes_de_releer: str | None = None,
):
    """La primera lectura de la pareja no ve nada; justo después A confirma su fila.

    Con `antes_de_releer`, ese SQL se confirma justo antes de la segunda lectura
    (la que hace el caso de uso tras perder la carrera): la fila ganadora cambia
    o desaparece entre medias.
    """
    leer_de_verdad = SQLAlchemyFriendshipRepository.find_by_pair
    ya_gano = False

    async def find_by_pair(self, user_id_a, user_id_b):
        nonlocal ya_gano
        if ya_gano and antes_de_releer is not None:
            await sql_en_la_bd_de_test(antes_de_releer)
        encontrada = await leer_de_verdad(self, user_id_a, user_id_b)
        if not ya_gano:
            ya_gano = True
            await sql_en_la_bd_de_test(
                "INSERT INTO friendships (id, requester_id, addressee_id, status, blocked_by, "
                "responded_at, created_at, updated_at) VALUES (:id, :requester_id, "
                ":addressee_id, :status, :blocked_by, NULL, :ahora, :ahora)",
                id=str(uuid.uuid4()),
                requester_id=requester_id,
                addressee_id=addressee_id,
                status=status,
                blocked_by=blocked_by,
                ahora=datetime.now(),
            )
        return encontrada

    monkeypatch.setattr(SQLAlchemyFriendshipRepository, "find_by_pair", find_by_pair)


async def _confirma_la_fila_de_a(id_a: str, id_b: str) -> None:
    """La fila que deja la petición de A que gana: su solicitud, ya confirmada."""
    ahora = datetime.now()
    await sql_en_la_bd_de_test(
        "INSERT INTO friendships (id, requester_id, addressee_id, status, blocked_by, "
        "responded_at, created_at, updated_at) VALUES (:id, :requester_id, "
        ":addressee_id, 'PENDING', NULL, NULL, :ahora, :ahora)",
        id=str(uuid.uuid4()),
        requester_id=id_a,
        addressee_id=id_b,
        ahora=ahora,
    )


async def _filas_de_la_pareja() -> list[tuple]:
    resultado = await sql_en_la_bd_de_test(
        "SELECT requester_id, addressee_id, status, blocked_by FROM friendships"
    )
    return [tuple(fila) for fila in resultado]


class TestSolicitudQuePierdeLaCarrera:
    @pytest.mark.asyncio
    async def test_contra_un_bloqueo_responde_como_si_ya_existiera(
        self, client: AsyncClient, monkeypatch
    ):
        """A1: A bloquea a B mientras B le escribe → 404 (no 500) y el bloqueo se queda."""
        a, b = await _dos_usuarios(client)
        id_a, id_b = a["user"]["id"], b["user"]["id"]
        _gana_a_mitad(
            monkeypatch, requester_id=id_a, addressee_id=id_b, status="BLOCKED", blocked_by=id_a
        )

        set_auth_cookies(client, b["cookies"])
        respuesta = await client.post("/api/v1/friends/requests", json={"addressee_id": id_a})

        assert respuesta.status_code == 404, respuesta.text
        assert await _filas_de_la_pareja() == [(id_a, id_b, "BLOCKED", id_a)]

    @pytest.mark.asyncio
    async def test_contra_la_solicitud_del_otro_responde_que_ya_hay_una(
        self, client: AsyncClient, monkeypatch
    ):
        """A2: A y B se escriben a la vez → B recibe el 409 de «ya hay una solicitud»."""
        a, b = await _dos_usuarios(client)
        id_a, id_b = a["user"]["id"], b["user"]["id"]
        _gana_a_mitad(
            monkeypatch, requester_id=id_a, addressee_id=id_b, status="PENDING", blocked_by=None
        )

        set_auth_cookies(client, b["cookies"])
        respuesta = await client.post("/api/v1/friends/requests", json={"addressee_id": id_a})

        assert respuesta.status_code == 409, respuesta.text
        # El de DuplicateFriendRequestViolation, no otro 409 cualquiera
        assert "already exists" in respuesta.json()["detail"], respuesta.text
        assert await _filas_de_la_pareja() == [(id_a, id_b, "PENDING", None)]

    @pytest.mark.parametrize(
        "antes_de_releer",
        [
            pytest.param("DELETE FROM friendships", id="ya_no_esta"),
            pytest.param(
                "UPDATE friendships SET status = 'DECLINED', responded_at = now()",
                id="rechazada",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_si_al_releer_la_ganadora_ya_no_esta_o_se_rechazo_pide_reintentar(
        self, client: AsyncClient, monkeypatch, antes_de_releer: str
    ):
        """A4: choca en el commit y al releer no hay fila (o es DECLINED) → 409 «try again»."""
        a, b = await _dos_usuarios(client)
        id_a, id_b = a["user"]["id"], b["user"]["id"]
        _gana_a_mitad(
            monkeypatch,
            requester_id=id_a,
            addressee_id=id_b,
            status="PENDING",
            blocked_by=None,
            antes_de_releer=antes_de_releer,
        )

        set_auth_cookies(client, b["cookies"])
        respuesta = await client.post("/api/v1/friends/requests", json={"addressee_id": id_a})

        assert respuesta.status_code == 409, respuesta.text
        # El de InvalidFriendshipStatusViolation, no el de «ya hay una solicitud»
        assert "try again" in respuesta.json()["detail"], respuesta.text
        # La solicitud de B no se ha guardado: lo que quede es solo lo de A
        assert all(fila[0] == id_a for fila in await _filas_de_la_pareja())

    @pytest.mark.asyncio
    async def test_contra_mi_propio_bloqueo_responde_el_403_de_siempre(
        self, client: AsyncClient, monkeypatch
    ):
        """N2: gana el bloqueo que B hace de A → 403, como si ya existiera."""
        a, b = await _dos_usuarios(client)
        id_a, id_b = a["user"]["id"], b["user"]["id"]
        _gana_a_mitad(
            monkeypatch, requester_id=id_b, addressee_id=id_a, status="BLOCKED", blocked_by=id_b
        )

        set_auth_cookies(client, b["cookies"])
        respuesta = await client.post("/api/v1/friends/requests", json={"addressee_id": id_a})

        assert respuesta.status_code == 403, respuesta.text
        assert await _filas_de_la_pareja() == [(id_b, id_a, "BLOCKED", id_b)]


class TestUnChoqueSinTraducirEnElCasoDeUso:
    @pytest.mark.asyncio
    async def test_si_el_choque_de_la_pareja_se_escapa_la_api_responde_409(
        self, client: AsyncClient, monkeypatch
    ):
        """N1: un DuplicateFriendshipViolation que sale del caso de uso → 409, no 500."""
        a, b = await _dos_usuarios(client)

        async def choca(self, user_id_a, user_id_b):
            raise DuplicateFriendshipViolation("concurrently")

        monkeypatch.setattr(SQLAlchemyFriendshipRepository, "find_by_pair", choca)

        set_auth_cookies(client, b["cookies"])
        respuesta = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": a["user"]["id"]}
        )

        assert respuesta.status_code == 409, respuesta.text


class TestLaUnidadDeTrabajoTraduceElChoqueAlConfirmar:
    @pytest.mark.asyncio
    async def test_un_insert_que_choca_en_el_commit_es_el_error_de_dominio(
        self, client: AsyncClient
    ):
        """Sin flush previo, el choque sale en el commit: el mismo error que en flush()."""
        a, b = await _dos_usuarios(client)
        id_a, id_b = a["user"]["id"], b["user"]["id"]
        sesiones = fastapi_app.dependency_overrides[get_db_session]()
        sesion = await anext(sesiones)
        try:
            uow = SQLAlchemySocialUnitOfWork(sesion)
            with pytest.raises(DuplicateFriendshipViolation) as choque:
                async with uow:
                    await uow.friendships.add(
                        Friendship.create(
                            id=FriendshipId.generate(),
                            requester_id=UserId(id_b),
                            addressee_id=UserId(id_a),
                        )
                    )
                    await _confirma_la_fila_de_a(id_a, id_b)
        finally:
            await sesiones.aclose()

        assert await _filas_de_la_pareja() == [(id_a, id_b, "PENDING", None)]
        # El texto no dice qué relación hay: si alguna vez llegara al cliente,
        # no puede delatar un bloqueo que la regla F-09 esconde con un 404
        texto = str(choque.value).lower()
        assert "block" not in texto and "friend" not in texto
