"""
Todos los mapas `error de dominio -> código HTTP` de la API, juntos (composition root).

Cada módulo declara el suyo en su `infrastructure/api/codigos_de_error.py`; `main.py`
los registra con `registra_los_codigos`. Una misma clase no puede estar en dos mapas.
"""

from src.modules.competition.infrastructure.api.codigos_de_error import (
    CODIGOS as CODIGOS_DE_COMPETICION,
)
from src.modules.quick_match.infrastructure.api.codigos_de_error import (
    CODIGOS as CODIGOS_DE_PARTIDA_RAPIDA,
)
from src.modules.social.infrastructure.api.codigos_de_error import CODIGOS as CODIGOS_DE_SOCIAL
from src.modules.user.infrastructure.api.codigos_de_error import CODIGOS as CODIGOS_DE_USUARIO
from src.shared.infrastructure.http.codigos_de_error_compartidos import CODIGOS_COMPARTIDOS

_MAPAS = (
    CODIGOS_COMPARTIDOS,
    CODIGOS_DE_COMPETICION,
    CODIGOS_DE_PARTIDA_RAPIDA,
    CODIGOS_DE_SOCIAL,
    CODIGOS_DE_USUARIO,
)


def todos_los_codigos() -> dict[type[Exception], int]:
    """El mapa de toda la API. Falla si una clase aparece en dos mapas."""
    todos: dict[type[Exception], int] = {}
    for mapa in _MAPAS:
        repetidas = todos.keys() & mapa.keys()
        if repetidas:
            raise ValueError(f"Errores en dos mapas: {sorted(c.__name__ for c in repetidas)}")
        todos.update(mapa)
    return todos
