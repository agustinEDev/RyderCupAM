# dev_tests.py
import subprocess
import json
import time
from pathlib import Path
from collections import defaultdict
import sys
import ast
from datetime import datetime

# Constants
NO_DESCRIPTION = "No description provided."

# --- Configuración de la Presentación ---
COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "ENDC": "\033[0m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
}

ICONS = {
    "PASSED": "✅",
    "FAILED": "❌",
    "SKIPPED": "⚠️ ",
    "ERROR": "🔥",
    "WARNING": "⚠️ ",
    "SUMMARY": "📊",
    "TIME": "⏱️ ",
    "SLOW": "🐢",
    "ROCKET": "🚀",
    "FOLDER": "📁",
    "DOC": "📝",
}

REPORTS_DIR = Path("tests/reports")
DOCSTRING_CACHE = {}

# --- Funciones Auxiliares ---

def print_header(title):
    """Imprime un encabezado llamativo."""
    print("\n" + COLORS["HEADER"] + COLORS["BOLD"] + "=" * 80)
    print(f"{title.center(80)}")
    print("=" * 80 + COLORS["ENDC"])

def discover_tests() -> dict:
    """Descubre tests y los organiza en una estructura anidada."""
    test_structure = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    test_root = Path("tests")
    for test_file in sorted(test_root.rglob("test_*.py")):
        parts = test_file.parts
        if len(parts) > 2:
            scope = parts[1].upper()
            module = parts[3].capitalize() if len(parts) > 3 else "Shared"
            layer = parts[4].capitalize() if len(parts) > 4 else "General"
            test_structure[scope][module][layer].append(test_file)
    return test_structure

def run_tests() -> tuple[str, int]:
    """Ejecuta pytest, guarda el reporte JSON y captura warnings de stderr."""
    REPORTS_DIR.mkdir(exist_ok=True)
    report_file = REPORTS_DIR / "test_report.json"
    command = [
        sys.executable, "-m", "pytest",
        "--json-report", f"--json-report-file={report_file}",
        "-n", "auto"
    ]
    print(f"{ICONS['ROCKET']} Ejecutando pytest con paralelización automática...")
    result = subprocess.run(command, check=False, capture_output=True, text=True)

    # Contar warnings en stderr
    warning_count = 0
    warning_lines = []
    for line in result.stderr.split('\n'):
        if 'warning' in line.lower() or 'Warning' in line:
            # Filtrar warnings reales, no mensajes informativos
            if any(keyword in line for keyword in ['PytestWarning', 'DeprecationWarning', 'PytestCollectionWarning', 'PytestDeprecationWarning']):
                warning_count += 1
                warning_lines.append(line.strip())

    # Guardar warnings en un archivo separado
    warnings_file = REPORTS_DIR / "warnings.txt"
    with open(warnings_file, 'w') as f:
        f.write(f"Total Warnings: {warning_count}\n\n")
        for line in warning_lines:
            f.write(f"{line}\n")

    try:
        with open(report_file, 'r') as f:
            report_data = json.load(f)
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        print(COLORS["RED"] + "Error: No se pudo leer o formatear el reporte JSON." + COLORS["ENDC"])
        with open(report_file, 'w') as f:
            f.write("{}")

    return str(report_file), warning_count

def get_docstrings_from_file(filepath: str) -> dict:
    """Extrae todos los docstrings de un fichero de test usando AST."""
    if filepath in DOCSTRING_CACHE:
        return DOCSTRING_CACHE[filepath]
    
    docs = {}
    try:
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docs[node.name] = ast.get_docstring(node) or NO_DESCRIPTION
            elif isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        key = f"{node.name}::{method.name}"
                        docs[key] = ast.get_docstring(method) or NO_DESCRIPTION
    except Exception:
        pass # Ignorar errores de parseo si el fichero es inválido
        
    DOCSTRING_CACHE[filepath] = docs
    return docs

def process_results(report_file: str, warning_count: int) -> dict:
    """Procesa el reporte JSON y extrae las estadísticas."""
    try:
        with open(report_file) as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"summary": {}, "tests": [], "by_file": defaultdict(list), "warning_count": 0, "warning_lines": []}

    results_by_file = defaultdict(list)
    for test in report.get("tests", []):
        filepath, *rest = test["nodeid"].split("::")
        test_name = "::".join(rest)
        duration = test.get("call", {}).get("duration", 0.0)

        results_by_file[filepath].append({
            "name": test_name,
            "nodeid": test["nodeid"],  # Guardamos el nodeid original
            "outcome": test["outcome"],
            "duration": duration
        })

    # Leer warnings del archivo generado
    warnings_file = Path("tests/reports/warnings.txt")
    warning_lines = []
    if warnings_file.exists():
        with open(warnings_file) as f:
            lines = f.readlines()
            if len(lines) > 2:  # Skip header lines
                warning_lines = [line.strip() for line in lines[2:] if line.strip()]

    return {
        "summary": report.get("summary", {}),
        "tests": report.get("tests", []),
        "by_file": results_by_file,
        "warning_count": warning_count,
        "warning_lines": warning_lines
    }

def display_results(test_structure: dict, results_by_file: dict):
    """Muestra los resultados de forma organizada en la terminal."""
    def _count_outcomes(tests_in_file: list) -> tuple:
        """Cuenta passed/failed/skipped en una lista de tests."""
        passed = sum(1 for t in tests_in_file if t.get('outcome') == 'passed')
        failed = sum(1 for t in tests_in_file if t.get('outcome') == 'failed')
        skipped = sum(1 for t in tests_in_file if t.get('outcome') == 'skipped')
        return passed, failed, skipped

    def _status_and_color(passed: int, failed: int) -> tuple:
        """Devuelve el icono de estado y color según counts."""
        status_icon = ICONS["PASSED"] if failed == 0 and passed > 0 else ICONS["FAILED"]
        color = COLORS["GREEN"] if failed == 0 else COLORS["RED"]
        return status_icon, color

    def _print_file_result(file_path: Path, tests_in_file: list) -> None:
        """Imprime la línea de resumen para un fichero de tests."""
        passed, failed, skipped = _count_outcomes(tests_in_file)
        status_icon, color = _status_and_color(passed, failed)
        print(f"      {status_icon} {color}{file_path.name}{COLORS['ENDC']} "
              f"({ICONS['PASSED']} {passed}, {ICONS['FAILED']} {failed}, {ICONS['SKIPPED']} {skipped})")

    for scope, modules in test_structure.items():
        print_header(f"{scope} TESTS")
        for module, layers in modules.items():
            print(f"\n  {COLORS['BLUE']}{ICONS['FOLDER']} Módulo: {module}{COLORS['ENDC']}")
            for layer, files in layers.items():
                print(f"    {COLORS['YELLOW']}Capa: {layer}{COLORS['ENDC']}")
                for file_path in files:
                    str_path = str(file_path)
                    tests_in_file = results_by_file.get(str_path, [])
                    _print_file_result(file_path, tests_in_file)

def _write_markdown_header(f, success_rate: float, failed: int) -> None:
    """Escribe el encabezado del reporte Markdown."""
    f.write("# 🚀 Resumen de Ejecución de Tests\n\n")
    f.write(f"- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    result_status = '✅ ÉXITO' if (success_rate == 100 and failed == 0) else '❌ FALLIDO'
    f.write(f"- **Resultado General**: {result_status}\n\n")

def _write_warnings_section(f, warning_count: int, warning_lines: list) -> None:
    """Escribe la sección de warnings si las hay."""
    if warning_count > 0:
        f.write("## ⚠️ Warnings\n\n")
        f.write(f"Se encontraron **{warning_count}** warnings durante la ejecución:\n\n")
        if warning_lines:
            for warning_line in warning_lines:
                f.write(f"- `{warning_line}`\n")
        f.write("\n")

def _write_global_stats(f, summary: dict, success_rate: float, total_time: float, warning_count: int) -> None:
    """Escribe la tabla de estadísticas globales."""
    f.write("## 📊 Estadísticas Globales\n\n")
    f.write("| Métrica | Valor |\n|---|---|\n")
    f.write(f"| ✅ **Tests Pasados** | {summary.get('passed', 0)} |\n")
    f.write(f"| ❌ **Tests Fallados** | {summary.get('failed', 0)} |\n")
    f.write(f"| ⚠️ **Tests Omitidos** | {summary.get('skipped', 0)} |\n")
    f.write(f"| ⚠️ **Warnings** | {warning_count} |\n")
    f.write(f"| **Total de Tests** | {summary.get('total', 0)} |\n")
    f.write(f"| **Tasa de Éxito** | {success_rate:.2f}% |\n")
    f.write(f"| ⏱️ **Duración Total** | {total_time:.2f} segundos |\n\n")

def _write_test_details(f, filepath: str, tests: list, slowest_test_nodeids: set, test_lookup: dict) -> None:
    """Escribe los detalles de los tests de un archivo."""
    f.write(f"---\n\n### {ICONS['FOLDER']} `{filepath}`\n\n")
    docstrings = get_docstrings_from_file(filepath)
    for test in sorted(tests, key=lambda x: x['name']):
        status_icon = ICONS.get(test['outcome'].upper(), "❓")
        description = ' '.join(docstrings.get(test['name'], "No description provided.").split())
        test_nodeid = test['nodeid']
        full_test_data = test_lookup.get(test_nodeid)
        slow_icon = f" {ICONS['SLOW']}" if test_nodeid in slowest_test_nodeids else ""
        f.write(f"- {status_icon} **`{test['name']}`** ({test['duration']:.4f}s){slow_icon}\n")
        f.write(f"  > _{description}_\n")
        if test['outcome'] == 'failed' and full_test_data:
            longrepr = full_test_data.get("call", {}).get("longrepr")
            if longrepr:
                f.write("\n  ```text\n")
                f.write(longrepr)
                f.write("\n  ```\n")
        f.write("\n")

def generate_markdown_report(results: dict, total_time: float):
    """Genera un fichero Markdown con el resumen de los tests."""
    summary = results["summary"]
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    total = summary.get("total", 0)
    warning_count = results.get("warning_count", 0)
    warning_lines = results.get("warning_lines", [])
    success_rate = (passed / total * 100) if total > 0 else 0

    report_path = REPORTS_DIR / "test_summary.md"
    slowest_tests = sorted([t for t in results['tests'] if t.get('outcome') == 'passed'],
                           key=lambda x: x.get('call', {}).get('duration', 0.0),
                           reverse=True)

    # Crear lookup optimizado y set para búsquedas rápidas
    test_lookup = {test['nodeid']: test for test in results['tests']}
    slowest_test_nodeids = {test['nodeid'] for test in slowest_tests[:5]}

    with open(report_path, "w") as f:
        _write_markdown_header(f, success_rate, failed)
        _write_global_stats(f, summary, success_rate, total_time, warning_count)
        _write_warnings_section(f, warning_count, warning_lines)

        for filepath, tests in sorted(results["by_file"].items()):
            _write_test_details(f, filepath, tests, slowest_test_nodeids, test_lookup)

    print(f"\n{ICONS['DOC']} Reporte Markdown generado en: {report_path}")

def display_summary(summary: dict, tests: list, warning_count: int, total_time: float):
    """Muestra un resumen final elegante y detallado."""
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    skipped = summary.get("skipped", 0)
    error = summary.get("error", 0)
    total = summary.get("total", 0)
    success_rate = (passed / total * 100) if total > 0 else 0
    summary_color = COLORS["GREEN"] if failed == 0 and error == 0 else COLORS["RED"]

    print_header(f"{ICONS['SUMMARY']} RESUMEN DE LA EJECUCIÓN")
    print(f"{summary_color}{COLORS['BOLD']}Resultado Final: {'¡TODOS LOS TESTS PASARON!' if success_rate == 100 else '¡HAN FALLADO TESTS!'}{COLORS['ENDC']}")
    print(f"  - {ICONS['PASSED']} Pasaron: {passed}")
    print(f"  - {ICONS['FAILED']} Fallaron: {failed}")
    print(f"  - {ICONS['ERROR']} Errores: {error}")
    print(f"  - {ICONS['SKIPPED']} Omitidos: {skipped}")
    print(f"  - {ICONS['WARNING']} Warnings: {warning_count}")
    print(f"  - Total: {total} tests")
    print("-" * 40)
    print(f"  - {COLORS['GREEN']}{COLORS['BOLD']}Tasa de Éxito: {success_rate:.2f}%{COLORS['ENDC']}")
    print(f"  - {ICONS['TIME']} Tiempo Total: {total_time:.2f} segundos")

    if tests:
        slowest_tests = sorted([t for t in tests if t['outcome'] == 'passed'], key=lambda x: x.get('call', {}).get('duration', 0.0), reverse=True)[:3]
        if slowest_tests:
            print("\n" + f"  {ICONS['SLOW']} Top 3 Tests (Pasados) Más Lentos:")
            for test in slowest_tests:
                name = test['nodeid'].split('::')[-1]
                duration = test.get('call', {}).get('duration', 0.0)
                print(f"    - {duration:.4f}s - {name}")

# --- Punto de Entrada ---

def main():
    """Función principal del script."""
    start_time = time.time()

    test_structure = discover_tests()
    report_file, warning_count = run_tests()
    results = process_results(report_file, warning_count)

    display_results(test_structure, results["by_file"])

    total_time = time.time() - start_time
    display_summary(results["summary"], results["tests"], results.get("warning_count", 0), total_time)

    # Generar el nuevo reporte en Markdown
    generate_markdown_report(results, total_time)

    if results["summary"].get("failed", 0) > 0 or results["summary"].get("error", 0) > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()