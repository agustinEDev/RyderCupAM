"""
El aviso de horario en Actividad: `TEE_TIME_ASSIGNED` (G, tabla del 22 oct 2026).

| #   | Caso                                              | Resultado                                |
|-----|---------------------------------------------------|------------------------------------------|
| G1  | Salida de stroke play                             | Aviso con torneo, ronda, dia, sesion,    |
|     |                                                   | hora «HH:MM» y compañeros                |
| G2  | Partido de Ryder                                  | Sin hora, con compañero, rivales y       |
|     |                                                   | `match_id`                               |
| G3  | Cambia                                            | El viejo de esa ronda se va, uno nuevo   |
|     |                                                   | con `changed`; los de otros, intactos.   |
|     |                                                   | Se compara con lo guardado y se relee la |
|     |                                                   | ronda con candado: el orden no importa   |
| G3  | Sale de la ronda                                  | Pierde el suyo, solo el de esa ronda     |
| G6  | Solo Actividad, solo para el                      | Sus amigos no lo ven                     |
| G7  | Lleva al torneo                                   | `competition_id` en el payload           |
| G9  | Se retira / se cancela / se borra el torneo       | Se va                                    |
| G9  | El torneo pasa a privado                          | Se queda: es suyo                        |
| G10 | Uno por (jugador, ronda)                          | Origen = la ronda                        |
| G11 | Compañero que me bloqueo                          | Sin nombre en el feed                    |
|     | Un lote                                           | Una lectura de usuarios y una escritura  |
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
    TeeTimeRef,
    TournamentRef,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

T = ActivityEventType
SABADO = date(2026, 10, 25)


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def avisos(social_uow, user_uow):
    return PublishCompetitionNoticesUseCase(social_uow, user_uow)


def _torneo(competition_id: str | None = None, is_public: bool = True) -> TournamentRef:
    return TournamentRef(
        competition_id=competition_id or str(uuid4()),
        name="Medal de otoño",
        start_date=SABADO,
        end_date=date(2026, 10, 26),
        is_public=is_public,
    )


async def _user(user_uow, nombre: str = "Pedro") -> User:
    user = User.create(
        first_name=nombre,
        last_name="Lopez",
        email_str=f"salida_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


def _salida(
    user: User,
    hora: str | None = "09:10",
    con=(),
    contra=(),
    partido: str | None = None,
    sesion: str = "MORNING",
    fuera: bool = False,
) -> TeeTimeRef:
    return TeeTimeRef(
        user_id=user.id,
        round_date=SABADO,
        session_type=sesion,
        tee_time=hora,
        partner_ids=tuple(u.id for u in con),
        opponent_ids=tuple(u.id for u in contra),
        match_id=partido,
        out_of_play=fuera,
    )


def _con_candado_espiado(social_uow, monkeypatch) -> list:
    """Apunta cada candado que se toma, en orden."""
    orden: list = []
    bloquear = social_uow.activity_events.lock_scope

    async def _bloquea(clave):
        orden.append(("candado", clave))
        return await bloquear(clave)

    monkeypatch.setattr(social_uow.activity_events, "lock_scope", _bloquea)
    return orden


def _vigentes(*salidas: TeeTimeRef):
    """Lo que hay ahora en la ronda, como lo releeria la publicacion."""

    async def _leer():
        return list(salidas)

    return _leer


async def _guardados(social_uow, user: User):
    async with social_uow:
        return await social_uow.activity_events.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], limit=100
        )


async def _feed(social_uow, user_uow, viewer: User):
    return await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(viewer.id.value))


async def _amistad(social_uow, a: User, b: User, bloqueo: bool = False) -> None:
    amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    if bloqueo:
        amistad.block(a.id)
    else:
        amistad.accept()
    async with social_uow:
        await social_uow.friendships.add(amistad)


class TestG1yG2:
    async def test_g1_stroke_play_payload(self, avisos, social_uow, user_uow):
        yo, pedro, juan = [await _user(user_uow) for _ in range(3)]
        torneo = _torneo()
        ronda = str(uuid4())

        await avisos.tee_times(torneo, ronda, _vigentes(_salida(yo, con=[pedro, juan])))

        (evento,) = await _guardados(social_uow, yo)
        assert evento.type == T.TEE_TIME_ASSIGNED
        assert evento.source_match_id == ronda
        assert evento.payload == {
            "competition_id": torneo.competition_id,
            "competition_name": "Medal de otoño",
            "start_date": "2026-10-25",
            "end_date": "2026-10-26",
            "round_id": ronda,
            "round_date": "2026-10-25",
            "session_type": "MORNING",
            "kind": "TEE_GROUP",
            "tee_time": "09:10",
            "partner_ids": [str(pedro.id.value), str(juan.id.value)],
            "opponent_ids": [],
            "match_id": None,
            "changed": False,
        }

    async def test_g2_ryder_payload(self, avisos, social_uow, user_uow):
        yo, pedro, juan, luis = [await _user(user_uow) for _ in range(4)]
        ronda = str(uuid4())
        partido = str(uuid4())

        await avisos.tee_times(
            _torneo(),
            ronda,
            _vigentes(_salida(yo, hora=None, con=[pedro], contra=[juan, luis], partido=partido)),
        )

        (evento,) = await _guardados(social_uow, yo)
        assert evento.payload["kind"] == "MATCH"
        assert evento.payload["tee_time"] is None
        assert evento.payload["match_id"] == partido
        assert evento.payload["partner_ids"] == [str(pedro.id.value)]
        assert evento.payload["opponent_ids"] == [str(juan.id.value), str(luis.id.value)]

    async def test_every_player_of_the_batch_gets_its_own(self, avisos, social_uow, user_uow):
        a, b = [await _user(user_uow) for _ in range(2)]

        await avisos.tee_times(
            _torneo(), str(uuid4()), _vigentes(_salida(a, con=[b]), _salida(b, con=[a]))
        )

        (de_a,) = await _guardados(social_uow, a)
        (de_b,) = await _guardados(social_uow, b)
        assert de_a.payload["partner_ids"] == [str(b.id.value)]
        assert de_b.payload["partner_ids"] == [str(a.id.value)]

    async def test_no_user_read_and_one_write_per_batch(
        self, avisos, social_uow, user_uow, monkeypatch
    ):
        """
        Sin leer usuarios: es solo suyo (SELF) y el interruptor de publicar solo
        decide lo que ven los amigos. Leerlos abriria otra transaccion y soltaria
        el candado de la ronda antes de escribir.
        """
        jugadores = [await _user(user_uow) for _ in range(4)]
        lecturas, escrituras = [], []
        leer = user_uow.users.find_by_ids
        escribir = social_uow.activity_events.add_many

        async def _lee(ids):
            lecturas.append(ids)
            return await leer(ids)

        async def _escribe(eventos):
            escrituras.append(eventos)
            return await escribir(eventos)

        monkeypatch.setattr(user_uow.users, "find_by_ids", _lee)
        monkeypatch.setattr(social_uow.activity_events, "add_many", _escribe)

        await avisos.tee_times(_torneo(), str(uuid4()), _vigentes(*[_salida(j) for j in jugadores]))

        assert lecturas == []
        assert len(escrituras) == 1
        assert len(escrituras[0]) == 4


class TestG3Cambios:
    """La publicacion reconcilia lo guardado con lo que hay ahora en la ronda."""

    async def test_a_change_replaces_the_notice_of_that_round_only(
        self, avisos, social_uow, user_uow
    ):
        yo, otro = [await _user(user_uow) for _ in range(2)]
        torneo = _torneo()
        ronda, otra_ronda = str(uuid4()), str(uuid4())
        await avisos.tee_times(torneo, ronda, _vigentes(_salida(yo), _salida(otro)))
        await avisos.tee_times(torneo, otra_ronda, _vigentes(_salida(yo, hora="15:00")))
        (del_otro_antes,) = await _guardados(social_uow, otro)

        await avisos.tee_times(torneo, ronda, _vigentes(_salida(yo, hora="09:20"), _salida(otro)))

        mios = {e.source_match_id: e.payload for e in await _guardados(social_uow, yo)}
        assert set(mios) == {ronda, otra_ronda}
        assert (mios[ronda]["tee_time"], mios[ronda]["changed"]) == ("09:20", True)
        assert mios[otra_ronda]["tee_time"] == "15:00"
        (del_otro,) = await _guardados(social_uow, otro)
        assert del_otro.id == del_otro_antes.id
        assert (del_otro.payload["tee_time"], del_otro.payload["changed"]) == ("09:10", False)

    async def test_a_change_is_a_new_notice(self, avisos, social_uow, user_uow):
        """Sale de nuevo: otra id y otra fecha de publicacion, para que cuente como novedad."""
        yo = await _user(user_uow)
        ronda = str(uuid4())
        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo)))
        (viejo,) = await _guardados(social_uow, yo)

        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo, hora="10:00")))

        (nuevo,) = await _guardados(social_uow, yo)
        assert nuevo.id != viejo.id

    @pytest.mark.parametrize(
        "cambio",
        [
            {"hora": "09:20"},
            {"con": "otro"},
            {"contra": "otro"},
            {"sesion": "AFTERNOON"},
        ],
    )
    async def test_what_counts_as_a_change(self, avisos, social_uow, user_uow, cambio):
        yo, pedro, otro = [await _user(user_uow) for _ in range(3)]
        ronda = str(uuid4())
        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo, con=[pedro])))
        argumentos = {"con": [pedro], **cambio}
        for clave in ("con", "contra"):
            if argumentos.get(clave) == "otro":
                argumentos[clave] = [otro]

        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo, **argumentos)))

        (evento,) = await _guardados(social_uow, yo)
        assert evento.payload["changed"] is True

    async def test_the_same_partners_in_another_order_or_another_match_id_is_no_change(
        self, avisos, social_uow, user_uow
    ):
        yo, a, b = [await _user(user_uow) for _ in range(3)]
        ronda = str(uuid4())
        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo, con=[a, b], partido="m1")))
        (antes,) = await _guardados(social_uow, yo)

        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo, con=[b, a], partido="m2")))

        (despues,) = await _guardados(social_uow, yo)
        assert despues.id == antes.id

    async def test_leaving_the_round_withdraws_only_his_notice_of_that_round(
        self, avisos, social_uow, user_uow
    ):
        yo, otro = [await _user(user_uow) for _ in range(2)]
        torneo = _torneo()
        ronda, otra_ronda = str(uuid4()), str(uuid4())
        await avisos.tee_times(torneo, ronda, _vigentes(_salida(yo), _salida(otro)))
        await avisos.tee_times(torneo, otra_ronda, _vigentes(_salida(yo)))

        await avisos.tee_times(torneo, ronda, _vigentes(_salida(otro)))

        assert [e.source_match_id for e in await _guardados(social_uow, yo)] == [otra_ronda]
        assert len(await _guardados(social_uow, otro)) == 1

    async def test_publishing_twice_the_same_round_changes_nothing(
        self, avisos, social_uow, user_uow
    ):
        """
        G3. Dos publicaciones de la misma ronda en cualquier orden releen lo que
        hay: la segunda no tiene nada que hacer, aunque su foto fuera vieja.
        """
        yo = await _user(user_uow)
        ronda = str(uuid4())
        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo, hora="09:20")))
        (antes,) = await _guardados(social_uow, yo)

        await avisos.tee_times(_torneo(), ronda, _vigentes(_salida(yo, hora="09:20")))

        (despues,) = await _guardados(social_uow, yo)
        assert despues.id == antes.id

    async def test_the_tournament_is_locked_before_the_round_is_read(
        self, avisos, social_uow, user_uow, monkeypatch
    ):
        """
        G3. Leer la ronda con el candado puesto: si no, dos publicaciones se
        cruzan. El candado es del torneo, el mismo que toman la baja y la
        cancelacion al borrar (revision final del 22 oct).
        """
        yo = await _user(user_uow)
        orden = _con_candado_espiado(social_uow, monkeypatch)
        leer = _vigentes(_salida(yo))

        async def _lee():
            orden.append(("leer", None))
            return await leer()

        torneo = _torneo()
        await avisos.tee_times(torneo, str(uuid4()), _lee)

        assert orden == [("candado", torneo.competition_id), ("leer", None)]

    async def test_out_of_play_keeps_his_notice_and_never_gets_a_new_one(
        self, avisos, social_uow, user_uow
    ):
        """
        Revision final: un no presentado o un retirado sigue en el grupo, fuera
        de juego. Su aviso no se toca, ni se le crea uno, ni se le quita.
        """
        yo, falta, nuevo = [await _user(user_uow) for _ in range(3)]
        torneo, ronda = _torneo(), str(uuid4())
        await avisos.tee_times(
            torneo, ronda, _vigentes(_salida(yo, con=[falta]), _salida(falta, con=[yo]))
        )
        (de_falta,) = await _guardados(social_uow, falta)

        await avisos.tee_times(
            torneo,
            ronda,
            _vigentes(
                _salida(yo, con=[falta]),
                _salida(falta, con=[yo, nuevo], fuera=True),
                _salida(nuevo, hora="10:00", fuera=True),
            ),
        )

        (sigue,) = await _guardados(social_uow, falta)
        assert sigue.id == de_falta.id
        assert await _guardados(social_uow, nuevo) == []

    async def test_an_empty_round_without_notices_touches_nothing(
        self, avisos, social_uow, user_uow
    ):
        yo = await _user(user_uow)
        await avisos.tee_times(_torneo(), str(uuid4()), _vigentes(_salida(yo)))

        await avisos.tee_times(_torneo(), str(uuid4()), _vigentes())

        assert len(await _guardados(social_uow, yo)) == 1


class TestReassigningInTwoSteps:
    """
    Prueba de punta a punta del 22 oct: reasignar rivales de la Ryder son dos
    `PUT matches/{id}/players`. Entre los dos, quien se queda sin partido pierde
    su aviso; en el segundo le vuelve a nacer uno, y debe decir «te han
    cambiado» (`changed: true`), no «ya tienes partido». Si su aviso se fue por
    una baja o una cancelacion, el nuevo es nuevo de verdad.
    """

    async def _dos_partidos(self, avisos, user_uow):
        """A contra B en m1 y C contra D en m2, publicados."""
        a, b, c, d = [await _user(user_uow, n) for n in ("Ana", "Bea", "Cris", "Dani")]
        torneo, ronda = _torneo(), str(uuid4())
        await avisos.tee_times(
            torneo,
            ronda,
            _vigentes(
                _salida(a, None, contra=[b], partido="m1"),
                _salida(b, None, contra=[a], partido="m1"),
                _salida(c, None, contra=[d], partido="m2"),
                _salida(d, None, contra=[c], partido="m2"),
            ),
        )
        return a, b, c, d, torneo, ronda

    @staticmethod
    def _cruzados(a, b, c, d, *, con_b: bool = True):
        """Segundo paso: A contra D en m1 y C contra B en m2 (sin B, el primer paso)."""
        salidas = [
            _salida(a, None, contra=[d], partido="m1b"),
            _salida(d, None, contra=[a], partido="m1b"),
            _salida(c, None, contra=[b] if con_b else [d], partido="m2b"),
        ]
        if con_b:
            salidas.append(_salida(b, None, contra=[c], partido="m2b"))
        return _vigentes(*salidas)

    async def test_who_was_left_without_a_match_gets_it_back_as_changed(
        self, avisos, social_uow, user_uow
    ):
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)

        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d, con_b=False))
        assert await _guardados(social_uow, b) == []
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d))

        (de_b,) = await _guardados(social_uow, b)
        assert de_b.payload["changed"] is True
        assert de_b.payload["opponent_ids"] == [str(c.id.value)]

    async def test_in_one_step_everybody_changed_is_changed(self, avisos, social_uow, user_uow):
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)

        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d))

        for jugador in (a, b, c, d):
            (evento,) = await _guardados(social_uow, jugador)
            assert evento.payload["changed"] is True

    async def test_a_newcomer_to_the_round_is_not_changed(self, avisos, social_uow, user_uow):
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d, con_b=False))
        nuevo = await _user(user_uow, "Eva")

        await avisos.tee_times(
            torneo,
            ronda,
            _vigentes(
                _salida(a, None, contra=[d], partido="m1b"),
                _salida(d, None, contra=[a], partido="m1b"),
                _salida(c, None, contra=[nuevo], partido="m2b"),
                _salida(nuevo, None, contra=[c], partido="m2b"),
            ),
        )

        (del_nuevo,) = await _guardados(social_uow, nuevo)
        assert del_nuevo.payload["changed"] is False

    async def test_it_is_remembered_only_for_that_round(self, avisos, social_uow, user_uow):
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d, con_b=False))

        otra_ronda = str(uuid4())
        await avisos.tee_times(torneo, otra_ronda, _vigentes(_salida(b, None, partido="m9")))

        (de_b,) = await _guardados(social_uow, b)
        assert de_b.payload["changed"] is False

    async def test_once_back_it_is_forgotten(self, avisos, social_uow, user_uow):
        """Vuelve con `changed`; si luego se queda igual, nada cambia ni se repite."""
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d, con_b=False))
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d))
        (antes,) = await _guardados(social_uow, b)

        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d))

        (despues,) = await _guardados(social_uow, b)
        assert despues.id == antes.id
        async with social_uow:
            assert await social_uow.activity_events.withdrawn_tee_times(ronda) == set()

    @pytest.mark.parametrize(
        "limpiar",
        [
            lambda avisos, b, torneo: avisos.left(b.id, torneo.competition_id),
            lambda avisos, b, torneo: avisos.tournament_cancelled(torneo.competition_id),
            lambda avisos, b, torneo: avisos.tournament_deleted(torneo.competition_id),
        ],
        ids=["baja", "cancelado", "borrado"],
    )
    async def test_after_leaving_or_cancelling_the_next_one_is_new(
        self, avisos, social_uow, user_uow, limpiar
    ):
        """Su aviso se fue por la baja o la cancelacion, no por un cambio."""
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d, con_b=False))

        await limpiar(avisos, b, torneo)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d))

        (de_b,) = await _guardados(social_uow, b)
        assert de_b.payload["changed"] is False

    async def test_leaving_forgets_only_his_own(self, avisos, social_uow, user_uow):
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)
        # Sin B ni C: los dos se quedan sin partido
        await avisos.tee_times(
            torneo,
            ronda,
            _vigentes(
                _salida(a, None, contra=[d], partido="m1b"),
                _salida(d, None, contra=[a], partido="m1b"),
            ),
        )

        await avisos.left(b.id, torneo.competition_id)

        async with social_uow:
            assert await social_uow.activity_events.withdrawn_tee_times(ronda) == {c.id}

    async def test_cancelling_another_tournament_does_not_forget_it(
        self, avisos, social_uow, user_uow
    ):
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d, con_b=False))

        await avisos.tournament_cancelled(_torneo().competition_id)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d))

        (de_b,) = await _guardados(social_uow, b)
        assert de_b.payload["changed"] is True

    async def test_deleting_the_round_forgets_only_that_round(
        self, avisos, social_uow, user_uow, monkeypatch
    ):
        """Revisor sin contexto: borrar la ronda no deja anotaciones huerfanas."""
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)
        await avisos.tee_times(torneo, ronda, self._cruzados(a, b, c, d, con_b=False))
        otra = str(uuid4())
        await avisos.tee_times(torneo, otra, _vigentes(_salida(b, None, partido="m9")))
        await avisos.tee_times(torneo, otra, _vigentes())
        orden = _con_candado_espiado(social_uow, monkeypatch)

        await avisos.round_deleted(torneo.competition_id, ronda)

        assert orden[0] == ("candado", torneo.competition_id)
        async with social_uow:
            assert await social_uow.activity_events.withdrawn_tee_times(ronda) == set()
            assert await social_uow.activity_events.withdrawn_tee_times(otra) == {b.id}
        # Y sus avisos de salida, si quedaba alguno, se van con ella
        for jugador in (a, c, d):
            assert [
                e for e in await _guardados(social_uow, jugador) if e.source_match_id == ronda
            ] == []
        assert [e.source_match_id for e in await _guardados(social_uow, b)] == []

    async def test_out_of_play_is_not_remembered(self, avisos, social_uow, user_uow):
        """El no presentado conserva su aviso: no se ha quedado sin partido."""
        a, b, c, d, torneo, ronda = await self._dos_partidos(avisos, user_uow)

        await avisos.tee_times(
            torneo,
            ronda,
            _vigentes(
                _salida(a, None, contra=[b], partido="m1"),
                _salida(b, None, contra=[a], partido="m1", fuera=True),
                _salida(c, None, contra=[d], partido="m2"),
                _salida(d, None, contra=[c], partido="m2"),
            ),
        )

        async with social_uow:
            assert await social_uow.activity_events.withdrawn_tee_times(ronda) == set()


class TestG6G7yG11:
    async def test_g6_only_for_him_his_friends_do_not_see_it(self, avisos, social_uow, user_uow):
        yo, amigo = [await _user(user_uow) for _ in range(2)]
        await _amistad(social_uow, yo, amigo)
        torneo = _torneo()

        await avisos.tee_times(torneo, str(uuid4()), _vigentes(_salida(yo)))

        assert (await _feed(social_uow, user_uow, amigo)).events == []
        (propio,) = (await _feed(social_uow, user_uow, yo)).events
        assert propio.type == "TEE_TIME_ASSIGNED"
        assert propio.payload["competition_id"] == torneo.competition_id

    async def test_g11_a_partner_with_a_block_is_not_named(self, avisos, social_uow, user_uow):
        yo = await _user(user_uow, "Yo")
        pedro = await _user(user_uow, "Pedro")
        bloqueado = await _user(user_uow, "Juan")
        await _amistad(social_uow, bloqueado, yo, bloqueo=True)

        await avisos.tee_times(
            _torneo(), str(uuid4()), _vigentes(_salida(yo, con=[pedro], contra=[bloqueado]))
        )

        feed = await _feed(social_uow, user_uow, yo)
        assert str(pedro.id.value) in feed.authors
        assert str(bloqueado.id.value) not in feed.authors


class TestG9Limpieza:
    @pytest.mark.parametrize(
        "limpiar",
        [
            lambda avisos, yo, torneo: avisos.left(yo.id, torneo.competition_id),
            lambda avisos, yo, torneo: avisos.tournament_cancelled(torneo.competition_id),
            lambda avisos, yo, torneo: avisos.tournament_deleted(torneo.competition_id),
        ],
        ids=["baja", "cancelado", "borrado"],
    )
    async def test_cleaning_takes_the_tournament_lock_first(
        self, avisos, social_uow, user_uow, monkeypatch, limpiar
    ):
        """
        Revision final: el borrado va en fila con las publicaciones del torneo;
        si no, una publicacion que leyo antes de la baja podria escribir
        despues de ella.
        """
        yo = await _user(user_uow)
        torneo = _torneo()
        await avisos.tee_times(torneo, str(uuid4()), _vigentes(_salida(yo)))
        orden = _con_candado_espiado(social_uow, monkeypatch)
        borrar_de = social_uow.activity_events.delete_for_competition

        async def _borra(*args, **kwargs):
            orden.append(("borrar", None))
            return await borrar_de(*args, **kwargs)

        monkeypatch.setattr(social_uow.activity_events, "delete_for_competition", _borra)

        await limpiar(avisos, yo, torneo)

        assert orden[0] == ("candado", torneo.competition_id)
        assert ("borrar", None) in orden

    async def test_withdrawing_from_the_tournament_takes_his_notices(
        self, avisos, social_uow, user_uow
    ):
        yo, otro = [await _user(user_uow) for _ in range(2)]
        torneo, otro_torneo = _torneo(), _torneo()
        await avisos.tee_times(torneo, str(uuid4()), _vigentes(_salida(yo), _salida(otro)))
        await avisos.tee_times(torneo, str(uuid4()), _vigentes(_salida(yo)))
        await avisos.tee_times(otro_torneo, str(uuid4()), _vigentes(_salida(yo)))

        await avisos.left(yo.id, torneo.competition_id)

        assert [e.payload["competition_id"] for e in await _guardados(social_uow, yo)] == [
            otro_torneo.competition_id
        ]
        assert len(await _guardados(social_uow, otro)) == 1

    async def test_cancelling_takes_everyones(self, avisos, social_uow, user_uow):
        yo, otro = [await _user(user_uow) for _ in range(2)]
        torneo, otro_torneo = _torneo(), _torneo()
        await avisos.tee_times(torneo, str(uuid4()), _vigentes(_salida(yo), _salida(otro)))
        await avisos.tee_times(otro_torneo, str(uuid4()), _vigentes(_salida(yo)))

        await avisos.tournament_cancelled(torneo.competition_id)

        assert [e.payload["competition_id"] for e in await _guardados(social_uow, yo)] == [
            otro_torneo.competition_id
        ]
        assert await _guardados(social_uow, otro) == []

    async def test_deleting_takes_everyones(self, avisos, social_uow, user_uow):
        yo = await _user(user_uow)
        torneo, otro_torneo = _torneo(), _torneo()
        await avisos.tee_times(torneo, str(uuid4()), _vigentes(_salida(yo)))
        await avisos.tee_times(otro_torneo, str(uuid4()), _vigentes(_salida(yo)))

        await avisos.tournament_deleted(torneo.competition_id)

        assert [e.payload["competition_id"] for e in await _guardados(social_uow, yo)] == [
            otro_torneo.competition_id
        ]

    async def test_made_private_keeps_it(self, avisos, social_uow, user_uow):
        yo = await _user(user_uow)
        torneo = _torneo()
        await avisos.tee_times(torneo, str(uuid4()), _vigentes(_salida(yo)))

        await avisos.tournament_made_private(torneo.competition_id)

        assert [e.type for e in await _guardados(social_uow, yo)] == [T.TEE_TIME_ASSIGNED]
