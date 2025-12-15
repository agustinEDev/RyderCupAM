#!/usr/bin/env python3
"""
Script para actualizar contraseñas débiles en tests a contraseñas que cumplan
la nueva Password Policy (12+ chars, complejidad completa).

Ejecutar desde la raíz del proyecto:
    python fix_test_passwords.py
"""

import os
import re
from pathlib import Path

# Mapeo de contraseñas débiles → contraseñas fuertes
PASSWORD_REPLACEMENTS = {
    # Contraseñas de 8-11 caracteres (muy comunes en tests)
    "Password123": "P@ssw0rd123!",         # 12 chars (agregado para integración)
    "TestPass123!": "T3stP@ss123!",        # 13 chars (conftest.py)
    "Pass123!": "P@ssw0rd123!",            # 12 chars (competition endpoints)
    "Password123!": "T3stP@ssw0rd!",       # 13 chars
    "TestPassword123": "T3stP@ssw0rd123!",  # 16 chars
    "testpassword": "t3stp@ssw0rd!",       # 13 chars
    "password123": "p@ssw0rd1234!",        # 13 chars
    "SecurePass1": "S3cur3P@ss123!",       # 14 chars
    "securePassword123": "s3cur3P@ssw0rd!",  # 15 chars
    "WrongPassword": "Wr0ngP@ssw0rd!",     # 15 chars
    "WrongPassword123": "Wr0ngP@ssw0rd!",  # 15 chars
    "SomePassword123": "S0m3P@ssw0rd!",    # 13 chars

    # Contraseñas más largas que aún no cumplen (sin símbolos)
    "MySecure123": "MyS3cur3P@ss!",        # 13 chars
    "MySecurePass": "MyS3cur3P@ss!",       # 13 chars
    "ValidPass123": "V@l1dP@ss123!",       # 14 chars (ya está en conftest)
    "TestPass123": "T3stP@ss123!",         # 12 chars
    "AnotherPass123": "An0th3rP@ss!",      # 13 chars
    "AnotherValidPass456": "An0th3rV@l1dP@ss!",  # 17 chars
    "NewSecurePass456": "N3wS3cur3P@ss!",  # 15 chars (test_update_security_use_case)
    "welcome2025": "W3lc0m3!2025",         # 12 chars (test_password blacklist)
    "admin2025": "Adm1n!20250!",           # 12 chars (blacklist test)
    "qwerty123": "Qw3rty!123456",          # 13 chars (blacklist test)

    # Contraseñas de test_user_routes.py que faltan símbolos
    "newPassword456": "n3wP@ssw0rd!",      # 13 chars
    "newPassword789": "n3wP@ssw0rd!9",     # 14 chars
    "oldPassword123": "0ldP@ssw0rd!",      # 13 chars
    "SecurePass123": "S3cur3P@ss123!",     # 14 chars
    "DifferentPass456": "D1ff3r3ntP@ss!",  # 15 chars
    "correctPassword123": "C0rr3ctP@ss!",  # 13 chars
    "wrongPassword": "Wr0ngP@ssw0rd!",     # 15 chars (ya válida)
    "CorrectPass123": "C0rr3ctP@ss123!",   # 15 chars (test_login_events_integration)

    # Contraseñas de 8 caracteres (crítico: deben cambiar)
    "s3cur3P@ssw0rd!": "s3cur3P@ssw0rd!",  # Ya es válida (15 chars)
    "Wr0ngP@ssw0rd!": "Wr0ngP@ssw0rd!",    # Ya es válida (15 chars)
    "S0m3P@ssw0rd!": "S0m3P@ssw0rd!",      # Ya es válida (13 chars)

    # IMPORTANTE: Esta línea debe ir AL FINAL para no interferir con otras
    "Password1": "P@ssw0rd123!",           # 12 chars
}

def fix_test_file(file_path: Path) -> int:
    """
    Reemplaza contraseñas débiles en un archivo de tests.

    Returns:
        Número de reemplazos realizados
    """
    content = file_path.read_text()
    original_content = content
    replacements_count = 0

    for weak_pwd, strong_pwd in PASSWORD_REPLACEMENTS.items():
        # Buscar patrón "weak_pwd" (con comillas)
        pattern = rf'["\']({re.escape(weak_pwd)})["\']'
        matches = re.findall(pattern, content)

        if matches:
            # Reemplazar manteniendo el tipo de comillas original
            content = re.sub(
                pattern,
                lambda m: f'"{strong_pwd}"' if m.group(0)[0] == '"' else f"'{strong_pwd}'",
                content
            )
            replacements_count += len(matches)

    # Escribir solo si hubo cambios
    if content != original_content:
        file_path.write_text(content)
        print(f"✅ {file_path}: {replacements_count} reemplazos")
        return replacements_count

    return 0


def main():
    """Busca y corrige todos los archivos de tests."""
    tests_dir = Path("tests")

    if not tests_dir.exists():
        print("❌ Directorio 'tests/' no encontrado. Ejecutar desde la raíz del proyecto.")
        return

    total_files = 0
    total_replacements = 0

    # Buscar todos los archivos .py en tests/
    for test_file in tests_dir.rglob("test_*.py"):
        # Excluir test_password.py porque tiene contraseñas específicas de blacklist
        if test_file.name == "test_password.py":
            continue
        replacements = fix_test_file(test_file)
        if replacements > 0:
            total_files += 1
            total_replacements += replacements

    # También procesar conftest.py
    conftest_file = tests_dir / "conftest.py"
    if conftest_file.exists():
        replacements = fix_test_file(conftest_file)
        if replacements > 0:
            total_files += 1
            total_replacements += replacements

    print(f"\n🎉 Completado:")
    print(f"   - Archivos modificados: {total_files}")
    print(f"   - Reemplazos totales: {total_replacements}")

    if total_replacements > 0:
        print(f"\n✨ Ejecutar tests para verificar:")
        print(f"   python dev_tests.py")


if __name__ == "__main__":
    main()
