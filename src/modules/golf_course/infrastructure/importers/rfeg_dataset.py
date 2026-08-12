"""
Lectura del volcado de campos federados que viaja con el repositorio.

El fichero va comprimido (0,7 MB frente a 11 MB en crudo) para que quepa en el
repositorio junto al código que lo interpreta: así cualquier entorno puede
reimportar con un comando, y se ve en git qué datos se cargaron y cuándo.
"""

import gzip
import json
from pathlib import Path
from typing import Any

# El fichero vive fuera del paquete, en data/, porque es un dato y no código.
DEFAULT_DATASET_PATH = Path(__file__).resolve().parents[5] / "data" / "rfeg_dataset.json.gz"

EXPECTED_SOURCE_FRAGMENT = "rfegolf"


class RfegDatasetError(ValueError):
    """El volcado no tiene la forma que espera el importador."""


def load_dataset(path: Path | None = None) -> dict[str, Any]:
    """
    Lee el volcado y comprueba que tiene la forma esperada.

    Se admite tanto comprimido como en crudo: al preparar una importación nueva
    es cómodo apuntar al JSON recién extraído sin comprimirlo antes.

    Args:
        path: Ruta al volcado. Por defecto, el que viaja en el repositorio

    Returns:
        El volcado completo

    Raises:
        RfegDatasetError: Si el fichero no existe o no tiene la forma esperada
    """
    dataset_path = path or DEFAULT_DATASET_PATH
    if not dataset_path.exists():
        raise RfegDatasetError(f"Dataset not found at {dataset_path}")

    try:
        if dataset_path.suffix == ".gz":
            with gzip.open(dataset_path, "rt", encoding="utf-8") as handle:
                dataset = json.load(handle)
        else:
            dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RfegDatasetError(f"Could not read the dataset at {dataset_path}: {error}") from error

    _validate(dataset, dataset_path)
    return dataset


def _validate(dataset: Any, dataset_path: Path) -> None:
    """
    Comprueba lo mínimo antes de recorrer cientos de clubes.

    Vale la pena parar aquí: un fichero equivocado se detecta en el acto en vez
    de a mitad de la importación, con parte del trabajo hecho.
    """
    if not isinstance(dataset, dict):
        raise RfegDatasetError(f"The dataset at {dataset_path} is not an object")

    clubs = dataset.get("clubs")
    if not isinstance(clubs, list) or not clubs:
        raise RfegDatasetError("The dataset has no clubs")

    source = str(dataset.get("source") or dataset.get("source_listing_url") or "")
    if EXPECTED_SOURCE_FRAGMENT not in source.lower():
        raise RfegDatasetError(
            f"The dataset does not look like an RFEG extraction (source: {source!r})"
        )

    for club in clubs:
        if not isinstance(club, dict) or "rfeg_id" not in club or "name" not in club:
            raise RfegDatasetError("A club in the dataset has no id or no name")


def clubs_with_courses(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Devuelve solo los clubes que publican algún recorrido."""
    return [club for club in dataset["clubs"] if club.get("courses")]
