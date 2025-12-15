import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import create_authenticated_user

# Marcar todos los tests para ejecutarse con asyncio
pytestmark = pytest.mark.asyncio


class TestUserRoutes:
    """
    Suite de tests de integración para las rutas de usuarios.
    """

    async def test_find_user_by_email_successfully(self, client: AsyncClient):
        """
        Verifica que se puede buscar un usuario por email y se devuelve su información.
        """
        # Primero registramos un usuario y obtenemos su token

        auth_data = await create_authenticated_user(
            client,
            "test_user@example.com",
            "s3cur3P@ssw0rd!",
            "Test",
            "User"
        )
        token = auth_data["token"]

        # Ahora buscamos el usuario por email
        search_response = await client.get(
            "/api/v1/users/search",
            params={"email": "test_user@example.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_response.status_code == status.HTTP_200_OK

        response_data = search_response.json()
        assert "user_id" in response_data
        assert response_data["email"] == "test_user@example.com"
        assert response_data["full_name"] == "Test User"

    async def test_find_user_by_full_name_successfully(self, client: AsyncClient):
        """
        Verifica que se puede buscar un usuario por nombre completo.
        """
        # Primero registramos un usuario

        auth_data = await create_authenticated_user(
            client,
            "john.doe@example.com",
            "s3cur3P@ssw0rd!",
            "John",
            "Doe"
        )
        token = auth_data["token"]

        # Ahora buscamos el usuario por nombre completo
        search_response = await client.get(
            "/api/v1/users/search",
            params={"full_name": "John Doe"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_response.status_code == status.HTTP_200_OK

        response_data = search_response.json()
        assert "user_id" in response_data
        assert response_data["email"] == "john.doe@example.com"
        assert response_data["full_name"] == "John Doe"

    async def test_find_user_with_both_email_and_name(self, client: AsyncClient):
        """
        Verifica que se puede buscar con ambos parámetros y prioriza por email.
        """
        # Registramos dos usuarios

        auth_data1 = await create_authenticated_user(
            client,
            "user1@example.com",
            "s3cur3P@ssw0rd!",
            "Jane",
            "Smith"
        )
        token = auth_data1["token"]

        user2_data = {
            "email": "user2@example.com",
            "password": "s3cur3P@ssw0rd!",
            "first_name": "John",
            "last_name": "Smith"
        }

        await client.post("/api/v1/auth/register", json=user2_data)

        # Buscamos con email de user1 pero nombre de user2
        search_response = await client.get(
            "/api/v1/users/search",
            params={
                "email": "user1@example.com",
                "full_name": "John Smith"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_response.status_code == status.HTTP_200_OK

        response_data = search_response.json()
        # Debe devolver user1 porque se prioriza la búsqueda por email
        assert response_data["email"] == "user1@example.com"
        assert response_data["full_name"] == "Jane Smith"

    async def test_find_user_not_found_by_email(self, client: AsyncClient):
        """
        Verifica que devuelve 404 cuando no se encuentra un usuario por email.
        """
        # Crear usuario autenticado para hacer la búsqueda

        auth_data = await create_authenticated_user(
            client,
            "searcher@example.com",
            "s3cur3P@ssw0rd!",
            "Searcher",
            "User"
        )
        token = auth_data["token"]

        search_response = await client.get(
            "/api/v1/users/search",
            params={"email": "nonexistent@example.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_response.status_code == status.HTTP_404_NOT_FOUND

        response_data = search_response.json()
        assert "detail" in response_data
        assert "nonexistent@example.com" in response_data["detail"]

    async def test_find_user_not_found_by_name(self, client: AsyncClient):
        """
        Verifica que devuelve 404 cuando no se encuentra un usuario por nombre.
        """
        # Crear usuario autenticado para hacer la búsqueda

        auth_data = await create_authenticated_user(
            client,
            "searcher2@example.com",
            "s3cur3P@ssw0rd!",
            "Searcher2",
            "User"
        )
        token = auth_data["token"]

        search_response = await client.get(
            "/api/v1/users/search",
            params={"full_name": "Nonexistent User"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_response.status_code == status.HTTP_404_NOT_FOUND

        response_data = search_response.json()
        assert "detail" in response_data
        assert "Nonexistent User" in response_data["detail"]

    async def test_find_user_requires_at_least_one_parameter(self, client: AsyncClient):
        """
        Verifica que se requiere al menos un parámetro de búsqueda.
        """
        # Crear usuario autenticado para hacer la búsqueda

        auth_data = await create_authenticated_user(
            client,
            "searcher3@example.com",
            "s3cur3P@ssw0rd!",
            "Searcher3",
            "User"
        )
        token = auth_data["token"]

        search_response = await client.get(
            "/api/v1/users/search",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = search_response.json()
        assert "detail" in response_data
        assert "al menos" in response_data["detail"].lower()

    async def test_find_user_case_insensitive_name_search(self, client: AsyncClient):
        """
        Verifica que la búsqueda por nombre es insensible a mayúsculas/minúsculas.
        """
        # Registramos un usuario y obtenemos su token

        auth_data = await create_authenticated_user(
            client,
            "case.test@example.com",
            "s3cur3P@ssw0rd!",
            "Case",
            "Test"
        )
        token = auth_data["token"]

        # Buscamos con diferentes casos
        search_cases = ["case test", "CASE TEST", "Case Test", "CaSe TeSt"]

        for search_name in search_cases:
            search_response = await client.get(
                "/api/v1/users/search",
                params={"full_name": search_name},
                headers={"Authorization": f"Bearer {token}"}
            )

            assert search_response.status_code == status.HTTP_200_OK
            response_data = search_response.json()
            assert response_data["email"] == "case.test@example.com"
            assert response_data["full_name"] == "Case Test"

    async def test_find_user_with_real_data_rafael_nadal(self, client: AsyncClient):
        """
        Verifica que se puede buscar a Rafael Nadal que ya está registrado en el sistema.
        """
        # Registramos a Rafael Nadal y obtenemos su token

        auth_data = await create_authenticated_user(
            client,
            "rafa_nadal@prueba.com",
            "s3cur3P@ssw0rd!",
            "Rafael",
            "Nadal Parera"
        )
        token = auth_data["token"]

        # Buscamos por email
        search_by_email = await client.get(
            "/api/v1/users/search",
            params={"email": "rafa_nadal@prueba.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_by_email.status_code == status.HTTP_200_OK
        email_data = search_by_email.json()
        assert email_data["full_name"] == "Rafael Nadal Parera"

        # Buscamos por nombre completo
        search_by_name = await client.get(
            "/api/v1/users/search",
            params={"full_name": "Rafael Nadal Parera"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert search_by_name.status_code == status.HTTP_200_OK
        name_data = search_by_name.json()
        assert name_data["email"] == "rafa_nadal@prueba.com"

        # Ambas búsquedas deben devolver el mismo user_id
        assert email_data["user_id"] == name_data["user_id"]

    # ========================================================================
    # Tests para Update Profile (PATCH /api/v1/users/profile)
    # ========================================================================

    async def test_update_profile_first_name_only(self, client: AsyncClient):
        """Verifica que se puede actualizar solo el nombre."""

        auth_data = await create_authenticated_user(
            client,
            "profile.test@example.com",
            "s3cur3P@ssw0rd!",
            "Original",
            "Name"
        )
        token = auth_data["token"]

        # Actualizar solo first_name
        update_response = await client.patch(
            "/api/v1/users/profile",
            json={"first_name": "Updated", "last_name": None},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["user"]["first_name"] == "Updated"
        assert data["user"]["last_name"] == "Name"  # No cambió
        assert "Profile updated" in data["message"]

    async def test_update_profile_last_name_only(self, client: AsyncClient):
        """Verifica que se puede actualizar solo el apellido."""

        auth_data = await create_authenticated_user(
            client,
            "profile2.test@example.com",
            "s3cur3P@ssw0rd!",
            "John",
            "Original"
        )
        token = auth_data["token"]

        # Actualizar solo last_name
        update_response = await client.patch(
            "/api/v1/users/profile",
            json={"first_name": None, "last_name": "Updated"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["user"]["first_name"] == "John"  # No cambió
        assert data["user"]["last_name"] == "Updated"

    async def test_update_profile_both_names(self, client: AsyncClient):
        """Verifica que se pueden actualizar ambos campos."""

        auth_data = await create_authenticated_user(
            client,
            "profile3.test@example.com",
            "s3cur3P@ssw0rd!",
            "Old",
            "Names"
        )
        token = auth_data["token"]

        # Actualizar ambos
        update_response = await client.patch(
            "/api/v1/users/profile",
            json={"first_name": "New", "last_name": "Names"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["user"]["first_name"] == "New"
        assert data["user"]["last_name"] == "Names"

    async def test_update_profile_requires_authentication(self, client: AsyncClient):
        """Verifica que se requiere autenticación."""
        update_response = await client.patch(
            "/api/v1/users/profile",
            json={"first_name": "New", "last_name": None}
        )

        assert update_response.status_code == status.HTTP_403_FORBIDDEN

    async def test_update_profile_rejects_empty_names(self, client: AsyncClient):
        """Verifica que no se aceptan strings vacíos (validación Pydantic)."""

        auth_data = await create_authenticated_user(
            client,
            "profile4.test@example.com",
            "s3cur3P@ssw0rd!",
            "Test",
            "User"
        )
        token = auth_data["token"]

        # Intentar actualizar con string vacío
        update_response = await client.patch(
            "/api/v1/users/profile",
            json={"first_name": "", "last_name": None},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Pydantic devuelve 422 para errores de validación
        assert update_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # ========================================================================
    # Tests para Update Security (PATCH /api/v1/users/security)
    # ========================================================================

    async def test_update_security_email_only(self, client: AsyncClient):
        """Verifica que se puede actualizar solo el email."""

        auth_data = await create_authenticated_user(
            client,
            "security.test@example.com",
            "s3cur3P@ssw0rd!",
            "Security",
            "Test"
        )
        token = auth_data["token"]

        # Actualizar solo email
        update_response = await client.patch(
            "/api/v1/users/security",
            json={
                "current_password": "s3cur3P@ssw0rd!",
                "new_email": "newemail@example.com",
                "new_password": None,
                "confirm_password": None
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["user"]["email"] == "newemail@example.com"
        assert "Security settings updated" in data["message"]

    async def test_update_security_password_only(self, client: AsyncClient):
        """Verifica que se puede actualizar solo el password."""

        auth_data = await create_authenticated_user(
            client,
            "security2.test@example.com",
            "0ldP@ssw0rd!",
            "Security2",
            "Test"
        )
        token = auth_data["token"]

        # Actualizar solo password
        update_response = await client.patch(
            "/api/v1/users/security",
            json={
                "current_password": "0ldP@ssw0rd!",
                "new_email": None,
                "new_password": "n3wP@ssw0rd!",
                "confirm_password": "n3wP@ssw0rd!"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_200_OK

        # Verificar que el nuevo password funciona
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "security2.test@example.com",
                "password": "n3wP@ssw0rd!"
            }
        )
        assert login_response.status_code == status.HTTP_200_OK

    async def test_update_security_both_email_and_password(self, client: AsyncClient):
        """Verifica que se pueden actualizar ambos."""

        auth_data = await create_authenticated_user(
            client,
            "security3.test@example.com",
            "0ldP@ssw0rd!",
            "Security3",
            "Test"
        )
        token = auth_data["token"]

        # Actualizar ambos
        update_response = await client.patch(
            "/api/v1/users/security",
            json={
                "current_password": "0ldP@ssw0rd!",
                "new_email": "newemail3@example.com",
                "new_password": "n3wP@ssw0rd!9",
                "confirm_password": "n3wP@ssw0rd!9"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["user"]["email"] == "newemail3@example.com"

        # Verificar login con nuevo email y password
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "newemail3@example.com",
                "password": "n3wP@ssw0rd!9"
            }
        )
        assert login_response.status_code == status.HTTP_200_OK

    async def test_update_security_rejects_wrong_current_password(self, client: AsyncClient):
        """Verifica que rechaza password actual incorrecto."""

        auth_data = await create_authenticated_user(
            client,
            "security4.test@example.com",
            "C0rr3ctP@ss!",
            "Security4",
            "Test"
        )
        token = auth_data["token"]

        # Intentar con password incorrecto
        update_response = await client.patch(
            "/api/v1/users/security",
            json={
                "current_password": "Wr0ngP@ssw0rd!",
                "new_email": "newemail@example.com",
                "new_password": None,
                "confirm_password": None
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "incorrect" in update_response.json()["detail"].lower()

    async def test_update_security_rejects_duplicate_email(self, client: AsyncClient):
        """Verifica que rechaza email ya en uso."""

        # Crear dos usuarios
        auth_data1 = await create_authenticated_user(
            client,
            "user1@example.com",
            "S3cur3P@ss123!",
            "User1",
            "Test"
        )

        await create_authenticated_user(
            client,
            "user2@example.com",
            "S3cur3P@ss123!",
            "User2",
            "Test"
        )

        token1 = auth_data1["token"]

        # User1 intenta usar email de User2
        update_response = await client.patch(
            "/api/v1/users/security",
            json={
                "current_password": "S3cur3P@ss123!",
                "new_email": "user2@example.com",  # Ya existe
                "new_password": None,
                "confirm_password": None
            },
            headers={"Authorization": f"Bearer {token1}"}
        )

        assert update_response.status_code == status.HTTP_409_CONFLICT
        assert "already in use" in update_response.json()["detail"]

    async def test_update_security_requires_authentication(self, client: AsyncClient):
        """Verifica que se requiere autenticación."""
        update_response = await client.patch(
            "/api/v1/users/security",
            json={
                "current_password": "p@ssw0rd1234!",
                "new_email": "newemail@example.com",
                "new_password": None,
                "confirm_password": None
            }
        )

        assert update_response.status_code == status.HTTP_403_FORBIDDEN

    async def test_update_security_password_confirmation_must_match(self, client: AsyncClient):
        """Verifica que el password y su confirmación deben coincidir."""

        auth_data = await create_authenticated_user(
            client,
            "security5.test@example.com",
            "S3cur3P@ss123!",
            "Security5",
            "Test"
        )
        token = auth_data["token"]

        # Passwords no coinciden
        update_response = await client.patch(
            "/api/v1/users/security",
            json={
                "current_password": "S3cur3P@ss123!",
                "new_email": None,
                "new_password": "N3wS3cur3P@ss!",
                "confirm_password": "D1ff3r3ntP@ss!"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert update_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
