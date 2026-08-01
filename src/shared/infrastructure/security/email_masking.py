"""Utilidad compartida para enmascarar emails en logs de seguridad."""


def mask_email(email: str) -> str:
    """Enmascara un email para logging seguro (ej: t***@example.com)."""
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:  # noqa: PLR2004
        return "***"
    local = parts[0]
    masked_local = local[0] + "***" if len(local) > 1 else "***"
    return f"{masked_local}@{parts[1]}"
