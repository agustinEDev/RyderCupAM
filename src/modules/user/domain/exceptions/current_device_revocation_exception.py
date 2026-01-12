"""Current Device Revocation Exception - Lanzada cuando se intenta revocar el dispositivo actual."""


class CurrentDeviceRevocationException(Exception):  # noqa: N818 - Exception is intentional naming
    """
    Excepción lanzada cuando un usuario intenta revocar el dispositivo desde el cual
    está haciendo la petición (auto-revocación).

    Esta excepción se lanza en el Application Layer (RevokeDeviceUseCase) cuando:
    - El dispositivo a revocar tiene el mismo fingerprint que el dispositivo actual
    - user_agent + ip_address del request coinciden con el dispositivo a revocar

    Security (OWASP A01):
        - Previene que el usuario se desloguee accidentalmente
        - Mantiene la sesión activa hasta logout explícito
        - Mejora la experiencia de usuario (UX)

    Use Case:
        Usuario quiere revocar dispositivos antiguos/perdidos, pero NO el actual.
        Esta excepción previene errores comunes donde el usuario revoca el dispositivo
        equivocado y pierde acceso a su sesión.

    Attributes:
        device_id: ID del dispositivo que se intentó revocar
        device_name: Nombre legible del dispositivo (ej: "Chrome on macOS")
        message: Mensaje descriptivo del error

    Example:
        >>> raise CurrentDeviceRevocationException(
        ...     device_id="7c9e6679-7425-40de-944b-e07fc1f90ae7",
        ...     device_name="Chrome 120.0 on macOS",
        ...     message="Cannot revoke current device. Use logout to close this session."
        ... )
    """

    def __init__(self, device_id: str, device_name: str, message: str | None = None):
        self.device_id = device_id
        self.device_name = device_name
        self.message = (
            message
            or f"No puedes revocar el dispositivo actual ({device_name}). Usa el endpoint de logout para cerrar esta sesión."
        )
        super().__init__(self.message)
