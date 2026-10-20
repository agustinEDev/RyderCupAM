"""
Lo que es solo de la Ryder Cup, en su propia pieza (RyderCupAM#251).

Decidido el 1 oct 2026: lo común a las dos modalidades se comparte y lo que es
de una sola va aparte. Equipos, modo de montaje, reparto y capitanes son de la
Ryder Cup. La pieza se guarda en las mismas columnas de `competitions` y es
inmutable: cada cambio devuelve una pieza nueva, porque SQLAlchemy no ve un
cambio hecho dentro de un composite y lo perdería sin avisar.
"""

from dataclasses import FrozenInstanceError

import pytest

from src.modules.competition.domain.value_objects.ryder_cup_setup import RyderCupSetup
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.user.domain.value_objects.user_id import UserId


def _pieza(**extra) -> RyderCupSetup:
    return RyderCupSetup.create(team_1_name="Europa", team_2_name="América", **extra)


class TestSeCreaComoHoy:
    def test_estilo_ryder_y_reparto_manual_por_defecto(self):
        pieza = _pieza()

        assert pieza.setup_mode == SetupMode.RYDER_CUP
        assert pieza.team_assignment == TeamAssignment.MANUAL

    def test_el_modo_automatico_reparte_solo(self):
        assert _pieza(setup_mode=SetupMode.AUTOMATIC).team_assignment == TeamAssignment.AUTOMATIC

    def test_nace_sin_capitanes(self):
        pieza = _pieza()

        assert pieza.team_a_captain_id is None
        assert pieza.team_b_captain_id is None
        assert pieza.team_a_vice_captain_id is None
        assert pieza.team_b_vice_captain_id is None

    @pytest.mark.parametrize(
        ("equipo_1", "equipo_2"),
        [("", "América"), ("Europa", "  "), (None, "América"), ("Europa", " europa ")],
    )
    def test_nombres_invalidos(self, equipo_1, equipo_2):
        with pytest.raises(ValueError):
            RyderCupSetup.create(team_1_name=equipo_1, team_2_name=equipo_2)


class TestEsInmutable:
    def test_no_se_cambia_por_dentro(self):
        """Un cambio por dentro se perdería en la base sin avisar: aquí, explota."""
        with pytest.raises(FrozenInstanceError):
            _pieza().team_1_name = "Otro"  # type: ignore[misc]

    def test_cada_cambio_es_una_pieza_nueva(self):
        original = _pieza()
        a, b = UserId.generate(), UserId.generate()

        cambiada = original.with_captains(a, b)

        assert (cambiada.team_a_captain_id, cambiada.team_b_captain_id) == (a, b)
        assert original.team_a_captain_id is None


class TestNombresDeEquipo:
    def test_se_cambia_uno_solo(self):
        assert _pieza().with_team_names("Ryder", None).team_1_name == "Ryder"

    def test_no_pueden_quedar_iguales(self):
        """La regla es de los dos: cambiar uno se mira contra el otro."""
        with pytest.raises(ValueError):
            _pieza().with_team_names(None, "EUROPA")

    def test_cambiar_el_modo_cambia_el_reparto(self):
        pieza = _pieza().with_setup_mode(SetupMode.AUTOMATIC)

        assert pieza.setup_mode == SetupMode.AUTOMATIC
        assert pieza.team_assignment == TeamAssignment.AUTOMATIC


class TestCapitanes:
    def test_captain_y_vice_captain_por_equipo(self):
        a, b, va = UserId.generate(), UserId.generate(), UserId.generate()
        pieza = _pieza().with_captains(a, b).with_vice_captain("A", va)

        assert pieza.captain("A") == a
        assert pieza.captain("B") == b
        assert pieza.vice_captain("A") == va
        assert pieza.is_captain_of("A", a)
        assert not pieza.is_captain_of("B", a)

    def test_solo_hay_equipos_a_y_b(self):
        with pytest.raises(ValueError):
            _pieza().captain("C")

    def test_cubrir_un_capitan_le_quita_el_puesto_de_subcapitan(self):
        a, b, nuevo = UserId.generate(), UserId.generate(), UserId.generate()
        pieza = _pieza().with_captains(a, b).with_vice_captain("A", nuevo)

        cubierta = pieza.with_captain("A", nuevo)

        assert cubierta.captain("A") == nuevo
        assert cubierta.vice_captain("A") is None

    def test_sin_subcapitanes_tras_repartir(self):
        a, b = UserId.generate(), UserId.generate()
        pieza = _pieza().with_vice_captain("A", a).with_vice_captain("B", b)

        assert pieza.without_vice_captains().vice_captain("A") is None
        assert pieza.without_vice_captains().vice_captain("B") is None


class TestBajas:
    def test_se_va_un_capitan_y_asciende_su_subcapitan(self):
        a, b, va = UserId.generate(), UserId.generate(), UserId.generate()
        pieza = _pieza().with_captains(a, b).with_vice_captain("A", va)

        despues = pieza.after_withdrawal(a)

        assert despues is not None
        assert despues.captain("A") == va
        assert despues.vice_captain("A") is None

    def test_se_va_un_subcapitan_y_queda_libre(self):
        a, b, vb = UserId.generate(), UserId.generate(), UserId.generate()
        pieza = _pieza().with_captains(a, b).with_vice_captain("B", vb)

        despues = pieza.after_withdrawal(vb)

        assert despues is not None
        assert despues.vice_captain("B") is None
        assert despues.captain("B") == b

    def test_se_va_alguien_que_no_era_nada(self):
        """None: no cambió nada, y la entidad no toca su fecha de actualización."""
        assert _pieza().after_withdrawal(UserId.generate()) is None


class TestRepartoDeEquipos:
    def test_sin_capitanes_es_el_reparto_de_siempre(self):
        assert _pieza().captains_for_team_split() is None

    def test_con_un_solo_capitan_no_se_reparte(self):
        from src.modules.competition.domain.value_objects.ryder_cup_setup import CaptainMissingError

        pieza = _pieza().with_captains(UserId.generate(), UserId.generate())
        cojo = pieza.after_withdrawal(pieza.team_a_captain_id)

        assert cojo is not None
        with pytest.raises(CaptainMissingError):
            cojo.captains_for_team_split()


class TestEnColumnas:
    def test_ida_y_vuelta(self):
        """Lo que guarda SQLAlchemy y lo que lee tienen que ser la misma pieza."""
        a, b, va = UserId.generate(), UserId.generate(), UserId.generate()
        pieza = (
            _pieza(setup_mode=SetupMode.AUTOMATIC).with_captains(a, b).with_vice_captain("A", va)
        )

        assert RyderCupSetup.from_columns(*pieza.__composite_values__()) == pieza

    def test_todas_las_columnas_a_nulo_es_que_no_hay_pieza(self):
        assert RyderCupSetup.from_columns(*([None] * 8)) is None

    def test_con_un_solo_nombre_se_lee_igual(self):
        """
        Hoy no puede pasar (las dos columnas son NOT NULL), pero si pasara, leer
        no tira la pieza: perder los capitanes de un torneo al cargarlo es peor
        que un nombre vacío.
        """
        capitan = UserId.generate()

        pieza = RyderCupSetup.from_columns(
            "Europa", None, "RYDER_CUP", "MANUAL", capitan, None, None, None
        )

        assert pieza is not None
        assert pieza.team_a_captain_id == capitan
