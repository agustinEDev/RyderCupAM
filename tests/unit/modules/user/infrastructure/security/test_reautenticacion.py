"""
La marca de reautenticación se gasta de una vez (BE #753, /code-review): comprobarla y
gastarla eran dos pasos, y dos vínculos a la vez pasaban los dos.
"""

from datetime import timedelta

from src.modules.user.infrastructure.security import reautenticacion

USUARIO = "00000000-0000-0000-0000-0000000000aa"


def test_a_mark_is_spent_only_once():
    marca = reautenticacion.emite(USUARIO)

    assert reautenticacion.gasta_si_vale(marca, USUARIO) is True
    assert reautenticacion.gasta_si_vale(marca, USUARIO) is False


def test_another_users_or_an_expired_mark_is_not_spent():
    ajena = reautenticacion.emite("00000000-0000-0000-0000-0000000000bb")
    caducada = reautenticacion.emite(USUARIO, dura=timedelta(seconds=-1))

    assert reautenticacion.gasta_si_vale(ajena, USUARIO) is False
    assert reautenticacion.gasta_si_vale(caducada, USUARIO) is False
    assert reautenticacion.gasta_si_vale(None, USUARIO) is False
