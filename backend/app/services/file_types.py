"""Decide what an uploaded file really is, from its name AND its first bytes.

The browser's Content-Type is never trusted: an attacker can label an HTML page "image/png".
SVG and HTML are refused outright because browsers run scripts inside them.
"""

import re
from pathlib import PurePosixPath

from app.core.errors import InvalidRequestError

_ZIP = b"PK\x03\x04"

# extension -> (content type served back, signature check on the first bytes, or None for text)
_ALLOWED: dict[str, tuple[str, bytes | None]] = {
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".gif": ("image/gif", b"GIF8"),
    ".webp": ("image/webp", b"RIFF"),
    ".pdf": ("application/pdf", b"%PDF-"),
    ".zip": ("application/zip", _ZIP),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", _ZIP),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _ZIP),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", _ZIP),
    ".txt": ("text/plain; charset=utf-8", None),
    ".log": ("text/plain; charset=utf-8", None),
    ".md": ("text/markdown; charset=utf-8", None),
    ".csv": ("text/csv; charset=utf-8", None),
    ".json": ("application/json", None),
}

IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
ALLOWED_EXTENSIONS = tuple(sorted(_ALLOWED))

_UNSAFE_CHARS = re.compile(r"[^\w .()-]+")


def clean_filename(raw: str | None) -> str:
    """The name shown and offered on download: no paths, no control characters."""
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    name = _UNSAFE_CHARS.sub("_", name).strip(" .")
    return name[:255] or "file"


def detect_content_type(filename: str, data: bytes) -> str:
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in _ALLOWED:
        raise InvalidRequestError(
            f"This file type isn't allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    content_type, signature = _ALLOWED[extension]
    if signature is None:
        if b"\x00" in data:
            raise InvalidRequestError("This doesn't look like a text file")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidRequestError("Text files must be UTF-8") from exc
    elif not data.startswith(signature) or (extension == ".webp" and data[8:12] != b"WEBP"):
        raise InvalidRequestError("The file's content doesn't match its extension")
    return content_type
