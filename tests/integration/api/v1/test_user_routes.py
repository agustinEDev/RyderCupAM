import pytest
from httpx import AsyncClient
from fastapi import status

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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "test_user@example.com",
            "securePassword123",
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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "john.doe@example.com",
            "securePassword123",
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
        from tests.conftest import create_authenticated_user

        auth_data1 = await create_authenticated_user(
            client,
            "user1@example.com",
            "securePassword123",
            "Jane",
            "Smith"
        )
        token = auth_data1["token"]

        user2_data = {
            "email": "user2@example.com",
            "password": "securePassword123",
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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "searcher@example.com",
            "securePassword123",
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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "searcher2@example.com",
            "securePassword123",
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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "searcher3@example.com",
            "securePassword123",
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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "case.test@example.com",
            "securePassword123",
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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "rafa_nadal@prueba.com",
            "securePassword123",
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