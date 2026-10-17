"""Building blocks for a user turn, so agents never import the SDK themselves."""

import base64

from anthropic.types import Base64PDFSourceParam, DocumentBlockParam, TextBlockParam

from app.core.llm.types import UserContent


def text_block(text: str) -> UserContent:
    return TextBlockParam(type="text", text=text)


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
