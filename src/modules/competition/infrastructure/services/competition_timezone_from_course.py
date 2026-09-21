"""
Adaptador: la zona horaria de una competicion sale de su primer campo (BE #319).

La hora de apertura que escribe el organizador es local del campo donde se
juega. El campo ya trae su zona resuelta desde sus coordenadas (BE #305), asi
que aqui solo hay que ir a buscarla.

«El primero» es el de menor `display_order`, que es el orden en que se juegan.
"""

import logging

from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_repository_interface import (
    CompetitionRepositoryInterface,
)
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)

logger = logging.getLogger(__name__)

# El atributo mapeado que guarda los campos de la competicion. El listado no
# lo carga y la ficha si, y de eso depende si hay que recargar (BE #331)
RELACION_DE_CAMPOS = "_golf_courses"


class CompetitionTimezoneFromCourse(ICompetitionTimezone):
    """Resuelve la zona de una competicion mirando el campo que se juega."""

    def __init__(
        self,
        golf_course_repository: IGolfCourseRepository,
        competition_repository: CompetitionRepositoryInterface | None = None,
    ):
        self._golf_courses = golf_course_repository
        self._competitions = competition_repository

    async def _con_sus_campos(self, competition: Competition) -> Competition:
        """Devuelve la competicion con sus campos cargados, recargandola si hace falta.

        La ficha la trae entera —`find_by_id` hace eager load—, pero el listado
        no: sus consultas no cargan la relacion, y tocarla ahi dispara una carga
        perezosa fuera de la sesion async, que revienta con `MissingGreenlet`.
        Cargarla en el listado tampoco vale: serian los campos, sus barras y sus
        hoyos de hasta 100 competiciones, justo el N+1 que BE #330 quito.

        Asi que se recarga solo cuando no esta cargada, y solo llegan aqui las
        pocas que estan esperando su apertura. Preguntarselo a SQLAlchemy en vez
        de intentarlo y capturar el error es lo que evita la consulta cuando ya
        viene cargada.
        """
        if self._competitions is None:
            return competition

        try:
            estado = inspect(competition)
            if estado is None:
                return competition

            # El nombre va a mano porque la clave del mapper solo existe con
            # TODOS los mapeos registrados, y este modulo se importa antes. Para
            # que un renombrado no se convierta en un 500 silencioso del listado
            # entero, se comprueba que la relacion siga existiendo: si no, se
            # recarga igual y se deja dicho en el log
            conocidas = {relacion.key for relacion in estado.mapper.relationships}
            if RELACION_DE_CAMPOS not in conocidas:
                logger.warning(
                    "La relacion %s ya no existe en el mapeo de Competition: se "
                    "recarga por si acaso. Revisar CompetitionTimezoneFromCourse.",
                    RELACION_DE_CAMPOS,
                )
                sin_cargar = True
            else:
                sin_cargar = RELACION_DE_CAMPOS in estado.unloaded
        except NoInspectionAvailable:
            # Una entidad que no viene de SQLAlchemy —un test con objetos en
            # memoria— no tiene nada que recargar
            return competition

        if not sin_cargar:
            return competition

        recargada = await self._competitions.find_by_id(competition.id)
        return recargada if recargada is not None else competition

    async def for_competition(self, competition: Competition) -> str | None:
        """La zona del primer campo, o `None` si todavia no hay campo."""
        competition = await self._con_sus_campos(competition)
        campos = competition.golf_courses
        if not campos:
            # Se puede crear una competicion, invitar y anadir el campo despues
            # (BE #323): hasta que lo haya, la apertura programada espera
            return None

        primero = min(campos, key=lambda cgc: cgc.display_order)
        campo = await self._golf_courses.find_by_id(primero.golf_course_id)
        if campo is None:
            logger.warning(
                "La competicion %s apunta a un campo que no existe: %s",
                competition.id.value,
                primero.golf_course_id.value,
            )
            return None

        return campo.timezone
