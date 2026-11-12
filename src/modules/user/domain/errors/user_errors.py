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


class TermsAcceptanceRequiredError(UserDomainError):
    """
    Se intenta dar de alta a alguien que no ha aceptado los Términos.

    La API ya lo impide (422), pero el caso de uso no se fía de que el request
    llegue validado: sin consentimiento explícito no hay alta.
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


class EmailTakenConcurrentlyError(UserAlreadyExistsError):
    """
    El correo se lo llevó otra alta entre la comprobación y el guardado.

    Lo lanza la unidad de trabajo al enviar el alta (`flush`) y chocar con la
    restricción única del correo. El registro lo trata como cualquier correo ya
    registrado (fase 3): la misma respuesta y el aviso al buzón.
    """

    pass


class DuplicateEmailError(UserDomainError):
    """
    Excepción lanzada cuando se intenta usar un email que ya está en uso.

    Se utiliza cuando un usuario intenta cambiar su email a uno que
    ya pertenece a otro usuario en el sistema.
    """

    pass


class AliasAlreadyTakenError(UserDomainError):
    """
    Excepción lanzada cuando el alias pedido ya lo tiene otra persona.

    La comparación ignora mayúsculas: "chuchi" y "Chuchi" son el mismo alias.
    Llega a la API como un 409 con un mensaje que el frontend enseña tal cual
    junto al campo.
    """

    pass


class AliasTakenConcurrentlyError(AliasAlreadyTakenError):
    """
    El alias se lo llevó otra petición entre la comprobación y el guardado.

    Lo lanza la unidad de trabajo al chocar con el índice único del alias. No sabe
    qué alias se pidió, así que el caso de uso lo vuelve a lanzar como
    AliasAlreadyTakenError con el alias en el mensaje.
    """


class InvalidCredentialsError(UserDomainError):
    """
    Excepción lanzada cuando las credenciales proporcionadas son inválidas.

    Se utiliza durante la autenticación o verificación de contraseña actual
    cuando el password proporcionado no coincide con el almacenado.
    """

    pass


class InvalidAvatarPresetError(UserDomainError):
    """
    Excepción lanzada cuando se referencia un preset_id de avatar fuera de rango.

    Los presets son un catálogo fijo (1..AVATAR_PRESET_COUNT) empaquetado con el backend,
    no una tabla en BD, así que la validación es puramente de rango.
    """

    pass


class AvatarUploadNotFoundError(UserDomainError):
    """
    Excepción lanzada cuando no se encuentra una foto subida por el usuario
    (id inexistente, o perteneciente a otro usuario).
    """

    pass


class AvatarUploadTooLargeError(UserDomainError):
    """Excepción lanzada cuando el archivo subido supera el tamaño máximo permitido."""

    pass


class InvalidAvatarImageError(UserDomainError):
    """
    Excepción lanzada cuando el archivo subido no es una imagen válida/soportada
    (no se puede decodificar, o el formato no está en la lista permitida).
    """

    pass

    pass
