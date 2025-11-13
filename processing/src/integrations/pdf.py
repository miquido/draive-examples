from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

from draive import (
    DataModel,
    File,
    FileAccess,
    Meta,
    ResourceContent,
    asynchronous,
    ctx,
)
from PIL.Image import Image
from pypdfium2 import PdfDocument, PdfPage

from integrations.images import normalized_image

__all__ = [
    "PDFPage",
    "read_pdf",
]


class PDFPage(DataModel):
    page: int
    text: str
    render: ResourceContent | None
    meta: Meta


async def read_pdf(
    source: Path | str | bytes,
    /,
    *,
    name: str | None = None,
    render: bool,
) -> AsyncGenerator[PDFPage]:
    data: bytes
    if isinstance(source, bytes):
        data = source

    else:
        async with ctx.disposables(FileAccess.open(source)):
            data = await File.read()

    document: PdfDocument = await _read_pdf(data)
    document_name: str = name or uuid4().hex
    total_pages: int = len(document)

    for page_number in range(total_pages):
        yield await _read_pdf_page(
            document[page_number],
            document_name=document_name,
            page_number=page_number,
            dpi=300,
            render=render,
        )


@asynchronous
def _read_pdf(
    pdf: bytes,
    /,
) -> PdfDocument:
    return PdfDocument(pdf)


@asynchronous
def _read_pdf_page(
    page: PdfPage,
    /,
    *,
    document_name: str,
    page_number: int,
    dpi: int,
    render: bool,
) -> PDFPage:
    # Extract page text, normalize whitespace and trim

    page_text: str = " ".join((page.get_textpage().get_text_bounded()).split())  # pyright: ignore[reportUnknownMemberType]

    if render:
        page_image: Image = page.render(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            # Calculate scale factor based on DPI (72 is the default PDF DPI)
            scale=dpi / 72.0,  # pyright: ignore[reportArgumentType]
            rotation=0,
        ).to_pil()

        return PDFPage(
            page=page_number,
            render=ResourceContent.of(
                normalized_image(page_image),  # pyright: ignore[reportUnknownArgumentType]
                mime_type="image/png",
                meta={
                    "page_number": int(page_number),
                },
            ),
            text=page_text,
            meta=Meta.of({"document": document_name}),
        )

    else:
        return PDFPage(
            page=page_number,
            render=None,
            text=page_text,
            meta=Meta.of({"document": document_name}),
        )
