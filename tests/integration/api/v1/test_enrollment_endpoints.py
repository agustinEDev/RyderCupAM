# -*- coding: utf-8 -*-
"""
Tests E2E para Enrollment Endpoints.

Tests de integración que verifican el flujo completo de los endpoints
de inscripciones incluyendo autenticación, validaciones y persistencia.
"""

import pytest
from httpx import AsyncClient
from datetime import date, timedelta

from tests.conftest import (
    create_authenticated_user,
    create_competition,
    activate_competition,
)


class TestRequestEnrollment:
    """Tests para POST /api/v1/competitions/{id}/enrollments"""

    @pytest.mark.asyncio
    async def test_request_enrollment_success(self, client: AsyncClient):
        """Solicitar inscripción en competición ACTIVE retorna 201."""
        # Arrange
        creator = await create_authenticated_user(
            client, "creator@test.com", "Pass123!", "Creator", "User"
        )
        player = await create_authenticated_user(
            client, "player@test.com", "Pass123!", "Player", "User"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        # Act
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "REQUESTED"
        assert data["user_id"] == player["user_id"]

    @pytest.mark.asyncio
    async def test_request_enrollment_draft_competition_returns_400(self, client: AsyncClient):
        """Solicitar inscripción en competición DRAFT retorna 400."""
        creator = await create_authenticated_user(
            client, "creator2@test.com", "Pass123!", "Creator", "Two"
        )
        player = await create_authenticated_user(
            client, "player2@test.com", "Pass123!", "Player", "Two"
        )

        comp = await create_competition(client, creator["token"])
        # No activamos la competición

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_request_enrollment_duplicate_returns_409(self, client: AsyncClient):
        """Solicitar inscripción duplicada retorna 409."""
        creator = await create_authenticated_user(
            client, "creator3@test.com", "Pass123!", "Creator", "Three"
        )
        player = await create_authenticated_user(
            client, "player3@test.com", "Pass123!", "Player", "Three"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        # Primera solicitud
        await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        # Segunda solicitud (duplicada)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        assert response.status_code == 409


class TestDirectEnrollPlayer:
    """Tests para POST /api/v1/competitions/{id}/enrollments/direct"""

    @pytest.mark.asyncio
    async def test_direct_enroll_success(self, client: AsyncClient):
        """Creador inscribe directamente a jugador retorna 201."""
        creator = await create_authenticated_user(
            client, "creator4@test.com", "Pass123!", "Creator", "Four"
        )
        player = await create_authenticated_user(
            client, "player4@test.com", "Pass123!", "Player", "Four"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"user_id": player["user_id"]},
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_direct_enroll_not_creator_returns_403(self, client: AsyncClient):
        """No creador intentando inscribir directamente retorna 403."""
        creator = await create_authenticated_user(
            client, "creator5@test.com", "Pass123!", "Creator", "Five"
        )
        other = await create_authenticated_user(
            client, "other5@test.com", "Pass123!", "Other", "Five"
        )
        player = await create_authenticated_user(
            client, "player5@test.com", "Pass123!", "Player", "Five"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"user_id": player["user_id"]},
            headers={"Authorization": f"Bearer {other['token']}"}
        )

        assert response.status_code == 403


class TestListEnrollments:
    """Tests para GET /api/v1/competitions/{id}/enrollments"""

    @pytest.mark.asyncio
    async def test_list_enrollments_empty(self, client: AsyncClient):
        """Listar inscripciones vacío retorna lista vacía."""
        creator = await create_authenticated_user(
            client, "creator6@test.com", "Pass123!", "Creator", "Six"
        )

        comp = await create_competition(client, creator["token"])

        response = await client.get(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_enrollments_with_data(self, client: AsyncClient):
        """Listar inscripciones retorna las existentes."""
        creator = await create_authenticated_user(
            client, "creator7@test.com", "Pass123!", "Creator", "Seven"
        )
        player1 = await create_authenticated_user(
            client, "player7a@test.com", "Pass123!", "Player", "7A"
        )
        player2 = await create_authenticated_user(
            client, "player7b@test.com", "Pass123!", "Player", "7B"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        # Crear 2 inscripciones
        await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player1['token']}"}
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player2['token']}"}
        )

        response = await client.get(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 200
        assert len(response.json()) == 2


class TestApproveRejectEnrollment:
    """Tests para POST /api/v1/enrollments/{id}/approve y /reject"""

    @pytest.mark.asyncio
    async def test_approve_enrollment_success(self, client: AsyncClient):
        """Aprobar inscripción cambia estado a APPROVED."""
        creator = await create_authenticated_user(
            client, "creator8@test.com", "Pass123!", "Creator", "Eight"
        )
        player = await create_authenticated_user(
            client, "player8@test.com", "Pass123!", "Player", "Eight"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        # Solicitar inscripción
        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        # Aprobar
        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/approve",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_reject_enrollment_success(self, client: AsyncClient):
        """Rechazar inscripción cambia estado a REJECTED."""
        creator = await create_authenticated_user(
            client, "creator9@test.com", "Pass123!", "Creator", "Nine"
        )
        player = await create_authenticated_user(
            client, "player9@test.com", "Pass123!", "Player", "Nine"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/reject",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"


class TestCancelWithdrawEnrollment:
    """Tests para POST /api/v1/enrollments/{id}/cancel y /withdraw"""

    @pytest.mark.asyncio
    async def test_cancel_enrollment_success(self, client: AsyncClient):
        """Cancelar inscripción propia cambia estado a CANCELLED."""
        creator = await create_authenticated_user(
            client, "creator10@test.com", "Pass123!", "Creator", "Ten"
        )
        player = await create_authenticated_user(
            client, "player10@test.com", "Pass123!", "Player", "Ten"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/cancel",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_withdraw_enrollment_success(self, client: AsyncClient):
        """Retirarse de inscripción aprobada cambia estado a WITHDRAWN."""
        creator = await create_authenticated_user(
            client, "creator11@test.com", "Pass123!", "Creator", "Eleven"
        )
        player = await create_authenticated_user(
            client, "player11@test.com", "Pass123!", "Player", "Eleven"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        # Solicitar y aprobar
        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        await client.post(
            f"/api/v1/enrollments/{enrollment_id}/approve",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        # Retirarse
        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/withdraw",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "WITHDRAWN"

    @pytest.mark.asyncio
    async def test_cancel_other_user_enrollment_returns_403(self, client: AsyncClient):
        """Cancelar inscripción de otro usuario retorna 403."""
        creator = await create_authenticated_user(
            client, "creator12@test.com", "Pass123!", "Creator", "Twelve"
        )
        player = await create_authenticated_user(
            client, "player12@test.com", "Pass123!", "Player", "Twelve"
        )
        other = await create_authenticated_user(
            client, "other12@test.com", "Pass123!", "Other", "Twelve"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/cancel",
            headers={"Authorization": f"Bearer {other['token']}"}
        )

        assert response.status_code == 403


class TestSetCustomHandicap:
    """Tests para PUT /api/v1/enrollments/{id}/handicap"""

    @pytest.mark.asyncio
    async def test_set_custom_handicap_success(self, client: AsyncClient):
        """Creador establece handicap personalizado exitosamente."""
        creator = await create_authenticated_user(
            client, "creator13@test.com", "Pass123!", "Creator", "Thirteen"
        )
        player = await create_authenticated_user(
            client, "player13@test.com", "Pass123!", "Player", "Thirteen"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        # Inscripción directa
        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"user_id": player["user_id"]},
            headers={"Authorization": f"Bearer {creator['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        # Establecer handicap
        response = await client.put(
            f"/api/v1/enrollments/{enrollment_id}/handicap",
            json={"enrollment_id": enrollment_id, "custom_handicap": 15.5},
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 200
        assert float(response.json()["custom_handicap"]) == 15.5


class TestEnrollmentEdgeCases:
    """Tests de edge cases para Enrollment"""

    @pytest.mark.asyncio
    async def test_approve_already_approved_returns_400(self, client: AsyncClient):
        """Aprobar inscripción ya aprobada retorna 400."""
        creator = await create_authenticated_user(
            client, "creator_ec1@test.com", "Pass123!", "Creator", "EC1"
        )
        player = await create_authenticated_user(
            client, "player_ec1@test.com", "Pass123!", "Player", "EC1"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        # Primera aprobación
        await client.post(
            f"/api/v1/enrollments/{enrollment_id}/approve",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        # Segunda aprobación
        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/approve",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_from_requested_returns_400(self, client: AsyncClient):
        """Retirarse de inscripción REQUESTED retorna 400 (debe estar APPROVED)."""
        creator = await create_authenticated_user(
            client, "creator_ec2@test.com", "Pass123!", "Creator", "EC2"
        )
        player = await create_authenticated_user(
            client, "player_ec2@test.com", "Pass123!", "Player", "EC2"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        # Intentar withdraw sin aprobar
        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/withdraw",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_approved_returns_400(self, client: AsyncClient):
        """Cancelar inscripción APPROVED retorna 400 (debe usar withdraw)."""
        creator = await create_authenticated_user(
            client, "creator_ec3@test.com", "Pass123!", "Creator", "EC3"
        )
        player = await create_authenticated_user(
            client, "player_ec3@test.com", "Pass123!", "Player", "EC3"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        # Aprobar
        await client.post(
            f"/api/v1/enrollments/{enrollment_id}/approve",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        # Intentar cancel en vez de withdraw
        response = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/cancel",
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_set_handicap_not_creator_returns_403(self, client: AsyncClient):
        """Establecer handicap sin ser creador retorna 403."""
        creator = await create_authenticated_user(
            client, "creator_ec4@test.com", "Pass123!", "Creator", "EC4"
        )
        player = await create_authenticated_user(
            client, "player_ec4@test.com", "Pass123!", "Player", "EC4"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        enroll_response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"user_id": player["user_id"]},
            headers={"Authorization": f"Bearer {creator['token']}"}
        )
        enrollment_id = enroll_response.json()["id"]

        # Jugador intenta cambiar su propio handicap (no permitido)
        response = await client.put(
            f"/api/v1/enrollments/{enrollment_id}/handicap",
            json={"enrollment_id": enrollment_id, "custom_handicap": 10.0},
            headers={"Authorization": f"Bearer {player['token']}"}
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_enrollment_not_found_returns_404(self, client: AsyncClient):
        """Operación en enrollment inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "notfound@test.com", "Pass123!", "Not", "Found"
        )

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/api/v1/enrollments/{fake_id}/approve",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_enrollments_filter_by_status(self, client: AsyncClient):
        """Filtrar inscripciones por estado."""
        creator = await create_authenticated_user(
            client, "creator_ec5@test.com", "Pass123!", "Creator", "EC5"
        )
        player1 = await create_authenticated_user(
            client, "player_ec5a@test.com", "Pass123!", "Player", "EC5A"
        )
        player2 = await create_authenticated_user(
            client, "player_ec5b@test.com", "Pass123!", "Player", "EC5B"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        # Crear 2 inscripciones, aprobar solo 1
        enroll1 = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player1['token']}"}
        )
        await client.post(
            f"/api/v1/enrollments/{enroll1.json()['id']}/approve",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            headers={"Authorization": f"Bearer {player2['token']}"}
        )

        # Filtrar solo APPROVED
        response = await client.get(
            f"/api/v1/competitions/{comp['id']}/enrollments?status=APPROVED",
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_direct_enroll_with_custom_handicap(self, client: AsyncClient):
        """Inscripción directa con handicap personalizado."""
        creator = await create_authenticated_user(
            client, "creator_ec6@test.com", "Pass123!", "Creator", "EC6"
        )
        player = await create_authenticated_user(
            client, "player_ec6@test.com", "Pass123!", "Player", "EC6"
        )

        comp = await create_competition(client, creator["token"])
        await activate_competition(client, creator["token"], comp["id"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"user_id": player["user_id"], "custom_handicap": 12.5},
            headers={"Authorization": f"Bearer {creator['token']}"}
        )

        assert response.status_code == 201
        assert float(response.json()["custom_handicap"]) == 12.5
