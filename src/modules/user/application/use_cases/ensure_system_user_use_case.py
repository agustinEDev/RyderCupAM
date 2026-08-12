"""
EnsureSystemUserUseCase - La cuenta técnica que figura como autora de los datos
importados.
"""

import secrets
import string

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId

# Longitud holgada: nadie va a teclear esta contraseña nunca, y cuanto más
# larga, menos margen deja si algún día la cuenta se reactivara por error.
_GENERATED_PASSWORD_LENGTH = 48


def _generate_unusable_password() -> str:
    """
    Genera una contraseña aleatoria que cumple la política y que nadie conoce.

    La cuenta de sistema queda desactivada, así que no puede iniciar sesión;
    esto solo evita dejar una contraseña previsible por si alguna vez se
    reactivara. Se garantiza un carácter de cada clase porque la política los
    exige y el azar podría no incluirlos.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?"),
    ]
    rest = [secrets.choice(alphabet) for _ in range(_GENERATED_PASSWORD_LENGTH - len(required))]
    password = required + rest
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


class EnsureSystemUserUseCase:
    """
    Use Case: obtener la cuenta de sistema que crea los datos importados,
    creándola si aún no existe.

    El agregado GolfCourse exige un creador, y atar cientos de campos federados
    a una cuenta personal la haría imborrable y mezclaría lo importado con lo
    que esa persona dio de alta a mano. La cuenta de sistema resuelve las dos
    cosas y deja el rastro donde se ve.

    La cuenta nace **desactivada**, lo que impide iniciar sesión con ella y,
    desde el arreglo de la búsqueda de jugadores, la mantiene fuera de "buscar
    amigos". No es admin: no ejecuta nada, solo figura como autora.

    Es idempotente: si la cuenta ya existe se devuelve su id, de modo que
    reimportar no crea una segunda.
    """

    def __init__(self, uow: UserUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        email_str: str,
        first_name: str = "Importador",
        last_name: str = "Automatico",
    ) -> UserId:
        """
        Devuelve el id de la cuenta de sistema, creándola si hace falta.

        Args:
            email_str: Correo que identifica la cuenta. No recibe correo real
            first_name: Nombre visible de la cuenta
            last_name: Apellido visible de la cuenta

        Returns:
            UserId de la cuenta de sistema
        """
        async with self._uow:
            existing = await self._uow.users.find_by_email(Email(email_str))
            if existing is not None:
                return self._require_id(existing)

            system_user = User.create(
                first_name=first_name,
                last_name=last_name,
                email_str=email_str,
                plain_password=_generate_unusable_password(),
            )
            # Se desactiva a sí misma: no hay ningún admin detrás de esta alta,
            # y la auditoría de la desactivación tiene que apuntar a algo.
            system_user.deactivate(deactivated_by_user_id=str(system_user.id.value))

            await self._uow.users.save(system_user)

            return self._require_id(system_user)

    @staticmethod
    def _require_id(user: User) -> UserId:
        """
        Devuelve el id del usuario, que a estas alturas siempre existe.

        `User.id` es opcional en el tipo porque el constructor admite None al
        hidratar, pero tanto un usuario recién creado como uno recuperado de la
        base de datos lo tienen. Fallar aquí sería un fallo de programación, no
        un caso que el importador deba manejar.
        """
        if user.id is None:
            raise ValueError("The system user has no id, which should never happen")
        return user.id
