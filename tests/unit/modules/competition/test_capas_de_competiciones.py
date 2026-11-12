"""
Competiciones sin ciclos de importación entre sus subpaquetes (hallazgo B10, fase 5).

Cuatro ciclos venían de unas pocas importaciones hacia atrás: el `EnvelopeDesk` importaba el
caso de uso que genera los partidos solo para anotar un tipo; tres entidades usaban reglas
puras que vivían en `domain/services`, junto a servicios que importan entidades; y el objeto
de valor `BolasFuera` importaba la entidad `HoleScore` para anotar un parámetro. Ahora los
tipos son `Protocol` y las reglas puras viven en `domain/policies` (C1, C3-C5). El orden de
las capas (C2) lo fijan dos contratos de `.importlinter` que comprueba `lint-imports` en el CI.
"""

import importlib
import itertools

import grimp
import pytest

COMPETICIONES = "src.modules.competition"


def test_c1_ningun_par_de_subpaquetes_de_competiciones_se_importa_en_ciclo():
    """Given el grafo de importaciones, When se cruzan los subpaquetes de competition, Then ningún par está en ciclo."""
    # Sin caché: con ella, un cambio hecho en el mismo segundo puede leerse con el grafo viejo
    grafo = grimp.build_graph("src", include_external_packages=False, cache_dir=None)
    paquetes = sorted(
        {
            ".".join(m.split(".")[:5])
            for m in grafo.modules
            if m.startswith(COMPETICIONES + ".") and len(m.split(".")) >= 5
        }
    )
    ciclos = [
        (a, b)
        for a, b in itertools.combinations(paquetes, 2)
        if grafo.find_shortest_chain(importer=a, imported=b, as_packages=True)
        and grafo.find_shortest_chain(importer=b, imported=a, as_packages=True)
    ]
    assert ciclos == []


def test_c3_el_caso_de_uso_que_genera_los_partidos_cumple_lo_que_pide_el_envelope_desk():
    """Given el Protocol del generador, When se mira el caso de uso real, Then tiene sus cinco métodos."""
    from src.modules.competition.application.services.envelope_desk import GeneradorDePartidos
    from src.modules.competition.application.use_cases.generate_matches_use_case import (
        GenerateMatchesUseCase,
    )

    generador = object.__new__(GenerateMatchesUseCase)
    assert isinstance(generador, GeneradorDePartidos)


def test_c4_la_fila_del_hoyo_cumple_lo_que_lee_bolas_fuera():
    """Given el Protocol de la fila, When se mira la entidad HoleScore, Then tiene los tres campos."""
    from src.modules.competition.domain.entities.hole_score import HoleScore
    from src.modules.competition.domain.value_objects.bolas_fuera import FilaDelHoyo

    fila = object.__new__(HoleScore)
    # Sus campos son propiedades sobre atributos privados
    fila.__dict__.update(_player_user_id=None, _hole_number=1, _validation_status=None)
    assert isinstance(fila, FilaDelHoyo)


@pytest.mark.parametrize(
    "ruta_vieja",
    [
        "src.modules.competition.domain.services.enrollment_opening_service",
        "src.modules.competition.domain.services.snake_draft_service",
        "src.modules.competition.domain.services.marcadores_en_cadena",
        "src.modules.competition.domain.services.zona_horaria",
    ],
)
def test_c5_las_rutas_viejas_no_existen(ruta_vieja):
    """Given la ruta de antes, When se importa, Then falla: nadie puede parchear una copia muerta."""
    with pytest.raises(ImportError):
        importlib.import_module(ruta_vieja)
