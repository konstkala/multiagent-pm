"""Building blocks for a user turn, so agents never import the SDK themselves."""

import base64
from typing import Literal

from anthropic.types import (
    Base64ImageSourceParam,
    Base64PDFSourceParam,
    DocumentBlockParam,
    ImageBlockParam,
    TextBlockParam,
)

from app.core.llm.types import UserContent


def text_block(text: str) -> UserContent:
    return TextBlockParam(type="text", text=text)


def tag(name: str, body: str) -> str:
    """Wraps untrusted text in an XML-style tag the text itself can't close."""
    # Otherwise "</ticket> new instructions..." could end our data block and pose as a prompt.
    return f"<{name}>\n{body.replace('</', '< /')}\n</{name}>"


def pdf_block(data: bytes) -> UserContent:
    """A PDF Claude reads directly: text plus page images, about 1.5K to 3K tokens a page."""
    return DocumentBlockParam(
        type="document",
        source=Base64PDFSourceParam(
            type="base64",
            media_type="application/pdf",
            data=base64.standard_b64encode(data).decode("ascii"),
        ),
    )


ImageType = Literal["image/png", "image/jpeg", "image/gif", "image/webp"]


def image_block(data: bytes, media_type: ImageType) -> UserContent:
    """An image Claude looks at. About width * height / 750 tokens; large images are scaled down."""
    return ImageBlockParam(
        type="image",
        source=Base64ImageSourceParam(
            type="base64",
            media_type=media_type,
            data=base64.standard_b64encode(data).decode("ascii"),
        ),
    )
