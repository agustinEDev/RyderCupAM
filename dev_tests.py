# -*- coding: utf-8 -*-
"""
Script para ejecutar todos los tests del proyecto y mostrar estadísticas atractivas.

Uso:
    python dev_tests.py

Este script:
- Descubre y ejecuta todos los tests con pytest
- Muestra resumen de tests pasados, fallados y porcentaje
- Salida colorida y clara para desarrollo
"""

import sys
import subprocess
import platform
from datetime import datetime

# ================================
# CONFIGURACIÓN DE COLORES
# ================================
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# ================================
# EJECUCIÓN DE TESTS
# ================================
def run_pytest():
    """
    Ejecuta pytest y captura la salida.
    Returns:
        tuple: (exit_code, output)
    """
    print(f"{Colors.OKCYAN}🔎 Buscando y ejecutando todos los tests del proyecto...{Colors.ENDC}")
    
    # Optimizaciones de rendimiento para tests
    cmd = [
        sys.executable, '-m', 'pytest', 'tests/',
        '--maxfail=5',              # Para rápido si hay fallos
        '--disable-warnings',       # Sin warnings
        '--tb=short',              # Stack traces cortos
        '-v',                      # Verbose output
        '--durations=0',           # Mostrar duración de tests
        '--cache-clear'            # Limpiar cache para tiempos reales
    ]
    
    # Detectar si pytest-xdist está disponible para paralelización
    try:
        import importlib.util
        if importlib.util.find_spec("xdist") is not None:
            import multiprocessing
            # Usar CPUs - 1 para dejar recursos al sistema
            workers = max(1, multiprocessing.cpu_count() - 1)
            cmd.extend(['-n', str(workers)])
            print(f"{Colors.OKCYAN}🚀 Ejecutando tests en paralelo con {workers} workers...{Colors.ENDC}")
        else:
            raise ImportError("xdist no encontrado")
    except ImportError:
        print(f"{Colors.WARNING}⚡ Tip: instala 'pytest-xdist' para tests paralelos más rápidos{Colors.ENDC}")
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.returncode, result.stdout

# ================================
# PARSEO DE RESULTADOS
# ================================
def parse_results(output):
    """
    Parsea la salida de pytest para extraer estadísticas.
    Returns:
        dict: stats con keys: total, passed, failed, errors, skipped
    """
    import re
    stats = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'errors': 0,
        'skipped': 0
    }
    # Busca líneas tipo: "== 18 passed, 2 failed, 1 skipped in ... =="
    summary = re.findall(r"=+ ([\d]+) passed(?:, ([\d]+) failed)?(?:, ([\d]+) skipped)?(?:, ([\d]+) errors)? in", output)
    if summary:
        passed = int(summary[0][0])
        failed = int(summary[0][1]) if summary[0][1] else 0
        skipped = int(summary[0][2]) if summary[0][2] else 0
        errors = int(summary[0][3]) if summary[0][3] else 0
        stats['passed'] = passed
        stats['failed'] = failed
        stats['skipped'] = skipped
        stats['errors'] = errors
        stats['total'] = passed + failed + skipped + errors
    return stats

# ================================
# ORGANIZACIÓN DE RESULTADOS
# ================================
def categorize_tests(output):
    """
    Organiza los tests por capas/categorías y por objetos específicos.
    Returns:
        dict: tests organizados por categoría y objeto
    """
    categories = {
        'unit': {
            'domain': {
                'entities': {
                    'user': [],
                    'team': [],
                    'tournament': [],
                    'other': []
                },
                'value_objects': {
                    'user_id': [],
                    'email': [],
                    'password': [],
                    'other': []
                },
                'repositories': {
                    'user_repository': [],
                    'team_repository': [],
                    'other': []
                },
                'services': {
                    'domain_services': [],
                    'other': []
                }
            },
            'application': {
                'use_cases': {
                    'user_use_cases': [],
                    'team_use_cases': [],
                    'other': []
                },
                'services': {
                    'app_services': [],
                    'other': []
                },
                'handlers': {
                    'command_handlers': [],
                    'query_handlers': [],
                    'other': []
                }
            },
            'infrastructure': {
                'repositories': {
                    'user_repository': [],
                    'team_repository': [],
                    'other': []
                },
                'adapters': {
                    'database_adapters': [],
                    'external_adapters': [],
                    'other': []
                },
                'external_services': {
                    'api_clients': [],
                    'other': []
                }
            }
        },
        'integration': {
            'api': {
                'endpoints': {
                    'health': [],
                    'user_endpoints': [],
                    'team_endpoints': [],
                    'auth_endpoints': [],
                    'other': []
                },
                'middleware': {
                    'auth_middleware': [],
                    'cors_middleware': [],
                    'other': []
                },
                'auth': {
                    'jwt_auth': [],
                    'oauth': [],
                    'other': []
                }
            },
            'database': {
                'repositories': {
                    'user_repository': [],
                    'team_repository': [],
                    'other': []
                },
                'migrations': {
                    'schema_migrations': [],
                    'data_migrations': [],
                    'other': []
                },
                'queries': {
                    'complex_queries': [],
                    'other': []
                }
            },
            'services': {
                'external_apis': {
                    'third_party_apis': [],
                    'other': []
                },
                'messaging': {
                    'event_messaging': [],
                    'other': []
                },
                'files': {
                    'file_storage': [],
                    'other': []
                }
            }
        },
        'e2e': [],
        'otros': []
    }
    
    for line in output.splitlines():
        if line.strip().startswith('tests/') and ('PASSED' in line or 'FAILED' in line or 'SKIPPED' in line):
            # Determinar categoría basada en la ruta
            if 'tests/unit/' in line:
                if '/domain/' in line:
                    if '/entities/' in line:
                        if '/user/' in line or 'test_user' in line:
                            categories['unit']['domain']['entities']['user'].append(line)
                        elif '/team/' in line or 'test_team' in line:
                            categories['unit']['domain']['entities']['team'].append(line)
                        elif '/tournament/' in line or 'test_tournament' in line:
                            categories['unit']['domain']['entities']['tournament'].append(line)
                        else:
                            categories['unit']['domain']['entities']['other'].append(line)
                    elif '/value_objects/' in line:
                        if 'test_user_id' in line or 'user_id' in line:
                            categories['unit']['domain']['value_objects']['user_id'].append(line)
                        elif 'test_email' in line or '/email' in line:
                            categories['unit']['domain']['value_objects']['email'].append(line)
                        elif 'test_password' in line or '/password' in line:
                            categories['unit']['domain']['value_objects']['password'].append(line)
                        else:
                            categories['unit']['domain']['value_objects']['other'].append(line)
                    elif '/repositories/' in line:
                        if 'user_repository' in line or '/user/' in line:
                            categories['unit']['domain']['repositories']['user_repository'].append(line)
                        elif 'team_repository' in line or '/team/' in line:
                            categories['unit']['domain']['repositories']['team_repository'].append(line)
                        else:
                            categories['unit']['domain']['repositories']['other'].append(line)
                    elif '/services/' in line:
                        categories['unit']['domain']['services']['domain_services'].append(line)
                    else:
                        categories['unit']['domain']['entities']['other'].append(line)  # Default
                elif '/application/' in line:
                    if '/use_cases/' in line:
                        categories['unit']['application']['use_cases'].append(line)
                    elif '/services/' in line:
                        categories['unit']['application']['services'].append(line)
                    elif '/handlers/' in line:
                        categories['unit']['application']['handlers'].append(line)
                    else:
                        categories['unit']['application']['use_cases'].append(line)  # Default a use_cases
                elif '/infrastructure/' in line:
                    if '/repositories/' in line:
                        categories['unit']['infrastructure']['repositories'].append(line)
                    elif '/adapters/' in line:
                        categories['unit']['infrastructure']['adapters'].append(line)
                    elif '/external_services/' in line:
                        categories['unit']['infrastructure']['external_services'].append(line)
                    else:
                        categories['unit']['infrastructure']['repositories'].append(line)  # Default a repositories
                else:
                    categories['unit']['domain']['entities'].append(line)  # Default general
            elif 'tests/integration/' in line:
                if '/api/' in line:
                    if '/endpoints/' in line or 'test_health' in line or '/api/' in line:
                        if 'health' in line or 'test_health' in line:
                            categories['integration']['api']['endpoints']['health'].append(line)
                        elif 'user' in line or '/user/' in line:
                            categories['integration']['api']['endpoints']['user_endpoints'].append(line)
                        elif 'team' in line or '/team/' in line:
                            categories['integration']['api']['endpoints']['team_endpoints'].append(line)
                        elif 'auth' in line or '/auth/' in line:
                            categories['integration']['api']['endpoints']['auth_endpoints'].append(line)
                        else:
                            categories['integration']['api']['endpoints']['other'].append(line)
                    elif '/middleware/' in line:
                        if 'auth' in line:
                            categories['integration']['api']['middleware']['auth_middleware'].append(line)
                        elif 'cors' in line:
                            categories['integration']['api']['middleware']['cors_middleware'].append(line)
                        else:
                            categories['integration']['api']['middleware']['other'].append(line)
                    elif '/auth/' in line:
                        if 'jwt' in line:
                            categories['integration']['api']['auth']['jwt_auth'].append(line)
                        elif 'oauth' in line:
                            categories['integration']['api']['auth']['oauth'].append(line)
                        else:
                            categories['integration']['api']['auth']['other'].append(line)
                    else:
                        # Default: asumir que son endpoints de salud si no hay subcarpeta específica
                        if 'health' in line or 'test_health' in line:
                            categories['integration']['api']['endpoints']['health'].append(line)
                        else:
                            categories['integration']['api']['endpoints']['other'].append(line)
                elif '/database/' in line:
                    if '/repositories/' in line:
                        categories['integration']['database']['repositories'].append(line)
                    elif '/migrations/' in line:
                        categories['integration']['database']['migrations'].append(line)
                    elif '/queries/' in line:
                        categories['integration']['database']['queries'].append(line)
                    else:
                        categories['integration']['database']['repositories'].append(line)  # Default a repositories
                elif '/services/' in line:
                    if '/external_apis/' in line:
                        categories['integration']['services']['external_apis'].append(line)
                    elif '/messaging/' in line:
                        categories['integration']['services']['messaging'].append(line)
                    elif '/files/' in line:
                        categories['integration']['services']['files'].append(line)
                    else:
                        categories['integration']['services']['external_apis'].append(line)  # Default a external_apis
                else:
                    categories['integration']['api']['endpoints'].append(line)  # Default general
            elif 'tests/e2e/' in line:
                categories['e2e'].append(line)
            else:
                categories['otros'].append(line)
    
    return categories

def get_test_icon_and_color(line):
    """
    Retorna icono y color según el resultado del test.
    """
    if 'PASSED' in line:
        return "✅", Colors.OKGREEN
    elif 'FAILED' in line:
        return "❌", Colors.FAIL
    elif 'SKIPPED' in line:
        return "⏭️ ", Colors.WARNING
    else:
        return "❓", Colors.ENDC

def print_category_results(category_name, tests, icon, indent=""):
    """
    Imprime resultados de una categoría específica.
    """
    if not tests:
        return 0, 0, 0  # passed, failed, total
    
    # Determinar indentación base
    base_indent = indent if category_name.startswith("    ") else ""
    
    print(f"\n{base_indent}{Colors.BOLD}{icon}{category_name}{Colors.ENDC}")
    
    passed = failed = 0
    for test in tests:
        test_icon, color = get_test_icon_and_color(test)
        # Extraer nombre del test y clase de forma más limpia
        test_path = test.split('::')
        if len(test_path) >= 3:
            # Formato: TestClass::test_method
            class_name = test_path[1].replace('Test', '').replace('test_', '')
            method_name = test_path[2].replace('test_', '').replace('_', ' ').title()
            test_name = f"{class_name} → {method_name}"
        elif len(test_path) >= 2:
            test_name = test_path[1].replace('test_', '').replace('_', ' ').title()
        else:
            test_name = test.split(' ')[0].replace('tests/', '').replace('test_', '')
        
        print(f"      {base_indent}{test_icon} {color}{test_name}{Colors.ENDC}")
        
        if 'PASSED' in test:
            passed += 1
        elif 'FAILED' in test:
            failed += 1
    
    total = len(tests)
    if total > 0:
        percent = 100 * passed / total
        status_color = Colors.OKGREEN if percent == 100 else Colors.WARNING if percent >= 80 else Colors.FAIL
        print(f"      {base_indent}{Colors.OKCYAN}📊 {passed}/{total} tests ({status_color}{percent:.1f}%{Colors.OKCYAN}){Colors.ENDC}")
    
    return passed, failed, total

def print_object_subcategories(category_name, objects_dict, category_icon):
    """
    Imprime subcategorías organizadas por objetos específicos.
    """
    if not any(objects_dict.values()):
        return
    
    print(f"\n    {Colors.BOLD}{category_icon} {category_name.upper()}{Colors.ENDC}")
    
    # Mapeo de nombres de objetos a iconos y nombres legibles
    object_mapping = {
        # Entities
        'user': ('👤', 'User'),
        'team': ('⚽', 'Team'), 
        'tournament': ('🏆', 'Tournament'),
        # Value Objects
        'user_id': ('🆔', 'User ID'),
        'email': ('📧', 'Email'),
        'password': ('🔐', 'Password'),
        # Repositories
        'user_repository': ('👤🗄️', 'User Repository'),
        'team_repository': ('⚽🗄️', 'Team Repository'),
        # Use Cases
        'user_use_cases': ('👤⚙️', 'User Use Cases'),
        'team_use_cases': ('⚽⚙️', 'Team Use Cases'),
        # API Endpoints
        'health': ('💚', 'Health Endpoints'),
        'user_endpoints': ('👤🌐', 'User API'),
        'team_endpoints': ('⚽🌐', 'Team API'),
        'auth_endpoints': ('🔐🌐', 'Auth API'),
        # Services
        'domain_services': ('⚙️', 'Domain Services'),
        'app_services': ('🔧', 'Application Services'),
        # Others
        'other': ('📝', 'Other')
    }
    
    for obj_key, tests in objects_dict.items():
        if tests:  # Solo mostrar si hay tests
            icon, name = object_mapping.get(obj_key, ('📄', obj_key.replace('_', ' ').title()))
            
            print(f"\n      {Colors.BOLD}{icon} {name}{Colors.ENDC}")
            
            passed = failed = 0
            for test in tests:
                test_icon, color = get_test_icon_and_color(test)
                # Extraer nombre del test y clase de forma más limpia
                test_path = test.split('::')
                if len(test_path) >= 3:
                    # Formato: TestClass::test_method
                    class_name = test_path[1].replace('Test', '').replace('test_', '')
                    method_name = test_path[2].replace('test_', '').replace('_', ' ').title()
                    test_name = f"{class_name} → {method_name}"
                elif len(test_path) >= 2:
                    test_name = test_path[1].replace('test_', '').replace('_', ' ').title()
                else:
                    test_name = test.split(' ')[0].replace('tests/', '').replace('test_', '')
                
                print(f"        {test_icon} {color}{test_name}{Colors.ENDC}")
                
                if 'PASSED' in test:
                    passed += 1
                elif 'FAILED' in test:
                    failed += 1
            
            total = len(tests)
            if total > 0:
                percent = 100 * passed / total
                status_color = Colors.OKGREEN if percent == 100 else Colors.WARNING if percent >= 80 else Colors.FAIL
                print(f"        {Colors.OKCYAN}📊 {passed}/{total} tests ({status_color}{percent:.1f}%{Colors.OKCYAN}){Colors.ENDC}")

# ================================
# SALIDA BONITA
# ================================
def print_stats(stats, output, exit_code):
    print(f"\n{Colors.HEADER}{Colors.BOLD}🧪 EJECUCIÓN DE TESTS - RYDER CUP MANAGER{Colors.ENDC}")
    print(f"{Colors.OKBLUE}📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 🖥️  {platform.system()} | 🐍 Python {platform.python_version()}{Colors.ENDC}")
    
    # Categorizar tests
    categories = categorize_tests(output)
    
    print(f"\n{Colors.HEADER}{Colors.BOLD}📊 RESULTADOS POR CAPAS{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'═' * 50}{Colors.ENDC}")
    
    # Tests Unitarios
    unit_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in categories['unit'].values())
    if unit_has_tests:
        print(f"\n{Colors.BOLD}🔬 TESTS UNITARIOS{Colors.ENDC}")
        print(f"{Colors.OKCYAN}{'─' * 20}{Colors.ENDC}")
        
        # Domain Layer
        domain_tests = categories['unit']['domain']
        domain_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in domain_tests.values())
        if domain_has_tests:
            print(f"\n  {Colors.BOLD}🏗️  CAPA DE DOMINIO{Colors.ENDC}")
            if any(domain_tests['entities'].values()):
                print_object_subcategories("Entidades", domain_tests['entities'], "📦")
            if any(domain_tests['value_objects'].values()):
                print_object_subcategories("Value Objects", domain_tests['value_objects'], "💎")
            if any(domain_tests['repositories'].values()):
                print_object_subcategories("Interfaces de Repositorio", domain_tests['repositories'], "🗄️")
            if any(domain_tests['services'].values()):
                print_object_subcategories("Servicios de Dominio", domain_tests['services'], "⚙️")
        
        # Application Layer
        app_tests = categories['unit']['application']
        app_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in app_tests.values())
        if app_has_tests:
            print(f"\n  {Colors.BOLD}⚙️  CAPA DE APLICACIÓN{Colors.ENDC}")
            if any(app_tests['use_cases'].values()):
                print_object_subcategories("Casos de Uso", app_tests['use_cases'], "🎯")
            if any(app_tests['services'].values()):
                print_object_subcategories("Servicios de Aplicación", app_tests['services'], "🔧")
            if any(app_tests['handlers'].values()):
                print_object_subcategories("Handlers", app_tests['handlers'], "📨")
        
        # Infrastructure Layer
        infra_tests = categories['unit']['infrastructure']
        infra_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in infra_tests.values())
        if infra_has_tests:
            print(f"\n  {Colors.BOLD}🔧 CAPA DE INFRAESTRUCTURA{Colors.ENDC}")
            if any(infra_tests['repositories'].values()):
                print_object_subcategories("Implementaciones de Repositorio", infra_tests['repositories'], "🗃️")
            if any(infra_tests['adapters'].values()):
                print_object_subcategories("Adaptadores", infra_tests['adapters'], "🔌")
            if any(infra_tests['external_services'].values()):
                print_object_subcategories("Servicios Externos", infra_tests['external_services'], "🌐")
    
    # Tests de Integración
    integration_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in categories['integration'].values())
    if integration_has_tests:
        print(f"\n{Colors.BOLD}🔗 TESTS DE INTEGRACIÓN{Colors.ENDC}")
        print(f"{Colors.OKCYAN}{'─' * 25}{Colors.ENDC}")
        
        # API Tests
        api_tests = categories['integration']['api']
        api_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in api_tests.values())
        if api_has_tests:
            print(f"\n  {Colors.BOLD}🌐 API{Colors.ENDC}")
            if any(api_tests['endpoints'].values()):
                print_object_subcategories("Endpoints", api_tests['endpoints'], "🎯")
            if any(api_tests['middleware'].values()):
                print_object_subcategories("Middleware", api_tests['middleware'], "🔀")
            if any(api_tests['auth'].values()):
                print_object_subcategories("Autenticación", api_tests['auth'], "🔐")
        
        # Database Tests
        db_tests = categories['integration']['database']
        db_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in db_tests.values())
        if db_has_tests:
            print(f"\n  {Colors.BOLD}🗄️  BASE DE DATOS{Colors.ENDC}")
            if any(db_tests['repositories'].values()):
                print_object_subcategories("Repositorios", db_tests['repositories'], "🗃️")
            if any(db_tests['migrations'].values()):
                print_object_subcategories("Migraciones", db_tests['migrations'], "📋")
            if any(db_tests['queries'].values()):
                print_object_subcategories("Consultas", db_tests['queries'], "🔍")
        
        # Services Tests
        service_tests = categories['integration']['services']
        service_has_tests = any(any(subcat.values()) if isinstance(subcat, dict) else subcat for subcat in service_tests.values())
        if service_has_tests:
            print(f"\n  {Colors.BOLD}🔄 SERVICIOS{Colors.ENDC}")
            if any(service_tests['external_apis'].values()):
                print_object_subcategories("APIs Externas", service_tests['external_apis'], "🌍")
            if any(service_tests['messaging'].values()):
                print_object_subcategories("Mensajería", service_tests['messaging'], "📨")
            if any(service_tests['files'].values()):
                print_object_subcategories("Archivos", service_tests['files'], "📁")
    
    # Tests E2E
    if categories['e2e']:
        print_category_results("End-to-End", categories['e2e'], "🎯")
    
    # Otros tests
    if categories['otros']:
        print_category_results("Otros", categories['otros'], "📝")
    
    # Resumen final
    print(f"\n{Colors.HEADER}{Colors.BOLD}📈 RESUMEN GENERAL{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'═' * 50}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}📊 Total tests ejecutados: {stats['total']}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}✅ Pasados: {stats['passed']}{Colors.ENDC}")
    print(f"{Colors.FAIL}❌ Fallados: {stats['failed']}{Colors.ENDC}")
    print(f"{Colors.WARNING}⏭️  Omitidos: {stats['skipped']}{Colors.ENDC}")
    print(f"{Colors.FAIL}⚠️  Errores: {stats['errors']}{Colors.ENDC}")
    
    if stats['total'] > 0:
        percent = 100 * stats['passed'] / stats['total']
        print(f"{Colors.BOLD}📊 Tests exitosos: {stats['passed']}/{stats['total']}{Colors.ENDC}")
        if percent == 100:
            print(f"{Colors.OKGREEN}{Colors.BOLD}🎉 Porcentaje de éxito: {percent:.1f}% - ¡PERFECTO!{Colors.ENDC}")
        elif percent >= 80:
            print(f"{Colors.OKGREEN}{Colors.BOLD}💪 Porcentaje de éxito: {percent:.1f}% - ¡MUY BIEN!{Colors.ENDC}")
        elif percent >= 60:
            print(f"{Colors.WARNING}{Colors.BOLD}⚠️  Porcentaje de éxito: {percent:.1f}% - MEJORABLE{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}{Colors.BOLD}🚨 Porcentaje de éxito: {percent:.1f}% - NECESITA TRABAJO{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}{'🎉 ¡TODOS LOS TESTS PASARON! 🎉' if exit_code == 0 else '🔥 HAY TESTS QUE NECESITAN ATENCIÓN 🔥'}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'═' * 50}{Colors.ENDC}")

# ================================
# MAIN
# ================================
if __name__ == "__main__":
    exit_code, output = run_pytest()
    stats = parse_results(output)
    print_stats(stats, output, exit_code)
    sys.exit(exit_code)
