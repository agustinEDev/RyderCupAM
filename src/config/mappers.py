"""
Arranque de todos los mappers de SQLAlchemy, en un solo sitio (#565).

Lo usan la aplicación (`main.py`), Alembic (`alembic/env.py`), los tests y los
scripts. Antes
cada uno llevaba su lista, y la de Alembic se había quedado con 3 de los 8
grupos: no conocía las tablas de campos, partidas rápidas ni las sociales, y un
`alembic revision --autogenerate` habría propuesto borrarlas.

Forma parte de la composition root: importa la infraestructura de todos los
módulos. Todas las funciones son idempotentes (se preguntan con
`inspect(..., raiseerr=False)`, ver BE #179), así que llamarla dos veces no
falla. El orden importa: GolfCourse antes que Competition, que la referencia.
"""

from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    start_mappers as start_competition_mappers,
)
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    start_golf_course_mappers,
)
from src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper import (
    start_quick_match_mappers,
)
from src.modules.social.infrastructure.persistence.mappers.activity_event_mapper import (
    start_activity_event_mappers,
)
from src.modules.social.infrastructure.persistence.mappers.friendship_mapper import (
    start_social_mappers,
)
from src.modules.social.infrastructure.persistence.mappers.profile_photo_mapper import (
    start_profile_photo_mappers,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import (
    start_mappers as start_user_mappers,
)
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import (
    start_mappers as start_country_mappers,
)


def start_all_mappers() -> None:
    """Mapea todas las entidades a sus tablas y deja el metadata completo."""
    start_user_mappers()
    start_country_mappers()
    start_golf_course_mappers()  # antes que Competition, que la referencia
    start_competition_mappers()
    start_social_mappers()
    start_profile_photo_mappers()
    start_activity_event_mappers()
    start_quick_match_mappers()
