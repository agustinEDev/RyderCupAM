"""Tests para RespondToInvitationUseCase."""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
)
from src.modules.competition.application.exceptions import (
    InvitationNotFoundError,
    NotInviteeError,
)
from src.modules.competition.application.services.genero_obligatorio import GenderRequiredError
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import (
    InvitationStatus,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.helpers import set_competition_status

pytestmark = pytest.mark.asyncio


class TestRespondToInvitationUseCase:
    """Tests para responder a una invitacion."""

    @pytest.fixture
    def comp_uow(self):
        return CompetitionInMemoryUoW()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _create_user(
        self,
        user_uow,
        email="user@test.com",
        first_name="Test",
        last_name="User",
        gender=Gender.MALE,
    ):
        user = User.create(
            first_name=first_name,
            last_name=last_name,
            email_str=email,
            plain_password="SecureP@ssw0rd123",
            gender=gender,
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    async def _create_active_competition(self, comp_uow, creator_id, max_players=24):
        create_uc = CreateCompetitionUseCase(comp_uow, LocationBuilder(comp_uow.countries))
        request = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=max_players,
        )
        created = await create_uc.execute(request, creator_id)


        return created

    async def _create_pending_invitation(
        self, comp_uow, competition_id, inviter_id, invitee_user_id, invitee_email
    ):
        """Helper: crea una invitacion PENDING en el repo."""
        invitation = Invitation.create(
            id=InvitationId.generate(),
            competition_id=CompetitionId(competition_id),
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            invitee_user_id=invitee_user_id,
        )
        async with comp_uow:
            await comp_uow.invitations.add(invitation)
            await comp_uow.commit()
        return invitation

    async def test_accept_invitation_successfully(self, comp_uow, user_uow):
        """Happy path: aceptar invitacion crea enrollment."""
        creator = await self._create_user(
            user_uow, email="creator@test.com", first_name="Creator", last_name="Boss"
        )
        invitee = await self._create_user(
            user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player"
        )
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="ACCEPT",
        )
        result = await uc.execute(request)

        assert result.status == "ACCEPTED"
        assert result.enrollment_id is not None
        assert result.inviter_name == "Creator Boss"
        assert result.invitee_name == "Invitee Player"

    # ==================== Con la inscripción cerrada (#710, 24 sep) ====================

    async def _pendiente_en_una_cerrada(self, comp_uow, user_uow):
        """Una invitación de antes del cambio, que se quedó pendiente al cerrar."""
        creator = await self._create_user(user_uow, email="c@test.com")
        invitee = await self._create_user(user_uow, email="i@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)
        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "i@test.com"
        )
        await set_competition_status(comp_uow, created.id, "CLOSED")
        return invitation, invitee

    async def test_i6_aceptarla_cerrada_la_deja_sin_plaza(self, comp_uow, user_uow):
        invitation, invitee = await self._pendiente_en_una_cerrada(comp_uow, user_uow)
        uc = RespondToInvitationUseCase(comp_uow, user_uow)

        with pytest.raises(InvalidInvitationStatusViolation, match="plazas"):
            await uc.execute(
                RespondInvitationRequestDTO(
                    invitation_id=invitation.id.value, user_id=invitee.id.value, action="ACCEPT"
                )
            )

        async with comp_uow:
            guardada = await comp_uow.invitations.find_by_id(invitation.id)
            inscripcion = await comp_uow.enrollments.find_by_user_and_competition(
                invitee.id, invitation.competition_id
            )
        assert guardada.status == InvitationStatus.NO_ROOM
        assert inscripcion is None

    async def test_i6b_otro_usuario_no_la_deja_sin_plaza(self, comp_uow, user_uow):
        """Solo el invitado responde: con el id de otra no se le cambia el estado."""
        invitation, _ = await self._pendiente_en_una_cerrada(comp_uow, user_uow)
        intruso = await self._create_user(user_uow, email="x@test.com")
        uc = RespondToInvitationUseCase(comp_uow, user_uow)

        with pytest.raises(NotInviteeError):
            await uc.execute(
                RespondInvitationRequestDTO(
                    invitation_id=invitation.id.value, user_id=intruso.id.value, action="ACCEPT"
                )
            )

        async with comp_uow:
            guardada = await comp_uow.invitations.find_by_id(invitation.id)
        assert guardada.status == InvitationStatus.PENDING

    async def test_i6c_una_ya_sin_plaza_lo_dice_en_su_idioma(self, comp_uow, user_uow):
        invitation, invitee = await self._pendiente_en_una_cerrada(comp_uow, user_uow)
        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        pedir = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value, user_id=invitee.id.value, action="ACCEPT"
        )
        with pytest.raises(InvalidInvitationStatusViolation):
            await uc.execute(pedir)

        # La segunda vez ya está NO_ROOM: el mismo motivo, no «Invitation is in status…»
        with pytest.raises(InvalidInvitationStatusViolation, match="No quedan plazas"):
            await uc.execute(pedir)

    async def test_aceptar_bloquea_la_fila_de_la_competicion(self, comp_uow, user_uow):
        """Contra el cierre a la vez (CodeRabbit en la #380): con la fila
        bloqueada, uno espera al otro y lee el estado de verdad."""
        creator = await self._create_user(user_uow, email="lc@test.com")
        invitee = await self._create_user(user_uow, email="li@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)
        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "li@test.com"
        )
        comp_uow.competitions.find_by_id_for_update = AsyncMock(
            wraps=comp_uow.competitions.find_by_id_for_update
        )

        await RespondToInvitationUseCase(comp_uow, user_uow).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitation.id.value, user_id=invitee.id.value, action="ACCEPT"
            )
        )

        comp_uow.competitions.find_by_id_for_update.assert_awaited()

    async def test_i7_rechazarla_cerrada_sigue_valiendo(self, comp_uow, user_uow):
        invitation, invitee = await self._pendiente_en_una_cerrada(comp_uow, user_uow)
        uc = RespondToInvitationUseCase(comp_uow, user_uow)

        result = await uc.execute(
            RespondInvitationRequestDTO(
                invitation_id=invitation.id.value, user_id=invitee.id.value, action="DECLINE"
            )
        )

        assert result.status == "DECLINED"

    # ==================== El género es obligatorio para apuntarse (#710) ====================

    async def _invitado_sin_genero(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="c2@test.com")
        invitee = await self._create_user(user_uow, email="sg@test.com", gender=None)
        created = await self._create_active_competition(comp_uow, creator.id)
        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "sg@test.com"
        )
        return invitation, invitee

    async def test_g4_sin_genero_no_se_acepta_y_la_invitacion_sigue_ahi(self, comp_uow, user_uow):
        invitation, invitee = await self._invitado_sin_genero(comp_uow, user_uow)
        uc = RespondToInvitationUseCase(comp_uow, user_uow)

        with pytest.raises(GenderRequiredError, match="tu género en tu perfil"):
            await uc.execute(
                RespondInvitationRequestDTO(
                    invitation_id=invitation.id.value, user_id=invitee.id.value, action="ACCEPT"
                )
            )

        async with comp_uow:
            guardada = await comp_uow.invitations.find_by_id(invitation.id)
            inscripcion = await comp_uow.enrollments.find_by_user_and_competition(
                invitee.id, invitation.competition_id
            )
        # Pendiente: la acepta en cuanto rellene su perfil
        assert guardada.status == InvitationStatus.PENDING
        assert inscripcion is None

    async def test_g5_sin_genero_se_puede_rechazar(self, comp_uow, user_uow):
        invitation, invitee = await self._invitado_sin_genero(comp_uow, user_uow)
        uc = RespondToInvitationUseCase(comp_uow, user_uow)

        result = await uc.execute(
            RespondInvitationRequestDTO(
                invitation_id=invitation.id.value, user_id=invitee.id.value, action="DECLINE"
            )
        )

        assert result.status == "DECLINED"

    async def test_decline_invitation_successfully(self, comp_uow, user_uow):
        """Happy path: rechazar invitacion."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="DECLINE",
        )
        result = await uc.execute(request)

        assert result.status == "DECLINED"
        assert result.enrollment_id is None

    async def test_should_raise_invitation_not_found(self, comp_uow, user_uow):
        """Invitacion inexistente lanza InvitationNotFoundError."""
        invitee = await self._create_user(user_uow, email="invitee@test.com")

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=uuid4(),
            user_id=invitee.id.value,
            action="ACCEPT",
        )

        with pytest.raises(InvitationNotFoundError):
            await uc.execute(request)

    async def test_should_raise_not_invitee(self, comp_uow, user_uow):
        """Usuario que no es invitee lanza NotInviteeError."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=other.id.value,
            action="ACCEPT",
        )

        with pytest.raises(NotInviteeError):
            await uc.execute(request)

    async def test_should_raise_invalid_status_for_already_accepted(self, comp_uow, user_uow):
        """Invitacion ya aceptada lanza InvalidInvitationStatusViolation."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        # Crear invitacion ya ACCEPTED
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(created.id),
            inviter_id=creator.id,
            invitee_email="invitee@test.com",
            invitee_user_id=invitee.id,
            status=InvitationStatus.ACCEPTED,
            expires_at=datetime.now() + timedelta(days=7),
            responded_at=datetime.now(),
        )
        async with comp_uow:
            await comp_uow.invitations.add(invitation)
            await comp_uow.commit()

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="ACCEPT",
        )

        with pytest.raises(InvalidInvitationStatusViolation):
            await uc.execute(request)

    async def test_should_raise_invalid_action(self, comp_uow, user_uow):
        """Accion invalida lanza ValueError."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="INVALID",
        )

        with pytest.raises(ValueError, match="Invalid action"):
            await uc.execute(request)

    async def test_accept_by_email_match(self, comp_uow, user_uow):
        """Invitee puede responder si el email coincide (sin invitee_user_id)."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        # Invitacion sin invitee_user_id (solo email)
        invitation = Invitation.create(
            id=InvitationId.generate(),
            competition_id=CompetitionId(created.id),
            inviter_id=creator.id,
            invitee_email="invitee@test.com",
            invitee_user_id=None,
        )
        async with comp_uow:
            await comp_uow.invitations.add(invitation)
            await comp_uow.commit()

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="ACCEPT",
        )
        result = await uc.execute(request)
        assert result.status == "ACCEPTED"
        assert result.enrollment_id is not None
