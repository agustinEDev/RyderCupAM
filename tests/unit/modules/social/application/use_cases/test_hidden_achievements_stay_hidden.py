"""
Lo que se publico oculto sigue oculto al volver a publicarse (fallo del
probador, 23 oct 2026).

Diego apaga «compartir actividad», se cierra el torneo TA y su birdie y su
record salen ocultos. Vuelve a encenderlo, el organizador reabre TA y lo cierra
otra vez: sus amigos los veian. `SetActivitySharingUseCase` dice que volver a
encenderlo «no destapa nada».

La regla: un logro que se vuelve a publicar con la misma identidad (jugador,
tipo y origen) conserva lo oculto; solo uno que no existia toma el interruptor
de ahora. Y apagarlo oculta lo publicado, asi que un logro visible que se vuelve
a publicar con el interruptor apagado sale oculto: visible solo si lo era antes
Y el interruptor esta encendido ahora.

Vale para todas las republicaciones: el cierre del mismo torneo (tras
reabrirlo o sin que la reapertura llegara a borrar), y la herencia de «campo
nuevo» y «primer torneo» por otro torneo o por una partida rapida.
"""

from datetime import timedelta

import pytest

from src.modules.social.application.use_cases.set_activity_sharing_use_case import (
    SetActivitySharingUseCase,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from tests.unit.modules.social.application.use_cases.test_exclusive_dated_achievements import (
    AYER,
    MANANA,
    TARDE,
    Escena,
    _a_las,
    _id,
)
from tests.unit.modules.social.stroke_play_world import DIA, tarjeta

pytestmark = pytest.mark.asyncio

T = ActivityEventType
ANTES = DIA - timedelta(days=30)


async def _diego() -> tuple[Escena, object, object]:
    """
    Diego con un torneo anterior peor (para que TA bata su marca) y TA en juego,
    con un birdie en el 4.
    """
    e = await Escena().montar()
    # El anterior, peor: TA sera su mejor marca
    previo_peor = await e.world.competition(e.ana, enrolled=[e.ana], completed=False, start=ANTES)
    await e.world.group(
        previo_peor, await e.world.round(previo_peor, e.course, ANTES), {e.ana: tarjeta(par=5)}
    )
    await e.cerrar(previo_peor)
    ta = await e.world.competition(e.ana, enrolled=[e.ana], completed=False, start=DIA)
    grupo = await e.world.group(
        ta, await e.world.round(ta, e.course, DIA, MANANA), {e.ana: tarjeta(h4=3)}
    )
    return e, ta, grupo


async def _interruptor(e: Escena, encendido: bool) -> None:
    await SetActivitySharingUseCase(e.world.users, e.social).execute(_id(e.ana), encendido)


async def _de_ta(e: Escena, ta) -> dict:
    """Los logros de TA: tipo -> visible para los amigos."""
    async with e.social:
        eventos = await e.social.activity_events.find_in(
            [ActivitySlice(user_ids=(e.ana.id,), types=frozenset(T))], limit=100
        )
    return {
        x.type: x.visible_to_friends
        for x in eventos
        if x.type.is_achievement and x.payload.get("competition_id") == _id(ta)
    }


async def _lo_ven_sus_amigos(e: Escena) -> set:
    async with e.social:
        eventos = await e.social.activity_events.find_in(
            [ActivitySlice(user_ids=(e.ana.id,), types=frozenset(T), only_visible_to_friends=True)],
            limit=100,
        )
    return {(x.type, x.source_match_id) for x in eventos}


async def _reabrir_y_cerrar(e: Escena, torneo) -> None:
    await e.reabrir(torneo)
    await e.cerrar(torneo)


# ==================== El mismo torneo ====================


class TestTheSameTournamentAgain:
    async def test_a_new_achievement_with_sharing_off_is_hidden(self):
        e, ta, _ = await _diego()
        await _interruptor(e, False)

        await e.cerrar(ta)

        logros = await _de_ta(e, ta)
        assert logros[T.BIRDIE] is False
        assert logros[T.PERSONAL_BEST] is False

    async def test_the_testers_sequence_keeps_them_hidden(self):
        """Apagado, cierra, encendido, reabre y cierra: siguen ocultos."""
        e, ta, grupo = await _diego()
        await _interruptor(e, False)
        await e.cerrar(ta)
        await _interruptor(e, True)

        await _reabrir_y_cerrar(e, ta)

        logros = await _de_ta(e, ta)
        assert logros[T.BIRDIE] is False
        assert logros[T.PERSONAL_BEST] is False
        assert all(origen != _id(grupo) for _, origen in await _lo_ven_sus_amigos(e))

    async def test_they_stay_hidden_after_several_reopenings(self):
        e, ta, _ = await _diego()
        await _interruptor(e, False)
        await e.cerrar(ta)
        await _interruptor(e, True)

        await _reabrir_y_cerrar(e, ta)
        await _reabrir_y_cerrar(e, ta)

        assert set((await _de_ta(e, ta)).values()) == {False}

    async def test_closing_again_without_the_reopening_deleting_keeps_them_hidden(self):
        """La reapertura no llego a borrar: el cierre sustituye sobre lo oculto."""
        e, ta, _ = await _diego()
        await _interruptor(e, False)
        await e.cerrar(ta)
        await _interruptor(e, True)

        await e.torneos().execute(_id(ta))

        logros = await _de_ta(e, ta)
        assert logros[T.BIRDIE] is False
        assert logros[T.PERSONAL_BEST] is False

    async def test_a_visible_one_turning_sharing_off_is_hidden_on_closing_again(self):
        """Decision: apagarlo oculta lo publicado, tambien lo que se vuelve a publicar."""
        e, ta, _ = await _diego()
        await e.cerrar(ta)
        await _interruptor(e, False)

        await _reabrir_y_cerrar(e, ta)

        assert set((await _de_ta(e, ta)).values()) == {False}

    async def test_turning_sharing_off_while_reopened_hides_them_on_closing(self):
        e, ta, _ = await _diego()
        await e.cerrar(ta)
        await e.reabrir(ta)
        await _interruptor(e, False)

        await e.cerrar(ta)

        assert set((await _de_ta(e, ta)).values()) == {False}

    async def test_a_visible_one_stays_visible_on_closing_again(self):
        e, ta, _ = await _diego()
        await e.cerrar(ta)

        await _reabrir_y_cerrar(e, ta)

        logros = await _de_ta(e, ta)
        assert logros[T.BIRDIE] is True
        assert logros[T.PERSONAL_BEST] is True

    async def test_a_new_achievement_on_the_second_close_takes_the_switch_of_now(self):
        """El eagle que no existia sale visible; el birdie que salio oculto, oculto."""
        e, ta, grupo = await _diego()
        await _interruptor(e, False)
        await e.cerrar(ta)
        await _interruptor(e, True)
        await e.reabrir(ta)
        await e.world.group(
            ta,
            await e.world.round(ta, e.course, DIA, TARDE),
            {e.ana: tarjeta(h4=3, h5=2)},
            numero=2,
        )

        await e.cerrar(ta)

        logros = await _de_ta(e, ta)
        assert logros[T.EAGLE_OR_BETTER] is True
        eventos = [x for x in await e.eventos(T.BIRDIE) if x.source_match_id == _id(grupo)]
        assert [x.visible_to_friends for x in eventos] == [False]

    async def test_a_new_achievement_on_the_second_close_with_sharing_off_is_hidden(self):
        e, ta, _ = await _diego()
        await e.cerrar(ta)
        await e.reabrir(ta)
        await _interruptor(e, False)
        await e.world.group(
            ta,
            await e.world.round(ta, e.course, DIA, TARDE),
            {e.ana: tarjeta(h5=2)},
            numero=2,
        )

        await e.cerrar(ta)

        assert (await _de_ta(e, ta))[T.EAGLE_OR_BETTER] is False


# ==================== La herencia de otro ====================


class TestInheritedFromAnotherTournament:
    async def test_a_later_tournament_inherits_its_hidden_exclusives_hidden(self):
        """
        El posterior se cerro oculto; el anterior se los llevo al cerrarse y, al
        reabrirlo, vuelven al posterior: ocultos, aunque ahora este encendido.
        """
        e = await Escena().montar()
        anterior, _ = await e.torneo(AYER, TARDE)
        posterior, grupo = await e.torneo(DIA, MANANA)
        await _interruptor(e, False)
        await e.cerrar(posterior)
        await _interruptor(e, True)
        await e.cerrar(anterior)
        assert await e.de(T.NEW_COURSE) != [_id(grupo)]

        await e.reabrir(anterior)

        for tipo in (T.NEW_COURSE, T.FIRST_TOURNAMENT):
            eventos = await e.eventos(tipo)
            assert [(x.source_match_id, x.visible_to_friends) for x in eventos] == [
                (_id(grupo), False)
            ]

    async def test_a_later_visible_one_inherits_them_visible(self):
        e = await Escena().montar()
        anterior, _ = await e.torneo(AYER, TARDE)
        posterior, grupo = await e.torneo(DIA, MANANA)
        await e.cerrar(posterior)
        await e.cerrar(anterior)

        await e.reabrir(anterior)

        eventos = await e.eventos(T.NEW_COURSE)
        assert [(x.source_match_id, x.visible_to_friends) for x in eventos] == [(_id(grupo), True)]

    async def test_a_quick_match_inherits_its_hidden_new_course_hidden(self):
        e = await Escena().montar()
        anterior, _ = await e.torneo(AYER, TARDE)
        partida = await e.rapida(_a_las(DIA, 9))
        await _interruptor(e, False)
        await e.publicar_rapida(partida)
        await _interruptor(e, True)
        await e.cerrar(anterior)
        assert await e.de(T.NEW_COURSE) != [_id(partida)]

        await e.reabrir(anterior)

        eventos = await e.eventos(T.NEW_COURSE)
        assert [(x.source_match_id, x.visible_to_friends) for x in eventos] == [
            (_id(partida), False)
        ]
