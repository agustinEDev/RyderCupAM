"""
Caso de Uso: Listar Competitions con filtros.

Permite obtener lista de competiciones con filtros opcionales.
"""

from datetime import datetime

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.enrollment_opener import (
    EnrollmentOpener,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId

# Quien tiene una invitacion o una solicitud en marcha necesita poder mirar la
# competicion antes de decidir. Quien fue rechazado, se retiro o cancelo, no:
# su fila sigue en la tabla, pero ya no esta dentro (BE #318)
ESTADOS_QUE_DEJAN_VER = {
    EnrollmentStatus.APPROVED,
    EnrollmentStatus.REQUESTED,
    EnrollmentStatus.INVITED,
}


class ListCompetitionsUseCase:
    """
    Caso de uso para listar competiciones con filtros opcionales.

    CLEAN ARCHITECTURE: Este use case retorna ENTIDADES de dominio, NO DTOs.
    La conversión a DTOs y el cálculo de campos de presentación (is_creator,
    enrolled_count, location_formatted) es responsabilidad de la capa de
    presentación (API Layer).

    Orquesta:
    1. Aplicar filtros opcionales (status, creator_id)
    2. Retornar lista de entidades Competition

    Responsabilidades:
    - Filtrado por criterios de negocio
    - Coordinar acceso a repositorios mediante UoW

    NO es responsabilidad del use case:
    - Formatear datos para presentación
    - Calcular campos derivados para UI
    - Convertir entidades a DTOs
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zona_del_campo: ICompetitionTimezone | None = None,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para acceso a repositorios
            zona_del_campo: De donde sale la zona horaria del campo que se juega.
                Hace falta para abrir las competiciones programadas a las que ya
                les toca: mirarlas en un listado tambien las abre (BE #331). Sin
                ella el listado sigue funcionando, simplemente no abre nada.
        """
        self._uow = uow
        self._zona_del_campo = zona_del_campo

    async def execute(
        self,
        status: str | None = None,
        creator_id: str | None = None,
        search_name: str | None = None,
        search_creator: str | None = None,
        viewer_id: str | None = None,
        is_admin: bool = False,
        viewer_email: str | None = None,
    ) -> list[Competition]:
        """
        Ejecuta el caso de uso de listado de competiciones.

        Args:
            status: Filtro opcional por estado (ej: "ACTIVE", "DRAFT")
            creator_id: Filtro opcional por creador (UUID string)
            search_name: Búsqueda parcial case-insensitive en nombre de competición
            search_creator: Búsqueda parcial case-insensitive en nombre del creador

        Returns:
            Lista de entidades Competition

        Raises:
            ValueError: Si los parámetros de filtro son inválidos
        """
        async with self._uow:
            # Si hay parámetros de búsqueda, usar el método find_by_filters
            if search_name or search_creator:
                encontradas = await self._fetch_with_search(
                    search_name=search_name,
                    search_creator=search_creator,
                    status=status,
                    creator_id=creator_id,
                )
                visibles = await self.visibles_para(
                    encontradas, viewer_id, is_admin, viewer_email=viewer_email
                )
                await EnrollmentOpener.abrir_las_que_toquen(
                    visibles, self._uow, self._zona_del_campo
                )
                return self._los_que_siguen_cumpliendo(visibles, status)

            # Si no hay búsqueda, usar el método antiguo (compatibilidad)
            competitions = await self._fetch_filtered_competitions(status, creator_id)
            visibles = await self.visibles_para(
                competitions, viewer_id, is_admin, viewer_email=viewer_email
            )

            # Se abren DESPUES de filtrar la visibilidad: una privada que no se
            # le ensena a quien mira tampoco se le abre de paso (BE #318)
            await EnrollmentOpener.abrir_las_que_toquen(visibles, self._uow, self._zona_del_campo)
            return self._los_que_siguen_cumpliendo(visibles, status)

    async def listar(
        self,
        estados: list[str] | None,
        creator_id: str | None = None,
        search_name: str | None = None,
        search_creator: str | None = None,
        viewer_id: str | None = None,
        is_admin: bool = False,
        viewer_email: str | None = None,
    ) -> list[Competition]:
        """
        Las competiciones de los estados pedidos, sin repetir, abriendo antes las que toquen.

        Sin estados (o con la lista vacía), todas. Es el filtro de `GET /competitions`,
        que puede llegar varias veces (`?status=ACTIVE&status=DRAFT`).

        Se reúnen las filas de todos los estados, se aparta lo que quien mira no puede
        ver, se abre lo que toque y solo entonces se filtra por los estados pedidos
        (BE #814). Si se piden las ACTIVE, se traen también las DRAFT: una programada a
        la que ya le toca abrir es una ACTIVE más. Antes cada estado se filtraba por su
        cuenta y esa programada no salía, o salía según el orden de los estados.
        """
        if not estados:
            return await self.execute(
                status=None,
                creator_id=creator_id,
                search_name=search_name,
                search_creator=search_creator,
                viewer_id=viewer_id,
                is_admin=is_admin,
                viewer_email=viewer_email,
            )

        pedidos = list(dict.fromkeys(e.upper() for e in estados))
        a_consultar = list(pedidos)
        if (
            CompetitionStatus.ACTIVE.value in pedidos
            and CompetitionStatus.DRAFT.value not in pedidos
        ):
            a_consultar.append(CompetitionStatus.DRAFT.value)

        async with self._uow:
            traidas: dict[CompetitionId, Competition] = {}
            for estado in a_consultar:
                if search_name or search_creator:
                    filas = await self._fetch_with_search(
                        search_name=search_name,
                        search_creator=search_creator,
                        status=estado,
                        creator_id=creator_id,
                    )
                else:
                    filas = await self._fetch_filtered_competitions(estado, creator_id)
                for competition in filas:
                    traidas.setdefault(competition.id, competition)

            # Se abren DESPUES de filtrar la visibilidad: una privada que no se le
            # ensena a quien mira tampoco se le abre de paso (BE #318)
            visibles = await self.visibles_para(
                list(traidas.values()), viewer_id, is_admin, viewer_email=viewer_email
            )
            await EnrollmentOpener.abrir_las_que_toquen(visibles, self._uow, self._zona_del_campo)
            return [c for c in visibles if c.status.value in pedidos]

    async def mis_competiciones(
        self,
        quien: UserId,
        estados: list[str] | None,
        search_name: str | None = None,
        search_creator: str | None = None,
        viewer_email: str | None = None,
    ) -> list[Competition]:
        """
        «Mis competiciones»: las que creó y, detrás, en las que está.

        En las que está: sus inscripciones y las privadas a las que le han invitado y
        aún no ha contestado (la invitación no crea fila de inscripción hasta que se
        acepta; release social 2). Pasan por la misma visibilidad que el listado: una
        fila rechazada o retirada no se borra, y sin esto el expulsado recuperaba la
        privada por aquí (BE #318). Se abren las que toquen DESPUÉS de la visibilidad
        y ANTES del filtro por estado, como en `execute`: filtrar por el estado viejo
        tiraría la recién abierta (BE #331).
        """
        async with self._uow:
            yo = str(quien.value)
            creadas = await self.listar(
                estados,
                creator_id=yo,
                search_name=search_name,
                search_creator=search_creator,
                viewer_id=yo,
            )
            inscripciones = await self._uow.enrollments.find_by_user(quien)
            estado_de_la_inscripcion = {i.competition_id: i.status for i in inscripciones}
            ids_creadas = {c.id for c in creadas}
            ids = {i.competition_id for i in inscripciones}
            ids |= set(
                await self._uow.invitations.competiciones_con_invitacion_pendiente(
                    quien, viewer_email, datetime.now()
                )
            )
            candidatas = []
            for competition_id in ids:
                competition = await self._uow.competitions.find_by_id(competition_id)
                if competition and competition.id not in ids_creadas:
                    candidatas.append(competition)

            visibles = await self.visibles_para(candidatas, yo, viewer_email=viewer_email)
            await EnrollmentOpener.abrir_las_que_toquen(visibles, self._uow, self._zona_del_campo)
            return creadas + self._las_inscritas_que_quedan(
                visibles, estados, estado_de_la_inscripcion
            )

    async def las_de_los_demas(
        self,
        quien: UserId,
        estados: list[str] | None,
        creator_id: str | None = None,
        search_name: str | None = None,
        search_creator: str | None = None,
        is_admin: bool = False,
        viewer_email: str | None = None,
    ) -> list[Competition]:
        """
        El listado sin las suyas: ni las que creó, ni en las que tiene inscripción, ni
        a las que le han invitado. Esas ya salen en «Mis competiciones» (revisor de la
        release social 2).
        """
        async with self._uow:
            todas = await self.listar(
                estados,
                creator_id=creator_id,
                search_name=search_name,
                search_creator=search_creator,
                viewer_id=str(quien.value),
                is_admin=is_admin,
                viewer_email=viewer_email,
            )
            inscripciones = await self._uow.enrollments.find_by_user(quien)
            suyas = {i.competition_id for i in inscripciones}
            suyas |= await self._uow.invitations.competiciones_con_invitacion_pendiente(
                quien, viewer_email, datetime.now()
            )
            return [c for c in todas if c.creator_id != quien and c.id not in suyas]

    @staticmethod
    def _las_inscritas_que_quedan(
        competitions: list[Competition],
        estados: list[str] | None,
        estado_de_la_inscripcion: dict[CompetitionId, EnrollmentStatus],
    ) -> list[Competition]:
        """
        Los filtros que dependen del ESTADO, ya con el estado definitivo (BE #331).

        Fuera la rechazada salvo en una competición ACTIVE, y las que no son de los
        estados pedidos.
        """
        pedidos = [e.upper() for e in estados] if estados else None
        quedan = []
        for competition in competitions:
            estado = competition.status.value
            rechazada = estado_de_la_inscripcion.get(competition.id) == EnrollmentStatus.REJECTED
            if rechazada and estado != "ACTIVE":
                continue
            if pedidos is None or estado in pedidos:
                quedan.append(competition)
        return quedan

    @staticmethod
    def _los_que_siguen_cumpliendo(
        competitions: list[Competition], status: str | None
    ) -> list[Competition]:
        """Vuelve a aplicar el filtro de estado despues de abrir.

        La consulta filtro por el estado que habia; abrir cambia el de algunas,
        y devolverlas igual haria que una pestana «Borradores» pintase una
        competicion con las inscripciones ya abiertas (BE #331).
        """
        if status is None:
            return competitions

        # `.upper()` como en todas las demas capas: la consulta normaliza
        # (`CompetitionStatus(status.upper())`) y la ruta tambien, asi que
        # comparar aqui en crudo hacia que `?status=active` devolviera vacio
        # despues de haber traido las filas correctas
        pedido = status.upper()
        return [c for c in competitions if c.status.value == pedido]

    async def visibles_para(
        self,
        competitions: list[Competition],
        viewer_id: str | None,
        is_admin: bool = False,
        *,
        viewer_email: str | None = None,
    ) -> list[Competition]:
        """Aparta las privadas de quien no esta dentro (BE #318).

        Lo usan `execute` y `mis_competiciones`, que añade las competiciones
        que salen de tus inscripciones. Ese camino se saltó el filtro cuando
        vivía en la ruta y dejaba al expulsado recuperando la privada de la
        que acababan de echarlo.

        Una privada la ve su creador, quien esta dentro y quien tiene una
        invitacion o una solicitud en marcha — ese necesita mirarla antes de
        decidir. La invitacion vive en su tabla, sin fila de inscripcion hasta
        que se acepta: cuenta la pendiente y sin caducar, por su usuario o por
        su correo (release social 2). No la ve quien fue rechazado, se retiro o cancelo: su fila
        sigue en la tabla, pero ya no esta dentro.

        Un admin lo ve todo: puede editarla y borrarla, asi que no verla en el
        listado le dejaria con el permiso y sin la puerta.

        Sin saber quien mira, solo se ensena lo publico.
        """
        if is_admin:
            return competitions

        publicas = [c for c in competitions if c.visibility.is_discoverable()]
        privadas = [c for c in competitions if not c.visibility.is_discoverable()]
        if not privadas or viewer_id is None:
            return publicas

        quien = UserId(viewer_id)
        # UNA consulta por quien mira, no una por competicion: el listado trae
        # hasta 100 por estado pedido
        inscripciones = await self._uow.enrollments.find_by_user(quien)
        dentro_de = {e.competition_id for e in inscripciones if e.status in ESTADOS_QUE_DEJAN_VER}
        dentro_de |= await self._uow.invitations.competiciones_con_invitacion_pendiente(
            quien, viewer_email, datetime.now()
        )

        visibles = {c.id for c in publicas}
        visibles |= {c.id for c in privadas if c.creator_id == quien or c.id in dentro_de}
        # En el orden en que venian, que es el que decidio la consulta
        return [c for c in competitions if c.id in visibles]

    async def _fetch_filtered_competitions(
        self,
        status: str | None,
        creator_id: str | None,
    ) -> list[Competition]:
        """
        Obtiene competiciones aplicando filtros.

        Args:
            status: Filtro por estado (opcional)
            creator_id: Filtro por creador (opcional)

        Returns:
            Lista de entidades Competition
        """
        # Si hay filtro por status
        if status:
            status_enum = CompetitionStatus(status.upper())
            competitions = await self._uow.competitions.find_by_status(status_enum)

            # Si además hay filtro por creator_id, filtrar en memoria
            if creator_id:
                creator_user_id = UserId(creator_id)
                competitions = [c for c in competitions if c.creator_id == creator_user_id]

            return competitions

        # Si solo hay filtro por creator_id
        if creator_id:
            creator_user_id = UserId(creator_id)
            return await self._uow.competitions.find_by_creator(creator_user_id)

        # Sin filtros: retornar todas las competiciones
        return await self._uow.competitions.find_all()

    async def _fetch_with_search(
        self,
        search_name: str | None,
        search_creator: str | None,
        status: str | None,
        creator_id: str | None,
    ) -> list[Competition]:
        """
        Obtiene competiciones usando búsqueda avanzada.

        Args:
            search_name: Búsqueda en nombre de competición
            search_creator: Búsqueda en nombre del creador
            status: Filtro por estado (opcional)
            creator_id: Filtro por creador (opcional)

        Returns:
            Lista de entidades Competition
        """
        # Convertir status string a enum si existe
        status_enum = CompetitionStatus(status.upper()) if status else None

        # Convertir creator_id string a UserId si existe
        creator_user_id = UserId(creator_id) if creator_id else None

        # Usar el método find_by_filters del repositorio
        return await self._uow.competitions.find_by_filters(
            search_name=search_name,
            search_creator=search_creator,
            status=status_enum,
            creator_id=creator_user_id,
        )
