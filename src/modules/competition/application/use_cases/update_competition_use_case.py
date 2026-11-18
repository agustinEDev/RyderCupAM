"""
Caso de Uso: Actualizar Competition.

Permite actualizar una competición existente (solo en estado DRAFT).
"""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from src.modules.competition.application.dto.competition_dto import (
    UpdateCompetitionRequestDTO,
    UpdateCompetitionResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionAlreadyExistsError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    DraftInProgressError,
    exigir_sin_draft_abierto,
)
from src.modules.competition.application.services.mover_el_torneo import (
    alguna_sesion_empezada,
    mover_la_actualizacion_programada,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)
from src.modules.competition.application.services.reapertura import Reapertura
from src.modules.competition.application.services.salidas_de_la_ronda import salidas_vigentes
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

# En el orden del día, para nombrarlas como se juegan
_ORDEN_DE_FRANJA = {SessionType.MORNING: 0, SessionType.AFTERNOON: 1, SessionType.EVENING: 2}


class CompetitionNotEditableError(Exception):
    """Excepción lanzada cuando la competición no está en estado DRAFT."""

    pass


class DatesLeaveSessionsOutError(CompetitionNotEditableError):
    """Las fechas nuevas dejan fuera estas sesiones (#710).

    Hereda del error de siempre para no cambiarle nada a quien ya lo captura.
    Lleva las sesiones: con varias, «alguna quedaría fuera» no decía cuál. Como
    datos y no como entidades: se leen fuera de la transacción, ya deshecha, y
    un atributo caducado revienta (MissingGreenlet)
    """

    def __init__(self, sesiones: list[tuple[UUID, date, str]]):
        self.sesiones = sesiones
        super().__init__(
            "No se pueden mover las fechas: alguna sesión quedaría fuera del torneo. "
            "Cambia o borra antes esas sesiones."
        )


class UpdateCompetitionUseCase:
    """
    Caso de uso para actualizar una competición existente.

    Restricciones:
    - Solo se puede actualizar en estado DRAFT
    - Solo el creador puede actualizar
    - Todos los campos son opcionales (actualización parcial)

    Orquesta:
    1. Validar que la competición existe
    2. Validar que el usuario es el creador
    3. Validar que está en estado DRAFT
    4. Actualizar solo los campos proporcionados
    5. Persistir cambios
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        location_builder: LocationBuilder,
        golf_course_repository: IGolfCourseRepository,
        actividad: CompetitionActivityPublisherInterface | None = None,
        plazo: PlazoDeInscripcion | None = None,
        correos: IInvitationEmailService | None = None,
        user_uow: UserUnitOfWorkInterface | None = None,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            location_builder: Domain Service para construir Location
            golf_course_repository: Campos de golf (otro módulo): al cambiar la
                ubicación, la entidad necesita el país de los suyos
            plazo: El plazo de inscripción (15 nov 2026): con él, una cerrada por
                el plazo puede moverse (R3); sin él, en CLOSED no se edita
        """
        self._uow = uow
        self._location_builder = location_builder
        self._golf_course_repo = golf_course_repository
        # Los avisos de Actividad (BE-2); sin el, no se avisa
        self._actividad = AvisosDeActividad(actividad)
        self._plazo = plazo
        # Reabierta al moverla (R3): el correo de invitación otra vez a quien no
        # tiene cuenta (O2, 15 nov 2026)
        self._correos = correos
        self._user_uow = user_uow

    async def _paises_de_los_campos(self, competition: Competition) -> list[CountryCode]:
        """El país de cada campo de golf de la competición."""
        paises = []
        for asociacion in competition.golf_courses:
            campo = await self._golf_course_repo.find_by_id(asociacion.golf_course_id)
            if campo is not None:
                paises.append(campo.country_code)
        return paises

    @staticmethod
    def _campos_de_localizacion(request: UpdateCompetitionRequestDTO) -> set[str]:
        """Campos de localización que el payload trae CON valor.

        Se mira `model_fields_set` para separar «no lo mandes» de «mándalo vacío»,
        y además se descarta el `None` explícito: `countries: []` quita los países
        acompañantes, `countries: null` no toca nada.
        """
        candidatos = ("main_country", "adjacent_country_1", "adjacent_country_2", "countries")
        enviados = request.model_fields_set
        return {c for c in candidatos if c in enviados and getattr(request, c) is not None}

    async def _construir_location(
        self, request: UpdateCompetitionRequestDTO, competition: Competition
    ) -> Location:
        """Construye la nueva localización a partir de lo que llega y de lo que hay.

        Tres reglas, de más fuerte a más débil:

        - Con `main_country` se rehace entera. Los acompañantes son los que lleguen,
          porque los de antes no tienen por qué ser adyacentes al país nuevo.
        - Con la lista `countries` manda la lista entera: lo que no esté en ella se va.
        - Con un campo adyacente suelto se cambia solo ese hueco y **el otro se
          conserva**; si no, repetir un país borraba al otro sin avisar.
        """
        enviados = self._campos_de_localizacion(request)
        actual = competition.location

        # En `enviados` solo entra lo que llega con valor: el `is not None` es para el tipo
        if "main_country" in enviados and request.main_country is not None:
            return await self._location_builder.build_from_codes(
                main_country=request.main_country,
                adjacent_country_1=request.adjacent_country_1,
                adjacent_country_2=request.adjacent_country_2,
            )

        principal = str(actual.main_country)

        if "countries" in enviados:
            return await self._location_builder.build_from_codes(
                main_country=principal,
                adjacent_country_1=request.adjacent_country_1,
                adjacent_country_2=request.adjacent_country_2,
            )

        def hueco(campo: str, valor_actual: CountryCode | None) -> str | None:
            if campo in enviados:
                enviado: str | None = getattr(request, campo)
                return enviado
            return str(valor_actual) if valor_actual else None

        return await self._location_builder.build_from_codes(
            main_country=principal,
            adjacent_country_1=hueco("adjacent_country_1", actual.adjacent_country_1),
            adjacent_country_2=hueco("adjacent_country_2", actual.adjacent_country_2),
        )

    @staticmethod
    def _comprobar_que_la_agenda_sigue_valiendo(
        rondas: list[Round], competition: Competition, request: UpdateCompetitionRequestDTO
    ) -> None:
        """Lo que la agenda ya montada no aguanta que cambie.

        Raises:
            CompetitionNotEditableError: Si alguna sesion quedaria fuera de las
                fechas nuevas, o si se cambia el modo de juego con alguna sesion
                que ya tiene partidos
        """
        if not rondas:
            return
        if request.start_date and request.end_date:
            fuera = [
                r for r in rondas if not request.start_date <= r.round_date <= request.end_date
            ]
            if fuera:
                ordenadas = sorted(
                    fuera, key=lambda r: (r.round_date, _ORDEN_DE_FRANJA[r.session_type])
                )
                raise DatesLeaveSessionsOutError(
                    [(r.id.value, r.round_date, r.session_type.value) for r in ordenadas]
                )
        cambia_el_modo = request.play_mode and request.play_mode != competition.play_mode.value
        if cambia_el_modo and any(not r.can_modify() for r in rondas):
            raise CompetitionNotEditableError(
                "No se puede cambiar el modo de juego: ya hay sesiones con partidos."
            )

    @staticmethod
    def _cambia_algo_mas(competition: Competition, request: UpdateCompetitionRequestDTO) -> bool:
        """
        Si llega algo, además de las fechas, con un valor distinto del que tiene.

        La app manda el formulario entero en cada edición (nombre, país, cupo,
        equipos...): lo que llega igual no cuenta como cambio (F1, 16 nov 2026).
        Un campo que no se sabe comparar cuenta como cambio.
        """
        location = competition.location

        def codigo(pais: object) -> str:
            return str(getattr(pais, "value", pais))

        adyacentes = [
            codigo(c) for c in (location.adjacent_country_1, location.adjacent_country_2) if c
        ]
        ryder = competition.ryder_cup

        def valor(v: object) -> object:
            return getattr(v, "value", v)

        iguales: dict[str, Callable[[Any], bool]] = {
            "name": lambda v: " ".join(v.split()) == competition.name.value,
            "main_country": lambda v: v == codigo(location.main_country),
            "play_mode": lambda v: v == competition.play_mode.value,
            "visibility": lambda v: valor(v) == valor(competition.visibility),
            "max_players": lambda v: v == competition.max_players,
            "max_playing_handicap": lambda v: v == competition.max_playing_handicap,
            "enrollment_opens_days_before": lambda v: v == competition.enrollment_opens_days_before,
            "team_1_name": lambda v: ryder is not None and v.strip() == ryder.team_1_name,
            "team_2_name": lambda v: ryder is not None and v.strip() == ryder.team_2_name,
            "setup_mode": lambda v: ryder is not None and valor(v) == valor(ryder.setup_mode),
            "team_assignment": lambda v: ryder is not None and v == valor(ryder.team_assignment),
        }
        # Los acompañantes, como conjunto: en otro orden son los mismos (D5)
        paises = {"countries", "adjacent_country_1", "adjacent_country_2"}
        if set(adyacentes) != UpdateCompetitionUseCase._acompanantes_pedidos(request, adyacentes):
            return True
        for campo in request.model_fields_set - {"start_date", "end_date"} - paises:
            nuevo = getattr(request, campo)
            # `None` es «no lo toques», salvo en la apertura, donde es «quítala»
            if nuevo is None and campo != "enrollment_opens_days_before":
                continue
            igual = iguales.get(campo)
            if igual is None or not igual(nuevo):
                return True
        return False

    @staticmethod
    def _acompanantes_pedidos(
        request: UpdateCompetitionRequestDTO, actuales: list[str]
    ) -> set[str]:
        """
        Los acompañantes con los que quedaría, con las reglas de siempre: la lista
        `countries` manda entera; un hueco suelto cambia solo ese; `None`, nada.
        """
        if request.countries is not None and "countries" in request.model_fields_set:
            return {str(c) for c in request.countries}
        huecos = [*actuales, None, None][:2]
        for i, campo in enumerate(("adjacent_country_1", "adjacent_country_2")):
            pedido = getattr(request, campo)
            if campo in request.model_fields_set and pedido is not None:
                huecos[i] = pedido
        return {str(h) for h in huecos if h}

    @staticmethod
    def _comprobar_que_caben_movidas(
        rondas: list[Round], dias: int, request: UpdateCompetitionRequestDTO
    ) -> None:
        """
        Las sesiones se mueven con el torneo (O1); si con el torneo nuevo alguna
        queda fuera —es más corto—, no se mueve nada.

        Raises:
            DatesLeaveSessionsOutError: Con las que quedarían fuera
            CompetitionNotEditableError: Si alguna ya se está jugando o se jugó
        """
        if any(r.status in (RoundStatus.IN_PROGRESS, RoundStatus.COMPLETED) for r in rondas):
            raise CompetitionNotEditableError(
                "No se pueden mover las fechas: alguna sesión ya se ha jugado."
            )
        inicio, fin = request.start_date, request.end_date
        fuera = [
            r
            for r in rondas
            if inicio is None
            or fin is None
            or not inicio <= r.round_date + timedelta(days=dias) <= fin
        ]
        if fuera:
            ordenadas = sorted(
                fuera, key=lambda r: (r.round_date, _ORDEN_DE_FRANJA[r.session_type])
            )
            raise DatesLeaveSessionsOutError(
                [
                    (r.id.value, r.round_date + timedelta(days=dias), r.session_type.value)
                    for r in ordenadas
                ]
            )

    async def _mover_si_la_cerro_el_plazo(
        self,
        competition_id: CompetitionId,
        request: UpdateCompetitionRequestDTO,
        user_id: UserId,
        is_admin: bool,
    ) -> UpdateCompetitionResponseDTO | None:
        """
        Cerrada por el plazo, mueve el torneo con todas sus sesiones y franjas los
        mismos días (O1) y, si el plazo nuevo está en el futuro, la reabre por el
        camino de siempre: se cerrará en el plazo nuevo (R3). Cerrada a mano no
        se mueve (None: sigue el camino de siempre, que en CLOSED no edita).
        """
        plazo = self._plazo
        if plazo is None or request.start_date is None or request.end_date is None:
            return None
        async with self._uow:
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if (
                competition is None
                or competition.status is not CompetitionStatus.CLOSED
                or not competition.enrollment_closed_by_deadline
            ):
                return None
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede actualizar la competición")
            if self._cambia_algo_mas(competition, request):
                raise CompetitionNotEditableError(
                    "Con las inscripciones cerradas por el plazo solo se pueden mover las fechas."
                )
            # Con la sala de draft abierta no se reabre (O1): se dice antes de mover nada
            try:
                await exigir_sin_draft_abierto(self._uow, competition_id)
            except DraftInProgressError as abierta:
                raise DraftInProgressError(
                    "No se pueden mover las fechas con la sala de draft abierta: "
                    "termina antes el draft."
                ) from abierta
            dias = (request.start_date - competition.dates.start_date).days
            rondas = await self._uow.rounds.find_by_competition(competition_id)
            self._comprobar_que_caben_movidas(rondas, dias, request)
            # Lo que ya empezó, por el reloj, no se mueve: ni la sesión ni el resto
            if await alguna_sesion_empezada(self._uow, rondas, plazo.zonas, plazo.ahora()):
                raise CompetitionNotEditableError(
                    "No se pueden mover las fechas: alguna sesión ya ha empezado."
                )
            antes = {r.id: await salidas_vigentes(self._uow, r.id) for r in rondas}
            # Una a una y en el orden que no deja dos sesiones el mismo día a la
            # vez (la base de datos no lo admite): hacia delante, la última primero
            for ronda in sorted(rondas, key=lambda r: r.round_date, reverse=dias > 0):
                ronda.desplazar(dias)
                await self._uow.rounds.update(ronda)
                await self._uow.flush()
            competition.move_dates_closed_by_deadline(
                DateRange(request.start_date, request.end_date)
            )
            # Y la actualización de hándicaps programada, con el torneo (O4)
            await mover_la_actualizacion_programada(
                self._uow, competition, dias, plazo.zonas, plazo.ahora()
            )
            reabierta = await plazo.queda_plazo(competition)
            reapertura = Reapertura(
                self._uow,
                plazo.zonas,
                plazo.ahora,
                self._actividad,
                correos=self._correos,
                user_uow=self._user_uow,
            )
            if reabierta:
                await reapertura.reabrir(competition)
            await self._uow.competitions.update(competition)
            await self._uow.flush()
            despues = {r.id: await salidas_vigentes(self._uow, r.id) for r in rondas}

        # Ya guardado: las salidas cambian de día (o se van con la reapertura) y,
        # reabierta, el «se han cerrado» ya no vale. El «no se puede cerrar» se
        # retiró al cerrarla (D7)
        for round_id, salidas in antes.items():
            await self._actividad.salidas_cambiadas(
                competition, round_id, salidas, despues[round_id]
            )
        if reabierta:
            await self._actividad.enrollments_closed_withdrawn(competition)
            # Como al reabrir a mano: sus avisos de hándicaps con la RFEG (#864)
            await reapertura.avisar_handicaps(competition)
            # Y las invitaciones que esperaban vuelven: «ya puedes aceptar» (P2)
            await reapertura.avisar_a_los_invitados(competition)
        return UpdateCompetitionResponseDTO(
            id=competition.id.value,
            name=str(competition.name),
            updated_at=competition.updated_at,
        )

    async def _avisar_tras_editar(
        self,
        competition: Competition,
        era_publica: bool,
        inicio_de_antes: date,
        estaba_avisada: bool,
    ) -> None:
        """
        Ya guardada: si deja de ser publica, sus amigos dejan de ver quien se
        apunto; al hacerse publica no se publica nada hacia atras (BE-2). Y con
        otra fecha hay otro plazo: el «no se puede cerrar», si se le dio, ya no
        vale (F2, D7).
        """
        if era_publica and competition.visibility != Visibility.PUBLIC:
            await self._actividad.made_private(competition.id)
        if estaba_avisada and competition.dates.start_date != inicio_de_antes:
            await self._actividad.close_block_withdrawn(competition)

    async def _editable(
        self, competition_id: CompetitionId, user_id: UserId, is_admin: bool
    ) -> Competition:
        """
        La competición, bloqueada, si quien pide la organiza y aún se puede tocar.

        Raises:
            CompetitionNotFoundError, NotCompetitionCreatorError, CompetitionNotEditableError
        """
        # 1. Buscar la competición
        # Bloqueada: mover las fechas no puede cruzarse con un cambio de las
        # jornadas por jugador (#251)
        competition = await self._uow.competitions.find_by_id_for_update(competition_id)
        if not competition:
            raise CompetitionNotFoundError(f"No existe competición con ID {competition_id.value}")

        # 2. Validar que el usuario es el creador
        if not is_admin and not competition.is_creator(user_id):
            raise NotCompetitionCreatorError("Solo el creador puede actualizar la competición")

        # 3. Validar que está en estado DRAFT (se puede modificar)
        if not competition.allows_modifications():
            raise CompetitionNotEditableError(
                f"No se puede modificar una competición en estado {competition.status.value}. "
                f"Solo mientras las inscripciones están abiertas."
            )
        return competition

    async def _comprobar_el_cupo(
        self, competition_id: CompetitionId, request: UpdateCompetitionRequestDTO
    ) -> None:
        """
        Con las inscripciones abiertas ya hay gente apuntada (BE #323), y bajar el
        número les dejaría fuera de un torneo que ya tenían.
        """
        if request.max_players is not None:
            inscritos = await self._uow.enrollments.count_approved(competition_id)
            if request.max_players < inscritos:
                raise CompetitionNotEditableError(
                    f"No se puede bajar el cupo a {request.max_players}: "
                    f"ya hay {inscritos} jugadores inscritos."
                )

    async def _nombre_nuevo(
        self, request: UpdateCompetitionRequestDTO, competition: Competition
    ) -> CompetitionName | None:
        """
        El nombre nuevo, o None si no cambia.

        El mismo de antes no se revalida: uno guardado con las reglas antiguas
        no impide editar el resto (la app manda siempre el nombre, revisor).
        Con los espacios ya normalizados: «A » sigue siendo «A» (CodeRabbit).
        """
        mismo = (
            request.name is not None and " ".join(request.name.split()) == competition.name.value
        )
        name = CompetitionName(request.name) if request.name and not mismo else None
        # Renombrar a un nombre que ya tiene es repetirlo, sin mirar mayúsculas (#540)
        if name is not None and await self._uow.competitions.exists_with_name(
            name, competition.creator_id, except_id=competition.id
        ):
            raise CompetitionAlreadyExistsError(f"Ya existe una competición con el nombre '{name}'")
        return name

    async def _localizacion_nueva(
        self, request: UpdateCompetitionRequestDTO, competition: Competition
    ) -> tuple[Location | None, list[CountryCode] | None]:
        """
        La localización se reconstruye en cuanto llega cualquiera de sus campos,
        no solo con `main_country`: la pantalla permite cambiar los países
        acompañantes sin tocar el principal, y entonces el principal no llega.

        «Llega» es traer el campo CON valor: `countries: []` significa «quítalos»
        y `countries: null` significa «no los toques», que es lo que manda un
        cliente que serializa el formulario entero con sus huecos.
        """
        if not self._campos_de_localizacion(request):
            return None, None
        nueva_location = await self._construir_location(request, competition)
        # Los campos son otro agregado: sus países los trae el caso de uso
        # y la entidad decide si la ubicación nueva los deja fuera
        paises_de_los_campos = await self._paises_de_los_campos(competition)
        return nueva_location, paises_de_los_campos

    async def execute(
        self,
        competition_id: CompetitionId,
        request: UpdateCompetitionRequestDTO,
        user_id: UserId,
        is_admin: bool = False,
    ) -> UpdateCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de actualización de competición.

        Args:
            competition_id: ID de la competición a actualizar
            request: DTO con los datos a actualizar (todos opcionales)
            user_id: ID del usuario que solicita la actualización

        Returns:
            DTO con los datos de la competición actualizada

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotEditableError: Si no está en estado DRAFT
        """
        # Cerrada por el plazo, se puede mover el torneo, y nada más (R3)
        movida = await self._mover_si_la_cerro_el_plazo(competition_id, request, user_id, is_admin)
        if movida is not None:
            return movida

        async with self._uow:
            competition = await self._editable(competition_id, user_id, is_admin)

            # 3a. Con agenda, solo se protege lo que ella necesita (BE #323,
            # afinado en BE #365). Antes se rechazaba TODO en cuanto habia una
            # sesion, y desde que la agenda se propone al crear la competicion
            # eso impedia hasta cambiarle el nombre.
            #
            # `ACTIVE` no significa «todavia no hay nada»: se vuelve a ACTIVE desde
            # CLOSED con `reopen_enrollments`, y entonces ya puede haber partidos.
            # Mover las fechas dejaria sesiones fuera del rango del torneo, y
            # cambiar el modo de juego dejaria los golpes ya anotados sin relacion
            # con lo que se ensena
            rondas = await self._uow.rounds.find_by_competition(competition_id)
            self._comprobar_que_la_agenda_sigue_valiendo(rondas, competition, request)

            # 3b. El cupo no puede quedarse por debajo de quien ya esta dentro.
            await self._comprobar_el_cupo(competition_id, request)

            # 4. Construir los Value Objects y obtener valores opcionales
            name = await self._nombre_nuevo(request, competition)
            dates = _fechas_nuevas(request)
            nueva_location, paises_de_los_campos = await self._localizacion_nueva(
                request, competition
            )

            play_mode = PlayMode(request.play_mode) if request.play_mode else None

            team_assignment = (
                TeamAssignment(request.team_assignment) if request.team_assignment else None
            )

            # 5. Actualizar la competición usando el método de dominio
            # Aparte de `update_info`: ahi un `None` significa «no lo toques», y
            # aqui tiene que poder significar «quitala» (BE #319)
            if "enrollment_opens_days_before" in request.model_fields_set:
                competition.schedule_enrollment_opening(request.enrollment_opens_days_before)

            era_publica = competition.visibility == Visibility.PUBLIC
            inicio_de_antes = competition.dates.start_date
            # Mover las fechas olvida el apunte: se mira antes (D7)
            estaba_avisada = competition.close_blocked_notified
            competition.update_info(
                visibility=request.visibility,
                setup_mode=request.setup_mode,
                name=name,
                dates=dates,
                location=nueva_location,
                golf_course_countries=paises_de_los_campos,
                play_mode=play_mode,
                max_players=request.max_players,
                team_assignment=team_assignment,
                team_1_name=request.team_1_name,
                team_2_name=request.team_2_name,
                max_playing_handicap=request.max_playing_handicap,
            )

            # 6. Persistir cambios
            await self._uow.competitions.update(competition)

        # 6b. Ya guardada: si deja de ser publica, sus amigos dejan de ver quien
        #     se apunto. Al hacerse publica no se publica nada hacia atras (BE-2)
        await self._avisar_tras_editar(competition, era_publica, inicio_de_antes, estaba_avisada)

        # 7. Retornar DTO de respuesta
        return UpdateCompetitionResponseDTO(
            id=competition.id.value,
            name=str(competition.name),
            updated_at=competition.updated_at,
        )


def _fechas_nuevas(request: UpdateCompetitionRequestDTO) -> DateRange | None:
    """Las fechas nuevas: las dos o ninguna."""
    if request.start_date and request.end_date:
        return DateRange(request.start_date, request.end_date)
    if request.start_date or request.end_date:
        raise ValueError(
            "Se deben proporcionar ambas fechas (start_date y end_date) para actualizarlas."
        )
    return None
