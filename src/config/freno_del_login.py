"""
El freno del login por correo y origen, en memoria (BE #732, ADR-043).

- 5 intentos por minuto por pareja correo + origen (antes, por correo desde
  cualquier red: cinco intentos ajenos dejaban al dueño en 429).
- 10 fallos en 30 minutos bloquean ESE origen 30 minutos para ese correo. Los demás
  orígenes siguen entrando.

En memoria, como los demás límites (la API corre en un solo proceso): un despliegue o
un reinicio lo pone a cero, y el atacante ganaría como mucho otros 10 intentos por
red. El respaldo de la cuenta (50 en una hora, todas las redes) sí está en la BD.

El correo se guarda en hash, como en los demás contadores. Todo es síncrono y sin
`await`: dentro del bucle de asyncio cada operación es atómica.

Con techo de memoria (auditoría OWASP, A04): como mucho MAXIMO_DE_PAREJAS por tabla.
Cada pareja que se usa pasa al final, así que las del principio son las más viejas:
cada operación borra las que ya no cuentan desde el principio (sin recorrer todo), y
con el tope lleno se va la más vieja.
"""

import hashlib
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta

from limits import parse

from src.config import rate_limit
from src.config.rate_limit import LOGIN_ATTEMPTS_PER_EMAIL_LIMIT, email_rate_limit_key, limiter
from src.modules.user.application.ports.freno_del_login_port import IFrenoDelLogin
from src.modules.user.domain.services.freno_del_login import (
    FALLOS_POR_ORIGEN,
    MINUTOS_DE_BLOQUEO_POR_ORIGEN,
    MINUTOS_DE_LA_VENTANA_POR_ORIGEN,
)

INTENTOS_POR_MINUTO = parse(LOGIN_ATTEMPTS_PER_EMAIL_LIMIT).amount
FALLOS_QUE_BLOQUEAN = FALLOS_POR_ORIGEN
MINUTOS_DE_BLOQUEO = MINUTOS_DE_BLOQUEO_POR_ORIGEN

UN_MINUTO = timedelta(minutes=1)
VENTANA_DE_FALLOS = timedelta(minutes=MINUTOS_DE_LA_VENTANA_POR_ORIGEN)
BLOQUEO = timedelta(minutes=MINUTOS_DE_BLOQUEO)
# Unos 2,7 KB por pareja (medido): 50.000 de intentos y de fallos son unos 150 MB
# como mucho. Los bloqueos vivos no cuentan para el tope: no se expulsan nunca, y los
# acota el techo de fallos de cada red
MAXIMO_DE_PAREJAS = 50_000


class FrenoDelLoginEnMemoria(IFrenoDelLogin):
    """Intentos, fallos y bloqueos de cada pareja correo + origen."""

    def __init__(
        self,
        reloj: Callable[[], datetime] = datetime.now,
        limita_intentos: Callable[[], bool] = lambda: limiter.enabled,
        maximo_de_parejas: int = MAXIMO_DE_PAREJAS,
    ):
        self._reloj = reloj
        # El cupo de intentos es un rate limit: se apaga con él (los tests). El
        # bloqueo por fallos es seguridad y no se apaga nunca
        self._limita_intentos = limita_intentos
        self._intentos: dict[tuple[str, str], deque[datetime]] = {}
        self._fallos: dict[tuple[str, str], deque[datetime]] = {}
        self._bloqueos: dict[tuple[str, str], datetime] = {}
        self._maximo = maximo_de_parejas

    @staticmethod
    def _clave(email: str, origen: str) -> tuple[str, str]:
        # El origen también en hash: lleva la IP, y la clave puede acabar en un volcado
        return email_rate_limit_key(email), hashlib.sha256(origen.encode()).hexdigest()

    def _barre(self, ahora: datetime) -> None:
        """Borra desde el principio (las más viejas) las parejas que ya no cuentan."""
        for tabla, ventana in ((self._intentos, UN_MINUTO), (self._fallos, VENTANA_DE_FALLOS)):
            while tabla:
                clave, marcas = next(iter(tabla.items()))
                if marcas and marcas[-1] > ahora - ventana:
                    break
                del tabla[clave]
        # Los bloqueos duran todos lo mismo: el primero en entrar es el primero en acabar
        while self._bloqueos:
            clave, hasta = next(iter(self._bloqueos.items()))
            if hasta > ahora:
                break
            del self._bloqueos[clave]

    def _al_final(self, tabla: dict, clave, nuevo):
        """Lleva la pareja al final (la más reciente) y respeta el tope."""
        valor = tabla.pop(clave, None)
        tabla[clave] = nuevo() if valor is None else valor
        while len(tabla) > self._maximo:
            del tabla[next(iter(tabla))]
        return tabla[clave]

    def tiene_bloqueos(self, email: str) -> bool:
        cuenta = email_rate_limit_key(email)
        ahora = self._reloj()
        return any(c[0] == cuenta and hasta > ahora for c, hasta in self._bloqueos.items())

    def _recientes(self, tabla: dict, clave, desde: datetime) -> deque[datetime]:
        marcas = self._al_final(tabla, clave, deque)
        while marcas and marcas[0] <= desde:
            marcas.popleft()
        return marcas

    def admite_intento(self, email: str, origen: str) -> bool:
        ahora = self._reloj()
        self._barre(ahora)
        if not self._limita_intentos():
            return True
        marcas = self._recientes(self._intentos, self._clave(email, origen), ahora - UN_MINUTO)
        if len(marcas) >= INTENTOS_POR_MINUTO:
            return False
        marcas.append(ahora)
        return True

    def bloqueado_hasta(self, email: str, origen: str) -> datetime | None:
        clave = self._clave(email, origen)
        hasta = self._bloqueos.get(clave)
        if hasta is None:
            return None
        if hasta <= self._reloj():
            del self._bloqueos[clave]
            return None
        return hasta

    def apunta_fallo(self, email: str, origen: str) -> datetime | None:
        ahora = self._reloj()
        self._barre(ahora)
        clave = self._clave(email, origen)
        marcas = self._recientes(self._fallos, clave, ahora - VENTANA_DE_FALLOS)
        marcas.append(ahora)
        if len(marcas) < FALLOS_QUE_BLOQUEAN:
            return None
        # Bloqueado: el contador empieza de cero cuando el bloqueo acabe
        del self._fallos[clave]
        hasta = ahora + BLOQUEO
        # Al final y sin tope: un bloqueo vivo no se expulsa (code-review). Duran
        # todos lo mismo, así que el orden de entrada es el de salida
        self._bloqueos.pop(clave, None)
        self._bloqueos[clave] = hasta
        return hasta

    def olvida(self, email: str, origen: str) -> None:
        self._fallos.pop(self._clave(email, origen), None)

    def techo_de_la_red_agotado(self, red: str) -> bool:
        # El de siempre (#273), en el almacenamiento de slowapi: se apaga con él
        return rate_limit.failed_logins_exhausted(red)

    def apunta_fallo_en_la_red(self, red: str) -> None:
        rate_limit.record_failed_login(red)

    def olvida_la_cuenta(self, email: str) -> bool:
        cuenta = email_rate_limit_key(email)
        habia = self.tiene_bloqueos(email)
        for tabla in (self._intentos, self._fallos, self._bloqueos):
            for clave in [c for c in tabla if c[0] == cuenta]:
                del tabla[clave]
        return habia

    def parejas_guardadas(self) -> int:
        """Cuántas parejas guarda (para los tests de memoria)."""
        return len(set(self._intentos) | set(self._fallos) | set(self._bloqueos))

    def reinicia(self) -> None:
        """Todo a cero (para los tests, entre uno y otro)."""
        self._intentos.clear()
        self._fallos.clear()
        self._bloqueos.clear()


# El de la app: uno para todo el proceso, como el limiter
freno_del_login = FrenoDelLoginEnMemoria()
