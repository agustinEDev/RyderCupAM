"""
Caso de Uso: Una pasada de una actualización de hándicaps con la RFEG (#251).

Decidido con Agustín el 7 oct 2026, como hace la RFEG («el hándicap de la base
de datos tras el cierre de inscripción»). Sustituye al refresco de las 3:00 de
cada día de juego (BE #502). Al cerrar las inscripciones se crea una
actualización y se lanza esta pasada en segundo plano.

- **En un Stableford o un Medal** todavía cerrado, si la RFEG da otro
  hándicap, se corrige el fijado y se rehacen las categorías.
- **En la Ryder** solo cambia el perfil: los partidos salen de él.
- Si alguien se queda sin actualizar, la actualización queda **incompleta** y
  se avisa al organizador por correo. Una pasada sobre una incompleta termina
  solo lo que falta.
- **Al terminar** (15 nov 2026, H1-H6), el organizador recibe la lista de los
  que se quedaron sin actualizar con la RFEG (los españoles, y todos si la
  competición es en España), por correo y en Actividad; y cada español al que
  la RFEG no encontró en esta pasada, su correo y su aviso. Si la RFEG falló,
  al jugador nada.
- Si la competición empieza a mitad, la actualización se corta y la pasada
  para: lo pendiente se queda como estaba.

Cómo:

- **Uno a uno y con pausa**, con hasta 3 intentos por jugador, cada uno con
  sus propias herramientas (sesión nueva): un fallo con un jugador no arrastra
  a los demás.
- **La RFEG se consulta sin ninguna transacción abierta**: puede tardar hasta
  10 s, y mientras tanto no tiene sentido tener una conexión ocupada.
- **Todo queda apuntado**, también lo que falla de forma inesperada.
"""

import hashlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.ports.handicap_update_email_service_interface import (
    IHandicapUpdateEmailService,
)
from src.modules.competition.application.services.aviso_del_organizador import (
    poner_al_dia_el_del_organizador,
)
from src.modules.competition.application.services.avisos_al_organizador import (
    AvisosAlOrganizador,
)
from src.modules.competition.application.services.avisos_de_actividad import (
    AvisosDeActividad,
    FabricaDeActividad,
)
from src.modules.competition.application.services.fijado_de_la_rfeg import (
    FabricaDeHerramientas,
    Herramientas,
    corregir_el_fijado,
)
from src.modules.competition.application.services.handicaps_al_cerrar import HandicapsAlCerrar
from src.modules.competition.application.services.pendientes_de_actualizar import (
    PendientesDeActualizar,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.refresco_rfeg import RefrescoRfeg
from src.modules.competition.application.services.sin_actualizar_de_la_competicion import (
    SinActualizarDeLaCompeticion,
)
from src.modules.competition.application.services.ventana_de_la_competicion import ventana_de
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    OrigenActualizacion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    MAX_INTENTOS,
    CorreoDeActualizacion,
    ResultadoRefresco,
)
from src.modules.competition.domain.services.sin_actualizar_con_la_rfeg import SinActualizar
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

# Segundos entre un jugador y el siguiente, y entre un intento fallido y el siguiente
PAUSA_ENTRE_JUGADORES = 2.0
PAUSA_ENTRE_INTENTOS = 5.0


def _huella(lista: list[UserId]) -> str:
    """La huella de una lista del organizador: la misma con los mismos jugadores."""
    return hashlib.sha256(",".join(sorted(str(u.value) for u in lista)).encode()).hexdigest()


class RefrescarHandicapsUseCase:
    """Una pasada de una actualización: pregunta por quien falte y la termina."""

    def __init__(
        self,
        herramientas: FabricaDeHerramientas,
        handicap_service: HandicapService | None,
        avisos: IHandicapUpdateEmailService | None,
        reloj: Callable[[], datetime],
        esperar: Callable[[float], Awaitable[None]],
        actividad: FabricaDeActividad | None = None,
    ):
        """
        Args:
            herramientas: Da herramientas nuevas (competición y usuarios sobre
                una misma sesión) cada vez que se le piden
            handicap_service: La RFEG
            avisos: El correo al organizador si queda alguien sin actualizar
            reloj: La hora actual, con huso
            esperar: Las pausas
            actividad: Monta Actividad para los avisos al terminar (15 nov 2026),
                solo cuando hay que avisar (T1)
        """
        self._herramientas = herramientas
        self._handicap_service = handicap_service
        self._avisos = AvisosAlOrganizador(avisos)
        self._reloj = reloj
        self._esperar = esperar
        self._actividad = actividad

    async def execute(self, update_id: uuid.UUID) -> int:
        """
        Returns:
            A cuántos jugadores se ha preguntado en esta pasada
        """
        pendientes = await self._pendientes(update_id)
        preguntados = 0
        # A quién no encontró la RFEG en esta pasada: solo a ellos se les avisa,
        # y así otra pasada de una incompleta no se lo repite
        no_encontrados: set[UserId] = set()
        for user_id in pendientes:
            if preguntados:
                await self._esperar(PAUSA_ENTRE_JUGADORES)
            if not await self._sigue(update_id):
                return preguntados
            if await self._refrescar(update_id, user_id) is ResultadoRefresco.NO_ENCONTRADO:
                no_encontrados.add(user_id)
            preguntados += 1
        await self._terminar(update_id, no_encontrados)
        return preguntados

    async def _pendientes(self, update_id: uuid.UUID) -> list[UserId]:
        """A quién preguntar: los inscritos sin personalizado que no tienen respuesta."""
        async with self._herramientas() as h, h.competiciones as uow:
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            if actualizacion is None or not actualizacion.sigue():
                return []
            return await PendientesDeActualizar.de(uow, actualizacion)

    async def _sigue(self, update_id: uuid.UUID) -> bool:
        """Si sigue en curso y con la ventana abierta; si se cerró, se corta (#251)."""
        async with self._herramientas() as h, h.competiciones as uow:
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            if actualizacion is None or not actualizacion.sigue():
                return False
            competicion = await uow.competitions.find_by_id_for_update(actualizacion.competition_id)
            return await self._dentro_de_la_ventana(uow, h.zonas, competicion, actualizacion)

    async def _dentro_de_la_ventana(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        competicion: Competition | None,
        actualizacion: ActualizacionDeHandicaps,
    ) -> bool:
        """
        «Se corta 10 s por jugador antes de empezar» vale también para la que está
        en marcha (Agustín, 7 oct 2026): si la ventana se cerró, se corta, y lo
        pendiente se queda como estaba.
        """
        if competicion is None:
            return False
        if (await ventana_de(uow, zonas, competicion, self._reloj())).abierta:
            return True
        actualizacion.cortar(self._reloj())
        await uow.handicap_updates.update(actualizacion)
        return False

    async def _refrescar(self, update_id: uuid.UUID, user_id: UserId) -> ResultadoRefresco | None:
        """
        Hasta 3 intentos con un jugador, con pausa entre uno y otro, mientras siga.

        Returns:
            Lo último que se apuntó, o None si se cortó antes de preguntar
        """
        resultado = None
        for intento in range(MAX_INTENTOS):
            if intento:
                await self._esperar(PAUSA_ENTRE_INTENTOS)
                if not await self._sigue(update_id):
                    return resultado
            resultado = await self._una_vez(update_id, user_id)
            if resultado is not ResultadoRefresco.FALLIDO:
                return resultado
        return resultado

    async def _una_vez(self, update_id: uuid.UUID, user_id: UserId) -> ResultadoRefresco:
        """
        Pregunta por un jugador y lo apunta.

        En tres pasos para no tener la transacción abierta mientras la RFEG
        contesta: leer al jugador, preguntar, y apuntar (que es cuando se
        guarda también su hándicap nuevo y se corrige el fijado).

        Lo que su perfil apuntó como actualizado mientras tanto no se pisa
        (R2): se mira antes de preguntar, y al apuntar no lo pisa el propio
        repositorio, en la misma sentencia.
        """
        try:
            async with self._herramientas() as h:
                async with h.competiciones as uow:
                    if await self._ya_actualizado(uow, update_id, user_id):
                        return ResultadoRefresco.ACTUALIZADO
                    jugador = await h.usuarios.find_by_id(user_id)
                if jugador is None:
                    # Ya no existe: no hay a quién preguntar, ni ahora ni luego
                    resultado = ResultadoRefresco.NO_ENCONTRADO
                else:
                    resultado = await RefrescoRfeg(self._handicap_service, h.usuarios).consultar(
                        jugador
                    )
                async with h.competiciones as uow:
                    # Con la competición bloqueada, también si no cambia nada: el
                    # vigilante la bloquea para dar una por cortada (#510)
                    await self._bloquear(uow, update_id)
                    if (
                        resultado is ResultadoRefresco.ACTUALIZADO
                        and jugador is not None
                        and jugador.handicap is not None
                    ):
                        nuevo = Decimal(str(jugador.handicap.value))
                        await self._corregir(uow, h, update_id, user_id, nuevo)
                    await uow.handicap_updates.apuntar(update_id, user_id, resultado, self._reloj())
            return resultado
        except Exception:
            logger.exception("No se pudo refrescar el hándicap de %s", user_id)
            await self._apuntar_el_fallo(update_id, user_id)
            return ResultadoRefresco.FALLIDO

    @staticmethod
    async def _ya_actualizado(
        uow: CompetitionUnitOfWorkInterface, update_id: uuid.UUID, user_id: UserId
    ) -> bool:
        """Si ya está apuntado como actualizado (lo apuntó su perfil, R2)."""
        intento = await uow.handicap_updates.resultado_de(update_id, user_id)
        return intento is not None and intento.resultado is ResultadoRefresco.ACTUALIZADO

    async def _corregir(
        self,
        uow: CompetitionUnitOfWorkInterface,
        h: Herramientas,
        update_id: uuid.UUID,
        user_id: UserId,
        nuevo: Decimal,
    ) -> None:
        """
        En un stroke play que siga cerrado, el hándicap fijado pasa a ser el nuevo.

        Con la competición bloqueada, y solo si la actualización sigue y la
        ventana está abierta: si a la vez alguien la inicia, una de las dos espera
        a la otra, y si la RFEG tardó hasta pasado el cierre, no se cambia nada.
        """
        actualizacion = await uow.handicap_updates.find_by_id(update_id)
        if actualizacion is None:
            return
        competicion = await uow.competitions.find_by_id_for_update(actualizacion.competition_id)
        actualizacion = await uow.handicap_updates.find_by_id(update_id)
        if (
            competicion is not None
            and actualizacion is not None
            and actualizacion.sigue()
            and await self._dentro_de_la_ventana(uow, h.zonas, competicion, actualizacion)
        ):
            await corregir_el_fijado(uow, h, competicion, user_id, nuevo, self._reloj())

    @staticmethod
    async def _bloquear(uow: CompetitionUnitOfWorkInterface, update_id: uuid.UUID) -> None:
        """La competición de la actualización, bloqueada hasta el final de la transacción."""
        actualizacion = await uow.handicap_updates.find_by_id(update_id)
        if actualizacion is not None:
            await uow.competitions.find_by_id_for_update(actualizacion.competition_id)

    async def _apuntar_el_fallo(self, update_id: uuid.UUID, user_id: UserId) -> None:
        """Un fallo inesperado también se apunta, con herramientas limpias."""
        try:
            async with self._herramientas() as h, h.competiciones as uow:
                await self._bloquear(uow, update_id)
                await uow.handicap_updates.apuntar(
                    update_id, user_id, ResultadoRefresco.FALLIDO, self._reloj()
                )
        except Exception:
            logger.exception("Tampoco se pudo apuntar el fallo de %s", user_id)

    async def _terminar(self, update_id: uuid.UUID, no_encontrados: set[UserId]) -> None:
        """
        Completa, o incompleta si alguien se quedó sin actualizar; y entonces se
        avisa, ya fuera de la transacción (H1-H6, 15 nov 2026): al organizador,
        si alguien se quedó sin actualizar con la RFEG; y a cada español al que
        la RFEG no encontró en esta pasada.

        Los correos no se repiten (D2, 16 nov 2026): al jugador, uno por
        competición; al organizador, otra vez solo si cambió la lista. Se
        apuntan en la misma transacción, antes de enviarlos: un correo que
        falle no se reintenta, pero dos pasadas a la vez no lo mandan dos veces.
        """
        async with self._herramientas() as h, h.competiciones as uow:
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            if actualizacion is None:
                return
            competicion = await uow.competitions.find_by_id_for_update(actualizacion.competition_id)
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            if competicion is None or actualizacion is None or not actualizacion.sigue():
                return
            sin_actualizar = await PendientesDeActualizar.de(uow, actualizacion)
            actualizacion.terminar(len(sin_actualizar), self._reloj())
            await uow.handicap_updates.update(actualizacion)
            # El del cierre cambia hándicaps segundos después del reparto: las
            # categorías iguales se rehacen con los corregidos (10 oct 2026)
            if actualizacion.origen is OrigenActualizacion.CIERRE:
                await HandicapsAlCerrar(uow, h.usuarios).repartir_de_nuevo(competicion)
            hecho = await SinActualizarDeLaCompeticion.de(
                uow, h.usuarios, competicion, actualizacion
            )
            # Los no encontrados en esta pasada: otra pasada no se lo repite
            avisar = [u for u in hecho.no_encontrados if u in no_encontrados]
            nombres = await self._lista_si_cambio(uow, h, competicion, hecho.para_el_organizador)
            organizador = (
                await self._avisos.quien(h.usuarios, competicion) if nombres is not None else None
            )
            a_escribir = await self._sin_correo_todavia(uow, competicion, avisar)
            jugadores = await h.usuarios.find_by_ids(a_escribir) if a_escribir else []
        if nombres is not None:
            await self._avisos.pendientes(organizador, competicion, nombres)
        for jugador in jugadores:
            await self._avisos.no_encontrado(jugador, competicion)
        await self._en_actividad(competicion, avisar, hecho)

    async def _lista_si_cambio(
        self,
        uow: CompetitionUnitOfWorkInterface,
        h: Herramientas,
        competicion: Competition,
        lista: list[UserId],
    ) -> list[str] | None:
        """
        Los nombres para el correo del organizador, o None si no hay que
        mandarlo: lista vacía, o la misma que recibió la última vez (D2). Una
        lista vacía olvida la enviada: si vuelve, se manda otra vez.
        """
        correos, organizador = uow.handicap_updates, competicion.creator_id
        tipo = CorreoDeActualizacion.LISTA_DEL_ORGANIZADOR
        if not lista:
            await correos.olvidar_correo(competicion.id, organizador, tipo)
            return None
        huella = _huella(lista)
        if await correos.correo_enviado(competicion.id, organizador, tipo) == huella:
            return None
        await correos.apuntar_correo(competicion.id, organizador, tipo, huella, self._reloj())
        nombres = await PlayerNames.de_la_competicion(lista, competicion.id, h.usuarios, uow)
        return list(nombres.values())

    async def _sin_correo_todavia(
        self, uow: CompetitionUnitOfWorkInterface, competicion: Competition, avisar: list[UserId]
    ) -> list[UserId]:
        """A quién de los no encontrados no se le escribió nunca en esta competición (D2)."""
        tipo = CorreoDeActualizacion.NO_ENCONTRADO
        nuevos = []
        for user_id in avisar:
            if await uow.handicap_updates.correo_enviado(competicion.id, user_id, tipo) is None:
                await uow.handicap_updates.apuntar_correo(
                    competicion.id, user_id, tipo, "", self._reloj()
                )
                nuevos.append(user_id)
        return nuevos

    async def _en_actividad(
        self,
        competicion: Competition,
        avisar: list[UserId],
        hecho: SinActualizar,
    ) -> None:
        """
        Los avisos de Actividad, que se renuevan en cada pasada; y los que ya no
        son ciertos se retiran (D3). Actividad se monta aquí, con la pasada ya
        terminada: si montarla o cerrarla falla, la pasada no se entera (T1). El
        del organizador se lee y se publica con la competición bloqueada (R4).
        """
        if self._actividad is None:
            return
        try:
            async with self._actividad() as publicador:
                actividad = AvisosDeActividad(publicador)
                await actividad.handicap_not_found(competicion, avisar)
                await actividad.handicap_not_found_withdrawn(competicion, hecho.sin_aviso)
        except Exception:
            logger.warning(
                "Could not publish the RFEG notices of %s", competicion.id.value, exc_info=True
            )
        await poner_al_dia_el_del_organizador(self._herramientas, self._actividad, competicion.id)
