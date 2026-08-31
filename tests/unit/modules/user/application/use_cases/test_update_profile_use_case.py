"""
Tests para UpdateProfileUseCase

Tests unitarios para el caso de uso de actualización de perfil del usuario.
"""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from src.modules.user.application.dto.user_dto import UpdateProfileRequestDTO
from src.modules.user.application.use_cases.update_profile_use_case import (
    UpdateProfileUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import (
    AliasAlreadyTakenError,
    UserNotFoundError,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    """Fixture que proporciona un Unit of Work en memoria."""
    return InMemoryUnitOfWork()


@pytest.fixture
def country_repository():
    """Fixture que proporciona un mock de CountryRepository."""
    mock_repo = AsyncMock()
    # Por defecto, todos los country codes son válidos
    mock_repo.exists.return_value = True
    return mock_repo


@pytest.fixture
async def existing_user(uow):
    """
    Fixture que crea un usuario existente en el sistema.
    """
    user = User.create(
        first_name="John",
        last_name="Doe",
        email_str="test@example.com",
        plain_password="V@l1dP@ss123!",
    )

    async with uow:
        await uow.users.save(user)
        await uow.commit()

    return user


@pytest.mark.asyncio
class TestUpdateProfileUseCase:
    """Tests para el caso de uso de actualización de perfil."""

    async def test_update_first_name_only(self, uow, country_repository, existing_user):
        """Debe actualizar solo el nombre cuando se proporciona."""
        # Arrange
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(first_name="Jane", last_name=None)

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "Jane"
        assert response.user.last_name == "Doe"  # No cambió
        assert response.message == "Profile updated successfully"

        # Verificar que se guardó en el repositorio
        updated_user = await uow.users.find_by_id(UserId(user_id))
        assert updated_user.first_name == "Jane"

    async def test_update_last_name_only(self, uow, country_repository, existing_user):
        """Debe actualizar solo el apellido cuando se proporciona."""
        # Arrange
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(first_name=None, last_name="Smith")

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "John"  # No cambió
        assert response.user.last_name == "Smith"
        assert response.message == "Profile updated successfully"

    async def test_update_both_names(self, uow, country_repository, existing_user):
        """Debe actualizar ambos campos cuando se proporcionan."""
        # Arrange
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(first_name="Jane", last_name="Smith")

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "Jane"
        assert response.user.last_name == "Smith"

    async def test_update_fails_when_user_not_found(self, uow, country_repository):
        """Debe lanzar UserNotFoundError cuando el usuario no existe."""
        # Arrange
        use_case = UpdateProfileUseCase(uow, country_repository)
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        request = UpdateProfileRequestDTO(first_name="Jane", last_name=None)

        # Act & Assert
        with pytest.raises(UserNotFoundError):
            await use_case.execute(non_existent_id, request)

    async def test_update_rejects_too_short_names(self, uow, country_repository, existing_user):
        """Debe rechazar nombres muy cortos (validación Pydantic)."""
        # Arrange
        UpdateProfileUseCase(uow, country_repository)
        str(existing_user.id.value)

        # Act & Assert - Pydantic valida min_length=2
        with pytest.raises(ValidationError):
            UpdateProfileRequestDTO(
                first_name="A",  # Muy corto
                last_name=None,
            )

    async def test_no_update_when_values_are_same(self, uow, country_repository, existing_user):
        """Debe retornar sin cambios cuando los valores son los mismos."""
        # Arrange
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(
            first_name="John",  # Mismo valor
            last_name="Doe",  # Mismo valor
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "John"
        assert response.user.last_name == "Doe"

    async def test_update_emits_domain_event(self, uow, country_repository, existing_user):
        """Debe emitir UserProfileUpdatedEvent cuando se actualiza."""
        # Arrange
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(first_name="Jane", last_name=None)

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        # Verificar que la respuesta tiene los datos actualizados
        assert response.user.first_name == "Jane"
        assert response.user.last_name == "Doe"  # No cambió

        # Verificar que se guardó en el repositorio
        updated_user = await uow.users.find_by_id(UserId(user_id))
        assert updated_user.first_name == "Jane"


@pytest.mark.asyncio
class TestUpdateProfileAlias:
    """
    Tests del alias en el caso de uso (BE #239).

    La unicidad la comprueba el caso de uso ANTES de guardar y la garantiza el
    índice único al hacer commit. Aquí se ejercitan los dos caminos.
    """

    async def test_sets_the_alias(self, uow, country_repository, existing_user):
        """Debe guardar el alias y devolverlo en la respuesta."""
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)

        response = await use_case.execute(user_id, UpdateProfileRequestDTO(alias="Chuchi"))

        assert response.user.alias == "Chuchi"
        saved = await uow.users.find_by_id(UserId(user_id))
        assert saved.alias == "Chuchi"
        assert saved.display_name == "Chuchi"

    async def test_clears_the_alias_with_an_empty_string(
        self, uow, country_repository, existing_user
    ):
        """La cadena vacía borra el alias y devuelve al nombre real."""
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        await use_case.execute(user_id, UpdateProfileRequestDTO(alias="Chuchi"))

        response = await use_case.execute(user_id, UpdateProfileRequestDTO(alias=""))

        assert response.user.alias is None
        saved = await uow.users.find_by_id(UserId(user_id))
        assert saved.alias is None
        assert saved.display_name == "John Doe"

    async def test_rejects_an_alias_taken_by_somebody_else(
        self, uow, country_repository, existing_user
    ):
        """Un alias que ya tiene otra persona se rechaza."""
        other = User.create(
            first_name="Ana",
            last_name="Garcia",
            email_str="ana@example.com",
            plain_password="V@l1dP@ss123!",
        )
        other.update_profile(alias="Chuchi")
        async with uow:
            await uow.users.save(other)
            await uow.commit()

        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)

        with pytest.raises(AliasAlreadyTakenError):
            await use_case.execute(user_id, UpdateProfileRequestDTO(alias="Chuchi"))

    async def test_rejects_the_same_alias_in_another_case(
        self, uow, country_repository, existing_user
    ):
        """
        La unicidad ignora mayúsculas: "chuchi" choca con "Chuchi".

        Es la mitad de la decisión de producto — dos cuentas llamadas igual
        harían inútil el alias para encontrar gente.
        """
        other = User.create(
            first_name="Ana",
            last_name="Garcia",
            email_str="ana@example.com",
            plain_password="V@l1dP@ss123!",
        )
        other.update_profile(alias="Chuchi")
        async with uow:
            await uow.users.save(other)
            await uow.commit()

        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)

        with pytest.raises(AliasAlreadyTakenError):
            await use_case.execute(user_id, UpdateProfileRequestDTO(alias="chuchi"))

    async def test_keeping_your_own_alias_is_not_a_conflict(
        self, uow, country_repository, existing_user
    ):
        """
        Reenviar el alias propio no choca consigo mismo.

        Pasa en cuanto el formulario manda el perfil entero: el alias viaja sin
        haber cambiado, y tratarlo como conflicto haría imposible editar el
        país sin borrar antes el alias.
        """
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        await use_case.execute(user_id, UpdateProfileRequestDTO(alias="Chuchi"))

        response = await use_case.execute(
            user_id, UpdateProfileRequestDTO(alias="Chuchi", first_name="Johnny")
        )

        assert response.user.alias == "Chuchi"
        assert response.user.first_name == "Johnny"

    async def test_changing_only_the_case_of_your_own_alias_is_allowed(
        self, uow, country_repository, existing_user
    ):
        """Cambiar solo las mayúsculas del alias propio debe poder hacerse."""
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)
        await use_case.execute(user_id, UpdateProfileRequestDTO(alias="chuchi"))

        response = await use_case.execute(user_id, UpdateProfileRequestDTO(alias="Chuchi"))

        assert response.user.alias == "Chuchi"

    async def test_translates_the_unique_index_violation_into_a_conflict(
        self, uow, country_repository, existing_user
    ):
        """
        La carrera la resuelve el índice, y su error sale como conflicto.

        Entre la comprobación y el commit cabe otra petición pidiendo el mismo
        alias. Se simula que el commit revienta con la violación del índice.
        """
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)

        original_commit = uow.commit

        async def commit_conflicting(*args, **kwargs):
            raise IntegrityError(
                "INSERT INTO users ...",
                {},
                Exception('duplicate key value violates unique constraint "ix_users_alias_lower"'),
            )

        uow.commit = commit_conflicting
        try:
            with pytest.raises(AliasAlreadyTakenError):
                await use_case.execute(user_id, UpdateProfileRequestDTO(alias="Chuchi"))
        finally:
            uow.commit = original_commit

    async def test_other_integrity_errors_are_not_swallowed(
        self, uow, country_repository, existing_user
    ):
        """
        Solo se traduce la violación del índice del alias.

        Cualquier otro IntegrityError seguiría subiendo: convertirlo en «ese
        alias está cogido» mandaría al usuario a cambiar algo que no es lo que
        falla.
        """
        use_case = UpdateProfileUseCase(uow, country_repository)
        user_id = str(existing_user.id.value)

        async def commit_failing(*args, **kwargs):
            raise IntegrityError(
                "INSERT INTO users ...",
                {},
                Exception('duplicate key value violates unique constraint "users_email_key"'),
            )

        uow.commit = commit_failing
        with pytest.raises(IntegrityError):
            await use_case.execute(user_id, UpdateProfileRequestDTO(alias="Chuchi"))
