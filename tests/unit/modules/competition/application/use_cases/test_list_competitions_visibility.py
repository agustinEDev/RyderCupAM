"""Una competicion privada no se le ensena a quien no esta dentro (BE #318).

Hasta ahora el listado devolvia todo: la pantalla de explorar mostraba la Ryder
de unos amigos a cualquiera —su nombre, sus fechas y su campo—. Privada quiere
decir invisible para quien no va a jugarla.

Quien SI la ve: su creador, y quien tiene una inscripcion en ella. Lo demas es
de otros.
"""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio


class TestWhatAStrangerSees:
    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork()

    async def _crear(self, uow, creator_id, nombre, visibility):
        create_uc = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        return await create_uc.execute(
            CreateCompetitionRequestDTO(
                name=nombre,
                start_date=date(2027, 6, 1),
                end_date=date(2027, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                visibility=visibility,
            ),
            creator_id,
        )

    async def test_a_stranger_does_not_see_a_private_one(self, uow):
        organizador = UserId(uuid4())
        desconocido = UserId(uuid4())
        await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(desconocido.value))

        assert visibles == []

    async def test_a_stranger_does_see_a_public_one(self, uow):
        organizador = UserId(uuid4())
        desconocido = UserId(uuid4())
        await self._crear(uow, organizador, "Campeonato del club", Visibility.PUBLIC)

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(desconocido.value))

        assert [str(c.name) for c in visibles] == ["Campeonato del club"]

    async def test_the_organiser_sees_their_own_private_one(self, uow):
        """Quien la monta tiene que poder encontrarla."""
        organizador = UserId(uuid4())
        await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(organizador.value))

        assert len(visibles) == 1

    async def test_the_organiser_sees_it_even_without_a_place(self, uow):
        """Organizar no es jugar: quien se retira de su torneo sigue montandolo.

        El creador se auto-inscribe al crearla, asi que sin este caso la rama
        que mira el creador no la cubre nadie.
        """
        organizador = UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        async with uow:
            suya = await uow.enrollments.find_by_user_and_competition(
                organizador, CompetitionId(creada.id)
            )
            await uow.enrollments.delete(suya.id)
            await uow.commit()

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(organizador.value))

        assert len(visibles) == 1

    async def test_somebody_enrolled_sees_it_too(self, uow):
        """Quien esta dentro la ve, aunque no sea suya."""
        organizador = UserId(uuid4())
        jugador = UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        async with uow:
            await uow.enrollments.save(
                Enrollment(
                    id=EnrollmentId.generate(),
                    competition_id=CompetitionId(creada.id),
                    user_id=jugador,
                    status=EnrollmentStatus.APPROVED,
                )
            )
            await uow.commit()

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(jugador.value))

        assert len(visibles) == 1

    async def test_somebody_enrolled_sees_it_past_one_hundred_old_enrollments(self, uow):
        """
        Given un jugador con 120 inscripciones viejas (rechazos en otras) y, la
        última, la de una privada
        When mira el listado
        Then la ve: con el límite oculto de 100 de `find_by_user`, su inscripción
        quedaba fuera y la privada desaparecía de su lista (BE #314)
        """
        organizador = UserId(uuid4())
        jugador = UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        async with uow:
            for _ in range(120):
                await uow.enrollments.save(
                    Enrollment(
                        id=EnrollmentId.generate(),
                        competition_id=CompetitionId(uuid4()),
                        user_id=jugador,
                        status=EnrollmentStatus.REJECTED,
                    )
                )
            await uow.enrollments.save(
                Enrollment(
                    id=EnrollmentId.generate(),
                    competition_id=CompetitionId(creada.id),
                    user_id=jugador,
                    status=EnrollmentStatus.APPROVED,
                )
            )
            await uow.commit()

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(jugador.value))

        assert len(visibles) == 1

    async def test_somebody_thrown_out_stops_seeing_it(self, uow):
        """Al que echan deja de verla: su fila sigue ahi, pero ya no esta dentro.

        Las inscripciones rechazadas, canceladas y retiradas no se borran, asi
        que mirar solo «tiene fila» dejaba al expulsado viendo la competicion
        privada de la que acaban de echarlo.
        """
        organizador = UserId(uuid4())
        echado = UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        async with uow:
            await uow.enrollments.save(
                Enrollment(
                    id=EnrollmentId.generate(),
                    competition_id=CompetitionId(creada.id),
                    user_id=echado,
                    status=EnrollmentStatus.REJECTED,
                )
            )
            await uow.commit()

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(echado.value))

        assert visibles == []

    async def test_somebody_invited_does_see_it(self, uow):
        """A quien le han invitado si: tiene que poder mirarla antes de decidir."""
        organizador = UserId(uuid4())
        invitado = UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        async with uow:
            await uow.enrollments.save(
                Enrollment(
                    id=EnrollmentId.generate(),
                    competition_id=CompetitionId(creada.id),
                    user_id=invitado,
                    status=EnrollmentStatus.INVITED,
                )
            )
            await uow.commit()

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(invitado.value))

        assert len(visibles) == 1

    # Release social 2 (27 oct 2026): la invitación vive en su tabla, sin fila de
    # inscripción hasta que se acepta; con ella pendiente, la privada se ve
    async def _invitar(self, uow, creada, organizador, *, user_id=None, email="x@test.com", **como):
        datos = {
            "status": InvitationStatus.PENDING,
            "expires_at": datetime.now() + timedelta(days=7),
        }
        async with uow:
            await uow.invitations.add(
                Invitation(
                    id=InvitationId.generate(),
                    competition_id=CompetitionId(creada.id),
                    inviter_id=organizador,
                    invitee_email=email,
                    invitee_user_id=user_id,
                    **{**datos, **como},
                )
            )
            await uow.commit()

    async def test_16_with_a_pending_invitation_they_see_it(self, uow):
        organizador, invitado = UserId(uuid4()), UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)
        await self._invitar(uow, creada, organizador, user_id=invitado)

        visibles = await ListCompetitionsUseCase(uow).execute(viewer_id=str(invitado.value))

        assert [c.id.value for c in visibles] == [creada.id]

    async def test_16_invited_by_their_email_they_see_it(self, uow):
        organizador, invitado = UserId(uuid4()), UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)
        await self._invitar(uow, creada, organizador, email="Ana@Test.com")

        visibles = await ListCompetitionsUseCase(uow).visibles_para(
            [await self._entidad(uow, creada)], str(invitado.value), viewer_email="ana@test.com"
        )

        assert len(visibles) == 1

    @pytest.mark.parametrize(
        "como",
        [
            {"status": InvitationStatus.DECLINED},
            {"status": InvitationStatus.CANCELLED},
            {"status": InvitationStatus.EXPIRED},
            {"expires_at": datetime.now() - timedelta(minutes=1)},
        ],
    )
    async def test_17_an_invitation_that_no_longer_counts_does_not(self, uow, como):
        organizador, invitado = UserId(uuid4()), UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)
        await self._invitar(uow, creada, organizador, user_id=invitado, **como)

        visibles = await ListCompetitionsUseCase(uow).execute(viewer_id=str(invitado.value))

        assert visibles == []

    async def test_16_somebody_else_s_invitation_does_not(self, uow):
        organizador, curioso = UserId(uuid4()), UserId(uuid4())
        creada = await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)
        await self._invitar(
            uow, creada, organizador, user_id=UserId(uuid4()), email="otro@test.com"
        )

        visibles = await ListCompetitionsUseCase(uow).visibles_para(
            [await self._entidad(uow, creada)], str(curioso.value), viewer_email="yo@test.com"
        )

        assert visibles == []

    async def _entidad(self, uow, creada):
        async with uow:
            return await uow.competitions.find_by_id(CompetitionId(creada.id))

    async def test_an_admin_sees_everything(self, uow):
        """El panel de administracion tiene que poder encontrarla para moderarla.

        Un admin puede editarla y borrarla; no verla en el listado le dejaba con
        el permiso y sin la puerta.
        """
        organizador = UserId(uuid4())
        admin = UserId(uuid4())
        await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute(viewer_id=str(admin.value), is_admin=True)

        assert len(visibles) == 1

    async def test_one_query_for_the_viewer_not_one_per_competition(self, uow):
        """Se pregunta UNA vez por quien mira, no una por competicion.

        La pantalla pide hasta 100, y con un estado por valor del filtro eso
        eran cientos de consultas por peticion, con el cuello en la CPU.
        """
        organizador = UserId(uuid4())
        curioso = UserId(uuid4())
        for i in range(5):
            await self._crear(uow, organizador, f"Ryder numero {i}", Visibility.PRIVATE)

        llamadas = []
        original = uow.enrollments.find_by_user

        async def espia(user_id, *args, **kwargs):
            llamadas.append(user_id)
            return await original(user_id, *args, **kwargs)

        uow.enrollments.find_by_user = espia
        por_competicion = []
        original_una = uow.enrollments.find_by_user_and_competition

        async def espia_una(user_id, competition_id, *args, **kwargs):
            por_competicion.append(competition_id)
            return await original_una(user_id, competition_id, *args, **kwargs)

        uow.enrollments.find_by_user_and_competition = espia_una

        uc = ListCompetitionsUseCase(uow)
        await uc.execute(viewer_id=str(curioso.value))

        assert len(por_competicion) == 0, "una consulta por competicion es un N+1"
        assert len(llamadas) == 1

    async def test_without_saying_who_looks_nothing_private_shows(self, uow):
        """Sin saber quien mira, se ensena solo lo publico."""
        organizador = UserId(uuid4())
        await self._crear(uow, organizador, "Ryder de los amigos", Visibility.PRIVATE)
        await self._crear(uow, organizador, "Campeonato del club", Visibility.PUBLIC)

        uc = ListCompetitionsUseCase(uow)
        visibles = await uc.execute()

        assert [str(c.name) for c in visibles] == ["Campeonato del club"]
