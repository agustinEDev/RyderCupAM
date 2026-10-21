"""Caso de Uso: Ver el perfil de un jugador."""

from src.modules.social.application.dto.profile_dto import (
    FriendshipStateDTO,
    PlayerProfileResponseDTO,
)
from src.modules.social.application.exceptions import ProfileNotVisibleError
from src.modules.social.application.games_together import head_to_head_of, page_of
from src.modules.social.application.ports.shared_games_interface import SharedGamesInterface
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Estados que ve el cliente. Los dos "pendiente" se separan porque no llevan al
# mismo boton: uno espera respuesta del otro, el otro pide respuesta tuya.
NO_RELATIONSHIP = "NONE"
PENDING_SENT = "PENDING_SENT"
PENDING_RECEIVED = "PENDING_RECEIVED"


class GetPlayerProfileUseCase:
    """
    El perfil de un jugador, con dos niveles segun quien mire.

    **La ficha minima es publica entre usuarios registrados**: nombre, apellidos
    y foto. Es lo que permite buscar a alguien por su nombre, reconocerlo y
    mandarle una solicitud, y no dice nada que la propia busqueda no diga ya.

    **Lo de detras es solo para amigos**: estadisticas, actividad, cara a cara
    y partidas juntos (BE-3). El handicap, desde el 22 oct 2026, lo ve
    cualquiera con sesion, salvo que haya un bloqueo entre los dos. El correo,
    ni los amigos: solo se lo ve uno mismo (BE #531).
    Quien no es amigo los recibe en None, no recortados ni a cero: un cero se
    leeria como "juega fatal" en vez de "esto no se puede ver".

    Antes esto era un 404 para cualquiera que no fuera amigo, con la idea de no
    confirmar que la cuenta existia. Esa proteccion dejo de tener sentido cuando
    se decidio que los jugadores se buscan por nombre: la cuenta ya es
    descubrible por diseño, y seguir fingiendo que no existe solo impediria
    mandarle una solicitud. El 404 se reserva ahora para lo que de verdad no
    esta: cuentas inexistentes o dadas de baja.

    La relacion se consulta en cada peticion y no se guarda en cache, que es lo
    que hace que deshacer una amistad retire el acceso al instante.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        stats_use_case: GetPlayerStatsUseCase,
        shared_games: SharedGamesInterface | None = None,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._stats = stats_use_case
        self._shared_games = shared_games

    async def execute(self, viewer_id_raw: str, target_id_raw: str) -> PlayerProfileResponseDTO:
        viewer_id = UserId(viewer_id_raw)
        target_id = UserId(target_id_raw)
        propio = viewer_id == target_id

        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(target_id)
            if user is None or not user.is_active:
                raise ProfileNotVisibleError("Profile not found")

            ficha = {
                "id": str(user.id.value),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "display_name": user.display_name,
                "avatar_source": user.avatar_source.value,
                "avatar_preset_id": user.avatar_preset_id,
                "has_avatar_upload": user.active_avatar_upload_id is not None,
            }
            handicap = float(user.handicap.value) if user.handicap else None
            email = user.email.value

        relacion, amigos = await self._relacion_y_amigos(viewer_id, target_id, propio)
        amigo = relacion.status == FriendshipStatus.ACCEPTED.value
        puede_ver_todo = propio or amigo
        # Con un bloqueo de por medio, de un lado o del otro, solo nombre y foto
        bloqueado = relacion.status == FriendshipStatus.BLOCKED.value

        # Fuera de la unidad de trabajo: las estadisticas abren las suyas, y
        # anidarlas sobre la misma sesion la cerraria antes de tiempo
        stats = await self._stats.execute(target_id) if puede_ver_todo else None

        # Lo jugado juntos, solo entre amigos: de uno mismo no hay cara a cara
        cara_a_cara = None
        partidas = None
        if amigo and not propio and self._shared_games is not None:
            juntos = await self._shared_games.between(viewer_id, target_id)
            cara_a_cara = head_to_head_of(juntos)
            partidas = page_of(juntos, cursor=None)

        return PlayerProfileResponseDTO(
            **ficha,
            # Bloqueado, solo nombre y foto: el campo no admite null sin romper
            # el contrato, asi que va a 0 y el cliente no lo pinta
            friends_count=0 if bloqueado else amigos,
            friendship=relacion,
            is_friend=amigo,
            # Ni a los amigos: el correo es dato suyo
            email=email if propio else None,
            # El handicap ya es publico entre usuarios con sesion (BE-3, 22 oct
            # 2026): ayuda a decidir con quien jugar. Salvo bloqueo
            handicap=None if bloqueado else handicap,
            stats=stats,
            head_to_head=cara_a_cara,
            games_together=partidas,
        )

    async def _relacion_y_amigos(
        self, viewer_id: UserId, target_id: UserId, propio: bool
    ) -> tuple[FriendshipStateDTO, int]:
        """
        En que punto esta la relacion y cuantos amigos tiene el otro.

        Las dos cosas salen del mismo repositorio, asi que se resuelven en una
        sola apertura en lugar de dos.

        **El contador va en la ficha publica**, junto al nombre y la foto. Es un
        numero: dice si alguien esta empezando o lleva tiempo, que es justo lo
        que ayuda a decidir si mandarle una solicitud, y no dice quienes son sus
        amigos ni nada de ellos.
        """
        async with self._social_uow:
            amigos = await self._social_uow.friendships.count_friends(target_id)

            if propio:
                return FriendshipStateDTO(status=NO_RELATIONSHIP), amigos

            friendship = await self._social_uow.friendships.find_by_pair(viewer_id, target_id)

        if friendship is None:
            return FriendshipStateDTO(status=NO_RELATIONSHIP), amigos

        return (
            FriendshipStateDTO(
                status=self._estado(friendship, viewer_id),
                friendship_id=str(friendship.id.value),
            ),
            amigos,
        )

    @staticmethod
    def _estado(friendship: Friendship, viewer_id: UserId) -> str:
        """
        El estado desde el punto de vista de quien mira.

        Una solicitud pendiente no significa lo mismo para los dos lados, asi
        que se traduce a dos estados distintos en lugar de devolver `PENDING` y
        dejar que el cliente deduzca quien la mando.
        """
        if friendship.status != FriendshipStatus.PENDING:
            return friendship.status.value

        return PENDING_SENT if friendship.requester_id == viewer_id else PENDING_RECEIVED
