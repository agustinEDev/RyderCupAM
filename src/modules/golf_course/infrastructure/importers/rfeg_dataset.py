"""
Lectura del volcado de campos federados.

El volcado se guarda fuera de git y se señala con la variable RFEG_DATASET_PATH;
sin ella, se busca en data/, que git ignora.
"""

import gzip
import json
import os
from pathlib import Path
from typing import Any

# Sitio por defecto: data/ en la raíz del repo (git y Docker ignoran el volcado).
DEFAULT_DATASET_PATH = Path(__file__).resolve().parents[5] / "data" / "rfeg_dataset.json.gz"

DATASET_PATH_ENV = "RFEG_DATASET_PATH"


def dataset_path() -> Path:
    """La ruta del volcado: RFEG_DATASET_PATH si está definida, si no la de siempre."""
    configured = os.environ.get(DATASET_PATH_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_DATASET_PATH


EXPECTED_SOURCE_FRAGMENT = "rfegolf"


class RfegDatasetError(ValueError):
    """El volcado no tiene la forma que espera el importador."""


def load_dataset(path: Path | None = None) -> dict[str, Any]:
    """
    Lee el volcado y comprueba que tiene la forma esperada.

    Se admite tanto comprimido como en crudo: al preparar una importación nueva
    es cómodo apuntar al JSON recién extraído sin comprimirlo antes.

    Args:
        path: Ruta al volcado. Por defecto, la de RFEG_DATASET_PATH o data/

    Returns:
        El volcado completo

    Raises:
        RfegDatasetError: Si el fichero no existe o no tiene la forma esperada
    """
    resolved = path or dataset_path()
    if not resolved.exists():
        raise RfegDatasetError(f"Dataset not found at {resolved}")

    try:
        if resolved.suffix == ".gz":
            with gzip.open(resolved, "rt", encoding="utf-8") as handle:
                dataset = json.load(handle)
        else:
            dataset = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RfegDatasetError(f"Could not read the dataset at {resolved}: {error}") from error

    _validate(dataset, resolved)
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
