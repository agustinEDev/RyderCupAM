"""Tests para SendInvitationByEmailUseCase."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    SendInvitationByEmailRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    DuplicateInvitationViolation,
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

pytestmark = pytest.mark.asyncio


class TestSendInvitationByEmailUseCase:
    """Tests para enviar invitacion por email."""

    @pytest.fixture
    def comp_uow(self):
        return CompetitionInMemoryUoW()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _create_user(
        self, user_uow, email="user@test.com", first_name="Test", last_name="User"
    ):
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
        create_uc = CreateCompetitionUseCase(comp_uow, LocationBuilder(comp_uow.countries))
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
        create_uc = CreateCompetitionUseCase(comp_uow, LocationBuilder(comp_uow.countries))
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
        """BE #319, el gemelo por correo: invitar en DRAFT abre las inscripciones."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)
        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.DRAFT

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        result = await uc.execute(
            SendInvitationByEmailRequestDTO(
                competition_id=created.id,
                inviter_id=creator.id.value,
                invitee_email="invitee@test.com",
            )
        )

        assert result.status == "PENDING"
        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.ACTIVE

    async def test_a_stranger_does_not_open_anything(self, comp_uow, user_uow):
        """Quien no puede invitar tampoco abre las inscripciones de rebote."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        with pytest.raises(NotCompetitionCreatorError):
            await uc.execute(
                SendInvitationByEmailRequestDTO(
                    competition_id=created.id,
                    inviter_id=other.id.value,
                    invitee_email="quien.sea@test.com",
                )
            )

        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.DRAFT

    async def test_an_admin_invites_as_the_creator_would(self, comp_uow, user_uow):
        """Un admin invita como lo haria el creador, borrador incluido.

        Decidido el 20 sep: no hay regla aparte para los administradores. Si
        invitan a un borrador, se abre, igual que si lo hiciera su creador.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        await self._create_user(user_uow, email="invitee@test.com")
        admin = await self._create_user(user_uow, email="admin@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)
        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        result = await uc.execute(SendInvitationByEmailRequestDTO(
                competition_id=created.id,
                inviter_id=admin.id.value,
                invitee_email="invitee@test.com",
            ), is_admin=True)

        assert result.status == "PENDING"
        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.ACTIVE

    async def test_second_invitation_leaves_the_status_alone(self, comp_uow, user_uow):
        """Ya abierta, invitar no vuelve a tocar el estado."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        await self._create_user(user_uow, email="uno@test.com")
        await self._create_user(user_uow, email="dos@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        for correo in ("uno@test.com", "dos@test.com"):
            await uc.execute(
                SendInvitationByEmailRequestDTO(
                    competition_id=created.id,
                    inviter_id=creator.id.value,
                    invitee_email=correo,
                )
            )

        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.ACTIVE

    async def test_a_failed_invitation_does_not_leave_it_open(self, comp_uow, user_uow):
        """Si la invitacion no sale adelante, la competicion sigue en DRAFT.

        En este camino hay mas formas de fallar antes de guardar la invitacion
        —un correo que no es de nadie, un duplicado, alguien ya inscrito—, asi
        que es donde mas importa que abrir sea lo ultimo que pasa.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        with pytest.raises(SelfInvitationViolation):
            await uc.execute(
                SendInvitationByEmailRequestDTO(
                    competition_id=created.id,
                    inviter_id=creator.id.value,
                    invitee_email="creator@test.com",
                )
            )

        assert await self._status_of(comp_uow, created.id) == CompetitionStatus.DRAFT

    async def test_the_opening_gets_saved(self, comp_uow, user_uow):
        """La apertura se persiste, no solo se cambia en memoria.

        El repositorio en memoria guarda la MISMA instancia que devuelve, asi
        que un `update` olvidado pasaria desapercibido aqui y no se escribiria
        nada en Postgres. Por eso se mira que la competicion llegue a guardarse.
        """
        creator = await self._create_user(user_uow, email="creator@test.com")
        await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_draft_competition(comp_uow, creator.id)

        guardadas = []
        original = comp_uow.competitions.update

        async def espia(competition):
            guardadas.append(competition.status)
            await original(competition)

        comp_uow.competitions.update = espia

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        await uc.execute(
            SendInvitationByEmailRequestDTO(
                competition_id=created.id,
                inviter_id=creator.id.value,
                invitee_email="invitee@test.com",
            )
        )

        assert CompetitionStatus.ACTIVE in guardadas

    async def test_should_send_invitation_to_registered_user(self, comp_uow, user_uow):
        """Happy path: enviar invitacion a un email de usuario registrado."""
        creator = await self._create_user(
            user_uow, email="creator@test.com", first_name="Creator", last_name="Boss"
        )
        invitee = await self._create_user(
            user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player"
        )
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="invitee@test.com",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        assert result.invitee_email == "invitee@test.com"
        assert result.invitee_user_id == invitee.id.value
        assert result.invitee_name == "Invitee Player"

    async def test_should_send_invitation_to_unregistered_email(self, comp_uow, user_uow):
        """Happy path: invitacion a email no registrado (invitee_user_id=None)."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="unregistered@test.com",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        assert result.invitee_email == "unregistered@test.com"
        assert result.invitee_user_id is None
        assert result.invitee_name is None

    async def test_should_raise_competition_not_found(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=uuid4(),
            inviter_id=creator.id.value,
            invitee_email="test@test.com",
        )

        with pytest.raises(CompetitionNotFoundError):
            await uc.execute(request)

    async def test_should_raise_not_creator(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=other.id.value,
            invitee_email="someone@test.com",
        )

        with pytest.raises(NotCompetitionCreatorError):
            await uc.execute(request)

    async def test_should_raise_self_invitation(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="creator@test.com",
        )

        with pytest.raises(SelfInvitationViolation):
            await uc.execute(request)

    async def test_should_raise_already_enrolled(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(created.id),
            user_id=invitee.id,
        )
        async with comp_uow:
            await comp_uow.enrollments.add(enrollment)
            await comp_uow.commit()

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="invitee@test.com",
        )

        with pytest.raises(AlreadyEnrolledInvitationViolation):
            await uc.execute(request)

    async def test_should_raise_duplicate_invitation(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="unregistered@test.com",
        )

        await uc.execute(request)

        with pytest.raises(DuplicateInvitationViolation):
            await uc.execute(request)

    async def test_should_send_with_personal_message(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="new@test.com",
            personal_message="Welcome!",
        )
        result = await uc.execute(request)
        assert result.personal_message == "Welcome!"

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
        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="extra@test.com",
        )

        with pytest.raises(InvitationRateLimitViolation):
            await uc.execute(request)

    async def test_should_call_email_service_for_registered_user(self, comp_uow, user_uow):
        """Email service se llama con invitee_name para usuario registrado."""
        creator = await self._create_user(
            user_uow, email="creator@test.com", first_name="Creator", last_name="Boss"
        )
        await self._create_user(
            user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player"
        )
        created = await self._create_active_competition(comp_uow, creator.id)

        mock_email = AsyncMock()
        mock_email.send_invitation_email = AsyncMock(return_value=True)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow, email_service=mock_email)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="invitee@test.com",
            personal_message="Welcome!",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        mock_email.send_invitation_email.assert_called_once()
        call_kwargs = mock_email.send_invitation_email.call_args[1]
        assert call_kwargs["to_email"] == "invitee@test.com"
        assert call_kwargs["invitee_name"] == "Invitee Player"
        assert call_kwargs["inviter_name"] == "Creator Boss"
        assert call_kwargs["competition_name"] == "Test Cup"
        assert call_kwargs["personal_message"] == "Welcome!"

    async def test_should_call_email_service_for_unregistered_user(self, comp_uow, user_uow):
        """Email service se llama con invitee_name=None para email no registrado."""
        creator = await self._create_user(
            user_uow, email="creator@test.com", first_name="Creator", last_name="Boss"
        )
        created = await self._create_active_competition(comp_uow, creator.id)

        mock_email = AsyncMock()
        mock_email.send_invitation_email = AsyncMock(return_value=True)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow, email_service=mock_email)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="unknown@test.com",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        mock_email.send_invitation_email.assert_called_once()
        call_kwargs = mock_email.send_invitation_email.call_args[1]
        assert call_kwargs["to_email"] == "unknown@test.com"
        assert call_kwargs["invitee_name"] is None

    async def test_should_create_invitation_even_if_email_fails(self, comp_uow, user_uow):
        """La invitacion se crea aunque el email falle."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        mock_email = AsyncMock()
        mock_email.send_invitation_email = AsyncMock(side_effect=Exception("Network error"))

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow, email_service=mock_email)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="someone@test.com",
        )
        result = await uc.execute(request)

        # Invitacion creada a pesar del error de email
        assert result.status == "PENDING"
        assert result.invitee_email == "someone@test.com"
