import re
import unicodedata
from pathlib import PurePath

FILENAME_MAX_LENGTH = 255
FALLBACK_FILENAME = "documento"
UNSAFE_CHARACTERS = re.compile(r"[\x00-\x1f\x7f<>:\"/\\|?*]")


def clean_filename(filename: str | None) -> str:
    """Nombre que se muestra al usuario: sin rutas ni caracteres raros. Nunca se usa como key en S3."""
    name = PurePath((filename or "").replace("\\", "/")).name
    name = UNSAFE_CHARACTERS.sub("", unicodedata.normalize("NFC", name)).strip()
    return name[:FILENAME_MAX_LENGTH] or FALLBACK_FILENAME
