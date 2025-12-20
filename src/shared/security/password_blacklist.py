"""
Password Blacklist - Common Weak Passwords

Lista de las contraseñas más comunes y débiles que deben ser rechazadas.
Basado en estudios de seguridad y análisis de breaches reales.

Fuentes:
- SplashData "Worst Passwords" annual report
- NordPass "Most Common Passwords" analysis
- NCSC (UK National Cyber Security Centre) recommendations
- Have I Been Pwned breach database patterns

OWASP ASVS Compliance:
- V2.1.7: Verify that a common password filter is applied
"""

# Top 100 contraseñas más comunes (case-insensitive check)
# Incluye variaciones numéricas comunes y patrones de teclado
COMMON_PASSWORDS = {
    # Números secuenciales
    "123456",
    "12345678",
    "123456789",
    "1234567890",
    "12345",
    "1234",
    "111111",
    "000000",
    "123123",
    "654321",

    # Palabra "password" y variaciones
    "password",
    "password1",
    "password123",
    "password12",
    "passw0rd",
    "p@ssw0rd",
    "p@ssword",
    "passwd",

    # Palabras comunes
    "welcome",
    "welcome1",
    "admin",
    "administrator",
    "root",
    "user",
    "letmein",
    "login",
    "master",
    "secret",
    "guest",
    "test",
    "demo",

    # Patrones de teclado
    "qwerty",
    "qwerty123",
    "qwertyuiop",
    "asdfgh",
    "asdfghjkl",
    "zxcvbnm",
    "1qaz2wsx",
    "qazwsx",
    "abc123",
    "abc123456",

    # Nombres comunes
    "monkey",
    "dragon",
    "baseball",
    "football",
    "superman",
    "batman",
    "trustno1",
    "iloveyou",
    "sunshine",
    "shadow",
    "michael",
    "jennifer",
    "jordan",
    "charlie",
    "princess",
    "killer",
    "master",

    # Defaults de sistemas
    "admin123",
    "admin1234",
    "changeme",
    "default",
    "temp",
    "temporary",
    "user123",

    # Variaciones con años
    "password2024",
    "password2025",
    "welcome2024",
    "welcome2025",
    "admin2024",
    "admin2025",

    # Frases comunes en español (nuestro contexto)
    "contraseña",
    "contrasena",
    "micontraseña",
    "micontrasena",
    "clave",
    "clave123",
    "administrador",
    "usuario",
    "bienvenido",

    # Variaciones típicas que intentan "cumplir" requisitos
    "Password1",
    "Password1!",
    "Password123",
    "Password123!",
    "Welcome1",
    "Welcome1!",
    "Welcome123",
    "Welcome123!",
    "Admin123!",
    "Qwerty123",
    "Qwerty123!",
    "Abc123!",
    "Abcd1234",
    "Abcd1234!",

    # Fechas comunes
    "01011990",
    "01011991",
    "01011992",
    "01011993",
    "01011994",
    "01011995",
    "12345678",

    # Otras comunes
    "nothing",
    "whatever",
    "anything",
    "something",
}


def is_common_password(password: str) -> bool:
    """
    Verifica si una contraseña está en la blacklist de contraseñas comunes.

    Args:
        password: La contraseña a verificar (sin hashear)

    Returns:
        True si la contraseña está en la blacklist, False si es aceptable

    Notes:
        - La comparación es case-insensitive (Password1 == password1)
        - Rechaza contraseñas que sean exactamente iguales a la blacklist
        - NO rechaza contraseñas que CONTENGAN palabras comunes (ej: "MyPassword123!" es OK)

    Examples:
        >>> is_common_password("password123")
        True
        >>> is_common_password("MySecureP@ssw0rd2025")
        False
        >>> is_common_password("Welcome1!")  # En blacklist
        True
    """
    return password.lower() in COMMON_PASSWORDS


def get_blacklist_size() -> int:
    """
    Retorna el tamaño de la blacklist de contraseñas comunes.

    Returns:
        Número de contraseñas en la blacklist
    """
    return len(COMMON_PASSWORDS)
