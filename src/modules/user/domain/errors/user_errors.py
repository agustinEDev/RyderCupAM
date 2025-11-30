"""
User Domain Errors - Excepciones específicas del dominio de usuarios

Define las excepciones que pueden ocurrir en las operaciones de dominio relacionadas
con usuarios, incluyendo errores de repositorio y validaciones de negocio.
"""

from typing import Any


class UserDomainError(Exception):
    """
    Excepción base para todos los errores del dominio de usuarios.

    Todas las excepciones específicas del dominio de usuarios deben heredar de esta clase.
    """

    def __init__(self, message: str, details: Any = None) -> None:
        self.message = message
        self.details = details
        super().__init__(self.message)


class UserValidationError(UserDomainError):
    """
    Excepción lanzada cuando la validación de una entidad User falla.

    Se utiliza para errores de validación en la construcción o modificación
    de entidades User que no están relacionados con Value Objects específicos.
    """
    pass


class UserNotFoundError(UserDomainError):
    """
    Excepción lanzada cuando no se puede encontrar un usuario.

    Se utiliza en operaciones de repositorio cuando se intenta acceder
    a un usuario que no existe en el sistema.
    """
    pass


class UserAlreadyExistsError(UserDomainError):
    """
    Excepción lanzada cuando se intenta crear un usuario que ya existe.

    Se utiliza principalmente cuando se detecta un conflicto por email duplicado
    durante la creación de nuevos usuarios.
    """
    pass


class DuplicateEmailError(UserDomainError):
    """
    Excepción lanzada cuando se intenta usar un email que ya está en uso.

    Se utiliza cuando un usuario intenta cambiar su email a uno que
    ya pertenece a otro usuario en el sistema.
    """
    pass


class InvalidCredentialsError(UserDomainError):
    """
    Excepción lanzada cuando las credenciales proporcionadas son inválidas.

    Se utiliza durante la autenticación o verificación de contraseña actual
    cuando el password proporcionado no coincide con el almacenado.
    """
    pass


class RepositoryError(UserDomainError):
    """
    Excepción base para errores de repositorio.

    Se utiliza para encapsular errores de persistencia, conexión a base de datos,
    o cualquier problema relacionado con la capa de infraestructura de datos.
    """
    pass


class RepositoryConnectionError(RepositoryError):
    """
    Excepción lanzada cuando hay problemas de conexión con el repositorio.

    Se utiliza cuando no se puede establecer o mantener una conexión
    con el sistema de persistencia (base de datos, etc.).
    """
    pass


class RepositoryOperationError(RepositoryError):
    """
    Excepción lanzada cuando una operación de repositorio falla.

    Se utiliza para errores durante operaciones CRUD como save, update, delete
    que fallan por problemas de integridad, constraints, etc.
    """
    pass


class RepositoryTimeoutError(RepositoryError):
    """
    Excepción lanzada cuando una operación de repositorio excede el timeout.

    Se utiliza cuando las operaciones de base de datos tardan más tiempo
    del configurado como límite máximo.
    """
    pass
