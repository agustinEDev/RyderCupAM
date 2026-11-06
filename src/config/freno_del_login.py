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
"""

import hashlib
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta

from limits import parse

from src.config.rate_limit import LOGIN_ATTEMPTS_PER_EMAIL_LIMIT, email_rate_limit_key, limiter
from src.modules.user.application.ports.freno_del_login_port import IFrenoDelLogin

INTENTOS_POR_MINUTO = parse(LOGIN_ATTEMPTS_PER_EMAIL_LIMIT).amount
FALLOS_QUE_BLOQUEAN = 10
MINUTOS_DE_BLOQUEO = 30

UN_MINUTO = timedelta(minutes=1)
VENTANA_DE_FALLOS = timedelta(minutes=MINUTOS_DE_BLOQUEO)
BLOQUEO = timedelta(minutes=MINUTOS_DE_BLOQUEO)
# Cada cuánto se barren las parejas que ya no cuentan nada
CADA_CUANTO_SE_LIMPIA = timedelta(minutes=1)


class FrenoDelLoginEnMemoria(IFrenoDelLogin):
    """Intentos, fallos y bloqueos de cada pareja correo + origen."""

    def __init__(
        self,
        reloj: Callable[[], datetime] = datetime.now,
        limita_intentos: Callable[[], bool] = lambda: limiter.enabled,
    ):
        self._reloj = reloj
        # El cupo de intentos es un rate limit: se apaga con él (los tests). El
        # bloqueo por fallos es seguridad y no se apaga nunca
        self._limita_intentos = limita_intentos
        self._intentos: dict[tuple[str, str], deque[datetime]] = {}
        self._fallos: dict[tuple[str, str], deque[datetime]] = {}
        self._bloqueos: dict[tuple[str, str], datetime] = {}
        self._ultimo_barrido = reloj()

    @staticmethod
    def _clave(email: str, origen: str) -> tuple[str, str]:
        # El origen también en hash: lleva la IP, y la clave puede acabar en un volcado
        return email_rate_limit_key(email), hashlib.sha256(origen.encode()).hexdigest()

    def _barre(self, ahora: datetime) -> None:
        if ahora - self._ultimo_barrido < CADA_CUANTO_SE_LIMPIA:
            return
        self._ultimo_barrido = ahora
        for tabla, ventana in ((self._intentos, UN_MINUTO), (self._fallos, VENTANA_DE_FALLOS)):
            for clave in [
                c for c, marcas in tabla.items() if not marcas or marcas[-1] <= ahora - ventana
            ]:
                del tabla[clave]
        for clave in [c for c, hasta in self._bloqueos.items() if hasta <= ahora]:
            del self._bloqueos[clave]

    @staticmethod
    def _recientes(tabla: dict, clave, desde: datetime) -> deque[datetime]:
        marcas = tabla.setdefault(clave, deque())
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
        self._bloqueos[clave] = hasta
        return hasta

    def olvida(self, email: str, origen: str) -> None:
        self._fallos.pop(self._clave(email, origen), None)

    def olvida_la_cuenta(self, email: str) -> bool:
        cuenta = email_rate_limit_key(email)
        ahora = self._reloj()
        habia = any(c[0] == cuenta and hasta > ahora for c, hasta in self._bloqueos.items())
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
