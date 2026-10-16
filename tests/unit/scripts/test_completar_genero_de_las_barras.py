"""
Tests del arranque del comando que completa el género de las barras (#880).

Lo que hace con la base de datos se prueba en su caso de uso; aquí, que registra
el mapeo antes de abrir la sesión, que pasa el dry-run y que un error de una
ronda se nota en el código de salida.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from scripts import completar_genero_de_las_barras as command
from src.modules.competition.application.use_cases.completar_genero_de_las_barras_use_case import (
    ResumenDelCompletado,
    RondaCompletada,
)


class _Session:
    def __init__(self, order):
        self._order = order

    async def __aenter__(self):
        self._order.append("session")
        return object()

    async def __aexit__(self, *_):
        return False


def _ejecutar(resumen, dry_run):
    order = []
    use_case = MagicMock(execute=AsyncMock(return_value=resumen))
    with (
        patch.object(command, "start_all_mappers", side_effect=lambda: order.append("mappers")),
        patch.object(command, "async_session_maker", side_effect=lambda: _Session(order)),
        patch.object(command, "SQLAlchemyCompetitionUnitOfWork"),
        patch.object(command, "SQLAlchemyGolfCourseUnitOfWork"),
        patch.object(command, "SQLAlchemyUnitOfWork"),
        patch.object(command, "CompletarGeneroDeLasBarrasUseCase", return_value=use_case),
    ):
        salida = asyncio.run(command.main(dry_run=dry_run))
    return salida, order, use_case


def test_registra_el_mapeo_antes_de_abrir_la_sesion_y_pasa_el_dry_run():
    salida, order, use_case = _ejecutar(ResumenDelCompletado(), dry_run=True)

    assert order == ["mappers", "session"]
    use_case.execute.assert_awaited_once_with(dry_run=True)
    assert salida == 0


def test_un_error_en_una_ronda_sale_con_1():
    resumen = ResumenDelCompletado(
        rondas=[RondaCompletada("Ryder", "r1", 4)], errores=["Ryder / ronda r2: campo roto"]
    )

    salida, _, _ = _ejecutar(resumen, dry_run=False)

    assert salida == 1
