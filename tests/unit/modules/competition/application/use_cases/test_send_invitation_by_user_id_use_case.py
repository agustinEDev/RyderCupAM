"""Tests para SendInvitationByUserIdUseCase."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InviteeNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    DuplicateInvitationViolation,
    InvitationCompetitionStatusViolation,
    InvitationRateLimitViolation,
    SelfInvitationViolation,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio


class TestSendInvitationByUserIdUseCase:
    """Tests para enviar invitacion por user_id."""

    @pytest.fixture
    def comp_uow(self):
        return CompetitionInMemoryUoW()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _create_user(
        self, user_uow, email="user@test.com", first_name="Test", last_name="User"
    ):
        """Helper: crea un usuario en user_uow."""
        user = User.create(
            first_name=first_name,
            last_name=last_name,
            email_str=email,
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    async def _create_active_competition(self, comp_uow, creator_id):
        """Helper: crea y activa una competicion."""
        create_uc = CreateCompetitionUseCase(
            comp_uow, LocationBuilder(comp_uow.countries), USUARIOS_CON_GENERO
        )
        request = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=24,
        )
        created = await create_uc.execute(request, creator_id)


        return created

    async def _create_draft_competition(self, comp_uow, creator_id):
        """Helper: crea una competicion que todavia espera su hora.

        Desde BE #332 una competicion nace con las inscripciones abiertas salvo
        que tenga apertura programada, asi que la unica que sigue en DRAFT —y
        por tanto la unica a la que una invitacion puede abrirle nada— es esa.
        """
        create_uc = CreateCompetitionUseCase(
            comp_uow, LocationBuilder(comp_uow.countries), USUARIOS_CON_GENERO
        )
        request = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=24,
            enrollment_opens_days_before=5,
        )
        return await create_uc.execute(request, creator_id)

    async def _status_of(self, comp_uow, competition_id):
        async with comp_uow:
            competition = await comp_uow.competitions.find_by_id(CompetitionId(competition_id))
            return competition.status

    async def test_first_invitation_opens_enrollment(self, comp_uow, user_uow):
        """BE #319: invitar a una competicion en DRAFT abre las inscripciones.

        Nadie deberia tener que pulsar un boton cuyo unico trabajo es mover un
        estado: el torneo arranca cuando se invita a la primera persona.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)
        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.DRAFT

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        result = await uc.execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=created.id,
                inviter_id=creator.id.value,
                invitee_user_id=invitee.id.value,
            )
        )

        assert result.status == "PENDING"
        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.ACTIVE

    async def test_an_admin_invites_as_the_creator_would(self, comp_uow, user_uow):
        """Un admin invita como lo haria el creador, borrador incluido.

        Decidido el 20 sep: no hay regla aparte para los administradores. Si
        invitan a un borrador, se abre, igual que si lo hiciera su creador.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        admin = await self._create_user(user_uow, email="admin@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)
        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        result = await uc.execute(SendInvitationByUserIdRequestDTO(
                competition_id=created.id,
                inviter_id=admin.id.value,
                invitee_user_id=invitee.id.value,
            ), is_admin=True)

        assert result.status == "PENDING"
        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.ACTIVE

    async def test_the_opening_gets_saved(self, comp_uow, user_uow):
        """La apertura se persiste, no solo se cambia en memoria.

        El repositorio en memoria guarda la MISMA instancia que devuelve, asi
        que un `update` olvidado pasaria desapercibido aqui y no se escribiria
        nada en Postgres. Por eso se mira que la competicion llegue a guardarse.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        guardadas = []
        original = comp_uow.competitions.update

        async def espia(competition):
            guardadas.append(competition.status)
            await original(competition)

        comp_uow.competitions.update = espia

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        await uc.execute(SendInvitationByUserIdRequestDTO(
                competition_id=created.id,
                inviter_id=creator.id.value,
                invitee_user_id=invitee.id.value,
            ))

        assert CompetitionStatus.ACTIVE in guardadas

    async def test_second_invitation_leaves_the_status_alone(self, comp_uow, user_uow):
        """Ya abierta, invitar no vuelve a tocar el estado."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        primero = await self._create_user(user_uow, email="uno@test.com")
        segundo = await self._create_user(user_uow, email="dos@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        for invitee in (primero, segundo):
            await uc.execute(
                SendInvitationByUserIdRequestDTO(
                    competition_id=created.id,
                    inviter_id=creator.id.value,
                    invitee_user_id=invitee.id.value,
                )
            )

        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.ACTIVE

    async def test_a_stranger_does_not_open_anything(self, comp_uow, user_uow):
        """Quien no puede invitar tampoco abre las inscripciones de rebote."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        with pytest.raises(NotCompetitionCreatorError):
            await uc.execute(
                SendInvitationByUserIdRequestDTO(
                    competition_id=created.id,
                    inviter_id=other.id.value,
                    invitee_user_id=invitee.id.value,
                )
            )

        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.DRAFT

    async def test_a_failed_invitation_does_not_leave_it_open(self, comp_uow, user_uow):
        """Si la invitacion no sale adelante, la competicion sigue en DRAFT.

        Abrir las inscripciones y luego fallar dejaria el torneo abierto sin que
        nadie haya sido invitado, que es medio arranque.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        with pytest.raises(InviteeNotFoundError):
            await uc.execute(
                SendInvitationByUserIdRequestDTO(
                    competition_id=created.id,
                    inviter_id=creator.id.value,
                    invitee_user_id=uuid4(),
                )
            )

        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.DRAFT

    async def test_should_send_invitation_successfully(self, comp_uow, user_uow):
        """Happy path: enviar invitacion a un usuario registrado."""
        creator = await self._create_user(
            user_uow, email="creator@test.com", first_name="Creator", last_name="User"
        )
        invitee = await self._create_user(
            user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player"
        )
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=invitee.id.value,
            personal_message="Join my tournament!",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        assert result.invitee_email == "invitee@test.com"
        assert result.invitee_user_id == invitee.id.value
        assert result.personal_message == "Join my tournament!"
        assert result.competition_name == "Test Cup"
        assert result.inviter_name == "Creator User"
        assert result.invitee_name == "Invitee Player"

    async def test_the_email_names_the_inviter_as_in_this_competition(self, comp_uow, user_uow):
        """Con alias pero sin pedirlo aquí: su nombre legal, también en el correo (#710)."""
        creator = await self._create_user(
            user_uow, email="c_alias@test.com", first_name="Agustin", last_name="Estevez"
        )
        async with user_uow:
            creator.update_profile(alias="Trinx")
            await user_uow.users.save(creator)
        invitee = await self._create_user(
            user_uow, email="i_alias@test.com", first_name="Invitee", last_name="Player"
        )
        created = await self._create_active_competition(comp_uow, creator.id)
        mock_email = AsyncMock()
        mock_email.send_invitation_email = AsyncMock(return_value=True)

        result = await SendInvitationByUserIdUseCase(
            comp_uow, user_uow, email_service=mock_email
        ).execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=created.id,
                inviter_id=creator.id.value,
                invitee_user_id=invitee.id.value,
            )
        )

        assert result.inviter_name == "Agustin Estevez"
        assert mock_email.send_invitation_email.call_args[1]["inviter_name"] == "Agustin Estevez"

    async def test_should_raise_competition_not_found(self, comp_uow, user_uow):
        """Competition inexistente lanza CompetitionNotFoundError."""
        creator = await self._create_user(user_uow, email="creator@test.com")

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=uuid4(),
            inviter_id=creator.id.value,
            invitee_user_id=uuid4(),
        )

        with pytest.raises(CompetitionNotFoundError):
            await uc.execute(request)

    async def test_should_raise_not_creator(self, comp_uow, user_uow):
        """No-creator lanza NotCompetitionCreatorError."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=other.id.value,
            invitee_user_id=invitee.id.value,
        )

        with pytest.raises(NotCompetitionCreatorError):
            await uc.execute(request)

    async def test_should_succeed_when_admin_not_creator(self, comp_uow, user_uow):
        """Admin (no creador) puede enviar invitacion con is_admin=True."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        admin = await self._create_user(user_uow, email="admin@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=admin.id.value,
            invitee_user_id=invitee.id.value,
        )

        result = await uc.execute(request, is_admin=True)

        assert result.status == "PENDING"

    async def test_should_raise_invitee_not_found(self, comp_uow, user_uow):
        """Invitee inexistente lanza InviteeNotFoundError."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=uuid4(),
        )

        with pytest.raises(InviteeNotFoundError):
            await uc.execute(request)

    async def test_should_raise_self_invitation(self, comp_uow, user_uow):
        """Auto-invitacion lanza SelfInvitationViolation."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=creator.id.value,
        )

        with pytest.raises(SelfInvitationViolation):
            await uc.execute(request)

    async def test_should_raise_already_enrolled(self, comp_uow, user_uow):
        """Invitee ya inscrito lanza AlreadyEnrolledInvitationViolation."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        # Crear enrollment aprobado para invitee
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(created.id),
            user_id=invitee.id,
        )
        async with comp_uow:
            await comp_uow.enrollments.add(enrollment)
            await comp_uow.commit()

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=invitee.id.value,
        )

        with pytest.raises(AlreadyEnrolledInvitationViolation):
            await uc.execute(request)

    async def test_should_raise_duplicate_invitation(self, comp_uow, user_uow):
        """Segunda invitacion PENDING al mismo email lanza DuplicateInvitationViolation."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=invitee.id.value,
        )

        # Primera invitacion
        await uc.execute(request)

        # Segunda invitacion al mismo usuario
        with pytest.raises(DuplicateInvitationViolation):
            await uc.execute(request)

    async def test_should_raise_competition_status_violation_for_cancelled(
        self, comp_uow, user_uow
    ):
        """Una competicion cancelada no admite invitaciones.

        Antes tampoco las admitia en DRAFT; eso cambio con BE #319, porque
        invitar es justamente lo que abre el torneo. Lo que sigue cerrado son
        los estados de los que ya no se vuelve.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        async with comp_uow:
            competition = await comp_uow.competitions.find_by_id(CompetitionId(created.id))
            competition.cancel("se queda sin jugadores")
            await comp_uow.competitions.update(competition)
            await comp_uow.commit()

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        send_req = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=invitee.id.value,
        )

        with pytest.raises(InvitationCompetitionStatusViolation):
            await uc.execute(send_req)

    async def test_should_send_without_personal_message(self, comp_uow, user_uow):
        """Invitacion sin mensaje personal es valida."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=invitee.id.value,
        )
        result = await uc.execute(request)
        assert result.personal_message is None

    async def test_should_raise_rate_limit_when_max_players_reached(self, comp_uow, user_uow):
        """Exceder max_players invitaciones por hora lanza InvitationRateLimitViolation."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)
        competition_id = CompetitionId(created.id)

        # Crear 24 invitaciones (max_players=24) directamente en repo
        for i in range(24):
            inv = Invitation.create(
                id=InvitationId.generate(),
                competition_id=competition_id,
                inviter_id=creator.id,
                invitee_email=f"player{i}@test.com",
            )
            async with comp_uow:
                await comp_uow.invitations.add(inv)
                await comp_uow.commit()

        # La invitacion 25 debe fallar por rate limit
        new_invitee = await self._create_user(user_uow, email="extra@test.com")

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=new_invitee.id.value,
        )

        with pytest.raises(InvitationRateLimitViolation):
            await uc.execute(request)

    async def test_should_call_email_service_on_success(self, comp_uow, user_uow):
        """Email service se llama con parametros correctos al enviar invitacion."""
        creator = await self._create_user(
            user_uow, email="creator@test.com", first_name="Creator", last_name="User"
        )
        invitee = await self._create_user(
            user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player"
        )
        created = await self._create_active_competition(comp_uow, creator.id)

        mock_email = AsyncMock()
        mock_email.send_invitation_email = AsyncMock(return_value=True)

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow, email_service=mock_email)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=invitee.id.value,
            personal_message="Join us!",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        mock_email.send_invitation_email.assert_called_once()
        call_kwargs = mock_email.send_invitation_email.call_args[1]
        assert call_kwargs["to_email"] == "invitee@test.com"
        assert call_kwargs["invitee_name"] == "Invitee Player"
        assert call_kwargs["inviter_name"] == "Creator User"
        assert call_kwargs["competition_name"] == "Test Cup"
        assert call_kwargs["personal_message"] == "Join us!"
        assert call_kwargs["expires_at"] is not None

    async def test_should_create_invitation_even_if_email_fails(self, comp_uow, user_uow):
        """La invitacion se crea aunque el email falle."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        mock_email = AsyncMock()
        mock_email.send_invitation_email = AsyncMock(side_effect=Exception("SMTP error"))

        uc = SendInvitationByUserIdUseCase(comp_uow, user_uow, email_service=mock_email)
        request = SendInvitationByUserIdRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_user_id=invitee.id.value,
        )
        result = await uc.execute(request)

        # Invitacion creada exitosamente a pesar del error de email
        assert result.status == "PENDING"
        assert result.invitee_email == "invitee@test.com"
