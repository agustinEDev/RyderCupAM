"""
El freno del login en memoria (BE #732, ADR-043).

  #   caso                                                 | esperado
  ----|-----------------------------------------------------|------------------------------
  F1  5 intentos en un minuto desde un origen               | el sexto no se admite
  F2  pasado el minuto                                      | vuelve a admitir
  F3  otro origen u otro correo                             | sus propios intentos
  F4  10 fallos de un origen                                | bloqueado 30 min desde el 10
  F5  el bloqueo de un origen                               | no toca a otro origen ni a otro correo
  F6  pasados los 30 min                                    | desbloqueado y a cero
  F7  los fallos de hace más de 30 min                      | no cuentan
  F8  acertar (olvida)                                      | a cero ese origen; no los demás
  F9  el desbloqueo del administrador                       | borra todos los orígenes del correo;
                                                            |   dice si había alguno bloqueado
  F10 el correo, con mayúsculas o espacios                  | el mismo contador
  F11 con el rate limit apagado (tests)                     | admite siempre; el bloqueo sigue
  F12 muchas parejas viejas                                 | se limpian solas: la memoria no crece
  F13 más parejas vivas que el tope                         | se van las más viejas; la memoria
                                                            |   tiene techo
  F14 una pareja vieja que se vuelve a usar                 | pasa al final: no es la que se va
  F15 con el tope lleno de parejas nuevas                   | un bloqueo vivo NO se va: llenar el
                                                            |   freno de basura no lo levanta
  F16 preguntar si una cuenta tiene bloqueos                | no borra nada
"""

from datetime import datetime, timedelta

from src.config.freno_del_login import (
    FALLOS_QUE_BLOQUEAN,
    INTENTOS_POR_MINUTO,
    MINUTOS_DE_BLOQUEO,
    FrenoDelLoginEnMemoria,
)
from src.modules.user.application.ports.freno_del_login_port import (
    origen_de_dispositivo,
    origen_de_red,
)

ANA = "ana@example.com"
A = origen_de_red("203.0.113.7")
B = origen_de_red("198.51.100.9")


class Reloj:
    def __init__(self):
        self.ahora = datetime(2026, 11, 6, 10, 0)

    def __call__(self):
        return self.ahora

    def avanza(self, **kw):
        self.ahora += timedelta(**kw)


def _freno(activo=True, tope=None):
    reloj = Reloj()
    extra = {"maximo_de_parejas": tope} if tope else {}
    return FrenoDelLoginEnMemoria(reloj=reloj, limita_intentos=lambda: activo, **extra), reloj


def test_los_numeros():
    """
    Given: El freno de BE #732
    When: Se leen sus constantes
    Then: 5 intentos por minuto, 10 fallos bloquean 30 minutos
    """
    assert (INTENTOS_POR_MINUTO, FALLOS_QUE_BLOQUEAN, MINUTOS_DE_BLOQUEO) == (5, 10, 30)


def test_f1_f2_cinco_intentos_por_minuto():
    """
    Given: Un origen que intenta 5 veces en un minuto
    When: Intenta la sexta, y otra pasado el minuto
    Then: La sexta no se admite; pasado el minuto, sí
    """
    freno, reloj = _freno()
    assert all(freno.admite_intento(ANA, A) for _ in range(5))
    assert not freno.admite_intento(ANA, A)

    reloj.avanza(seconds=60)
    assert freno.admite_intento(ANA, A)


def test_f3_otro_origen_u_otro_correo_tienen_sus_intentos():
    """
    Given: El origen A agotó sus intentos para Ana
    When: Intenta B para Ana, o A para otro correo
    Then: Se admiten
    """
    freno, _ = _freno()
    for _ in range(6):
        freno.admite_intento(ANA, A)

    assert freno.admite_intento(ANA, B)
    assert freno.admite_intento("luis@example.com", A)


def test_f4_f5_diez_fallos_bloquean_ese_origen_y_solo_ese():
    """
    Given: 9 fallos de A para Ana
    When: Falla la décima
    Then: A queda bloqueado 30 min para Ana; B y otro correo, no
    """
    freno, reloj = _freno()
    for _ in range(9):
        assert freno.apunta_fallo(ANA, A) is None
    hasta = freno.apunta_fallo(ANA, A)

    assert hasta == reloj.ahora + timedelta(minutes=30)
    assert freno.bloqueado_hasta(ANA, A) == hasta
    assert freno.bloqueado_hasta(ANA, B) is None
    assert freno.bloqueado_hasta("luis@example.com", A) is None


def test_f6_pasados_los_30_minutos_se_desbloquea_a_cero():
    """
    Given: A bloqueado para Ana
    When: Pasan 30 minutos y falla otra vez
    Then: Ya no está bloqueado, y ese fallo es el primero
    """
    freno, reloj = _freno()
    for _ in range(10):
        freno.apunta_fallo(ANA, A)

    reloj.avanza(minutes=29, seconds=59)
    assert freno.bloqueado_hasta(ANA, A) is not None
    reloj.avanza(seconds=1)
    assert freno.bloqueado_hasta(ANA, A) is None
    for _ in range(9):
        assert freno.apunta_fallo(ANA, A) is None


def test_f7_los_fallos_de_hace_mas_de_30_minutos_no_cuentan():
    """
    Given: 9 fallos de A para Ana a las 10:00
    When: Falla otra vez a las 10:31
    Then: No bloquea: los de antes ya no cuentan
    """
    freno, reloj = _freno()
    for _ in range(9):
        freno.apunta_fallo(ANA, A)
    reloj.avanza(minutes=31)

    assert freno.apunta_fallo(ANA, A) is None


def test_f8_acertar_pone_a_cero_ese_origen_y_no_los_demas():
    """
    Given: 9 fallos de A y 9 de B para Ana
    When: Acierta desde A
    Then: A vuelve a cero (otros 9 sin bloquear); B bloquea con el siguiente
    """
    freno, _ = _freno()
    for _ in range(9):
        freno.apunta_fallo(ANA, A)
        freno.apunta_fallo(ANA, B)

    freno.olvida(ANA, A)

    for _ in range(9):
        assert freno.apunta_fallo(ANA, A) is None
    assert freno.apunta_fallo(ANA, B) is not None


def test_f9_el_desbloqueo_del_administrador_borra_todo_el_correo():
    """
    Given: A bloqueado para Ana, un dispositivo con fallos, y A bloqueado para Luis
    When: El administrador desbloquea a Ana
    Then: Ana queda sin bloqueos ni fallos; Luis sigue bloqueado. Sin nada que
          borrar, lo dice
    """
    freno, _ = _freno()
    movil = origen_de_dispositivo("D7A0C6E2-0000-4000-8000-000000000001")
    for _ in range(10):
        freno.apunta_fallo(ANA, A)
        freno.apunta_fallo("luis@example.com", A)
    for _ in range(9):
        freno.apunta_fallo(ANA, movil)

    assert freno.olvida_la_cuenta(ANA) is True

    assert freno.bloqueado_hasta(ANA, A) is None
    assert freno.apunta_fallo(ANA, movil) is None
    assert freno.bloqueado_hasta("luis@example.com", A) is not None
    assert freno.olvida_la_cuenta("pepe@example.com") is False


def test_f10_el_correo_normalizado_es_el_mismo_contador():
    """
    Given: 9 fallos para «ana@example.com»
    When: Falla «  ANA@Example.com »
    Then: Bloquea: es el mismo correo
    """
    freno, _ = _freno()
    for _ in range(9):
        freno.apunta_fallo(ANA, A)

    assert freno.apunta_fallo("  ANA@Example.com ", A) is not None


def test_f11_con_el_rate_limit_apagado_admite_siempre_pero_bloquea():
    """
    Given: El rate limit apagado, como lo apagan algunos tests
    When: 20 intentos en un minuto y 10 fallos
    Then: Los admite todos, y los 10 fallos bloquean igual: es seguridad, no cupo
    """
    freno, _ = _freno(activo=False)

    assert all(freno.admite_intento(ANA, A) for _ in range(20))
    for _ in range(10):
        freno.apunta_fallo(ANA, A)
    assert freno.bloqueado_hasta(ANA, A) is not None


def test_f12_las_parejas_viejas_se_limpian_solas():
    """
    Given: 5000 correos distintos con un intento y un fallo cada uno
    When: Pasa una hora y llega otro intento
    Then: El freno ya no guarda ninguno de aquellos
    """
    freno, reloj = _freno()
    for i in range(5000):
        freno.admite_intento(f"u{i}@example.com", A)
        freno.apunta_fallo(f"u{i}@example.com", A)

    reloj.avanza(hours=1)
    freno.admite_intento(ANA, A)

    assert freno.parejas_guardadas() <= 1


def test_el_dispositivo_es_el_mismo_con_mayusculas():
    """
    Given: El id de un dispositivo en mayúsculas y en minúsculas
    When: Se hace su origen
    Then: Es el mismo
    """
    assert origen_de_dispositivo("ABC-1") == origen_de_dispositivo("abc-1")


def test_f13_con_mas_parejas_que_el_tope_se_van_las_mas_viejas():
    """
    Given: Un tope de 100 parejas
    When: Fallan 150 correos distintos, uno detrás de otro
    Then: Guarda como mucho 100, y son las últimas
    """
    freno, reloj = _freno(tope=100)
    for i in range(150):
        reloj.avanza(seconds=1)
        freno.apunta_fallo(f"u{i}@example.com", A)

    assert freno.parejas_guardadas() <= 100
    for _ in range(9):
        freno.apunta_fallo("u149@example.com", A)
    assert freno.bloqueado_hasta("u149@example.com", A) is not None


def test_f14_una_pareja_que_se_vuelve_a_usar_no_es_la_que_se_va():
    """
    Given: Un tope de 3 parejas y Ana con 9 fallos, la primera en llegar
    When: Ana falla otra vez (pasa al final) y llegan otras dos parejas
    Then: Ana sigue guardada: su décimo fallo la bloquea
    """
    freno, _reloj = _freno(tope=3)
    for _ in range(8):
        freno.apunta_fallo(ANA, A)
    freno.apunta_fallo("b@example.com", A)
    freno.apunta_fallo(ANA, A)  # Ana pasa al final
    freno.apunta_fallo("c@example.com", A)
    freno.apunta_fallo("d@example.com", A)  # se va b, no Ana

    assert freno.apunta_fallo(ANA, A) is not None


def test_f15_un_bloqueo_vivo_no_se_expulsa_aunque_se_llene_el_tope():
    """
    Given: Un tope de 3 parejas y la red A bloqueada para Ana
    When: Se bloquean otras 5 parejas
    Then: Ana sigue bloqueada: un atacante no levanta un bloqueo llenando el freno
    """
    freno, _reloj = _freno(tope=3)
    for _ in range(10):
        freno.apunta_fallo(ANA, A)
    for i in range(5):
        for _ in range(10):
            freno.apunta_fallo(f"basura{i}@example.com", A)

    assert freno.bloqueado_hasta(ANA, A) is not None


def test_f16_tiene_bloqueos_no_borra_nada():
    """
    Given: La red A bloqueada para Ana, y 3 fallos de B
    When: Se pregunta si Ana tiene bloqueos, y por Luis
    Then: Ana sí, Luis no, y lo de Ana sigue igual
    """
    freno, _reloj = _freno()
    for _ in range(10):
        freno.apunta_fallo(ANA, A)
    for _ in range(3):
        freno.apunta_fallo(ANA, B)

    assert freno.tiene_bloqueos(ANA)
    assert not freno.tiene_bloqueos("luis@example.com")
    assert freno.bloqueado_hasta(ANA, A) is not None
    for _ in range(6):
        assert freno.apunta_fallo(ANA, B) is None
    assert freno.apunta_fallo(ANA, B) is not None
