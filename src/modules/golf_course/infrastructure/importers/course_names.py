"""
Nombres presentables a partir de los que publica la RFEG.

La federación publica los nombres en mayúsculas, a menudo sin tildes, y con el
club delante solo a veces. Aquí se convierten en algo que se pueda leer en una
lista del móvil sin que parezca un grito.
"""

import json
import re
import unicodedata
from pathlib import Path

_ACCENTS_FILE = Path(__file__).with_name("name_accents.json")

_VOWELS = frozenset("AEIOUÁÉÍÓÚÜ")

# Palabras de tres letras o menos que no distinguen a un club: aparecen en
# demasiados nombres como para servir de pista ('SAN', 'LOS', 'DEL').
_MIN_DISTINCTIVE_LENGTH = 4

# Un nombre repetido por la fuente tiene exactamente dos mitades.
_REPEATED_NAME_PARTS = 2

_WORD_PATTERN = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ&\.]+")


def _load_name_tables() -> tuple[dict[str, str], frozenset[str], frozenset[str], frozenset[str]]:
    """Lee las tablas revisadas de tildes, siglas y partículas."""
    data = json.loads(_ACCENTS_FILE.read_text(encoding="utf-8"))
    return (
        data["accents"],
        frozenset(data["stopwords"]),
        frozenset(data["acronyms"]),
        frozenset(data["lowercase_particles"]),
    )


ACCENTS, STOPWORDS, ACRONYMS, LOWERCASE_PARTICLES = _load_name_tables()


def strip_accents(text: str) -> str:
    """Quita las tildes de un texto, para comparar sin depender de ellas."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def normalize_for_comparison(text: str) -> str:
    """
    Deja un nombre en su forma comparable: sin tildes, en mayúsculas y sin
    signos.

    Sirve para decidir si dos nombres son el mismo, no para mostrarlos.
    """
    cleaned = re.sub(r"[^A-Z0-9 ]+", " ", strip_accents(text).upper())
    return " ".join(cleaned.split())


def _looks_like_acronym(word: str) -> bool:
    """
    True si la palabra es una sigla y hay que dejarla en mayúsculas.

    Se reconocen solas las que llevan punto o &, las de una sola letra (que en
    estos nombres designan el recorrido: 'Campo A') y las que no tienen ninguna
    vocal. El resto se distinguen de una palabra corriente únicamente por
    conocimiento del dominio, así que salen de una lista revisada: sin ella,
    'GOLF', 'SANTA' o 'REAL' también parecerían siglas por venir en mayúsculas.
    """
    letters = [char for char in word if char.isalpha()]
    if not letters:
        return True
    if "." in word or "&" in word:
        return True
    if len(letters) == 1:
        return True
    upper = strip_accents(word).upper()
    if upper in ACRONYMS:
        return True
    return all(char.isupper() for char in letters) and not (set(upper) & _VOWELS)


def _restore_accents(word: str) -> str:
    """Devuelve la palabra con su tilde si la tabla revisada la conoce."""
    key = strip_accents(word).upper()
    if key in STOPWORDS:
        return word
    return ACCENTS.get(key, word)


def prettify(name: str) -> str:
    """
    Convierte un nombre de la RFEG en uno presentable.

    Restaura las tildes que la fuente pierde, pasa a capitalización normal y
    respeta las siglas. Las palabras que ya vienen con mayúsculas y minúsculas
    mezcladas se dejan como están: la fuente ya las escribió bien.

    Args:
        name: Nombre tal como lo publica la federación

    Returns:
        El nombre listo para mostrar
    """

    is_first = True

    def convert(match: re.Match[str]) -> str:
        nonlocal is_first
        opens_the_name = is_first
        is_first = False

        word = match.group(0)
        accented = _restore_accents(word)
        if _looks_like_acronym(accented):
            return accented
        if not accented.isupper():
            # Ya viene con formato propio ('Aguilón Golf'), no se toca más allá
            # de la tilde.
            return accented
        upper = strip_accents(accented).upper()
        if upper in LOWERCASE_PARTICLES and not opens_the_name:
            return accented.lower()
        return accented.capitalize()

    return _WORD_PATTERN.sub(convert, name).strip()


def build_course_name(club_name: str, course_name: str) -> str:
    """
    Compone el nombre con el que se guarda un recorrido.

    La RFEG suele publicar el recorrido ya identificado ('ALDEAMAYOR - P&P'),
    así que anteponer siempre el club daría nombres largos y repetidos. Solo se
    antepone cuando el nombre del recorrido no comparte ninguna palabra
    distintiva con el del club, que son 18 de los 802 recorridos: casos como
    'GOLF MUNICIPAL DE GIJÓN' con el recorrido 'LA LLOREA - Tragamón', donde
    buscar por el club no encontraría nada.

    Args:
        club_name: Nombre del club
        course_name: Nombre del recorrido

    Returns:
        Nombre final del campo
    """
    generic = {"CLUB", "GOLF", "REAL", "CAMPO", "RESORT", "HOTEL", "DE", "DEL", "LA", "EL"}
    club_words = {
        word
        for word in normalize_for_comparison(club_name).split()
        if len(word) >= _MIN_DISTINCTIVE_LENGTH and word not in generic
    }
    course_words = set(normalize_for_comparison(course_name).split())

    pretty_course = prettify(course_name)
    if club_words & course_words:
        return pretty_course

    return f"{prettify(club_name)} - {pretty_course}"


def collapse_repetition(name: str) -> str:
    """
    Deja en uno los nombres que la fuente publica dos veces.

    La RFEG antepone el club al recorrido, y cuando el recorrido se llama igual
    que el club sale 'Aguilón Golf - Aguilón Golf'. Se compara sin tildes ni
    signos porque las dos mitades no siempre se escriben igual.

    Ojo: no se aplica sin mirar al resto de recorridos del club. Usar
    build_club_course_names() para eso.
    """
    parts = [part.strip() for part in name.split(" - ")]
    if len(parts) == _REPEATED_NAME_PARTS and normalize_for_comparison(
        parts[0]
    ) == normalize_for_comparison(parts[1]):
        return parts[1]
    return name


def prettify_place(name: str | None) -> str | None:
    """
    Deja presentable una localidad o una provincia.

    Además de las tildes y la capitalización, deshace el artículo pospuesto del
    nomenclátor oficial: la RFEG publica 'CALA DE MIJAS, LA', que es como se
    ordena en un listado pero no como se lee.

    Args:
        name: Localidad o provincia tal como viene de la fuente

    Returns:
        El nombre listo para mostrar, o None si no había nada
    """
    if not name or not name.strip():
        return None

    cleaned = name.strip()
    if "," in cleaned:
        body, _, article = cleaned.rpartition(",")
        if normalize_for_comparison(article) in {"LA", "EL", "LOS", "LAS"}:
            cleaned = f"{article.strip()} {body.strip()}"

    return prettify(cleaned)


def build_club_course_names(club_name: str, course_names: list[str]) -> list[str]:
    """
    Compone el nombre de todos los recorridos de un club a la vez.

    Hace falta ver el club entero porque el colapso de nombres repetidos puede
    volver indistinguibles dos recorridos que sí son distintos: hay tres clubes
    donde la federación publica uno como 'LA ENVIA - La Envía' y otro como 'LA
    ENVIA', y son campos diferentes (par 70 y par 58). En esos casos se
    conserva el nombre largo, que es feo pero no miente.

    Args:
        club_name: Nombre del club
        course_names: Nombres de sus recorridos, tal como los publica la fuente

    Returns:
        Un nombre por recorrido, en el mismo orden
    """
    full = [build_course_name(club_name, course_name) for course_name in course_names]
    collapsed = [collapse_repetition(name) for name in full]

    seen: dict[str, int] = {}
    for name in collapsed:
        key = normalize_for_comparison(name)
        seen[key] = seen.get(key, 0) + 1

    return [
        collapsed[index] if seen[normalize_for_comparison(collapsed[index])] == 1 else full[index]
        for index in range(len(full))
    ]
