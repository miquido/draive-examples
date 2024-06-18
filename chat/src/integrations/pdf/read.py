import re as regex
from asyncio import get_running_loop
from io import BytesIO, StringIO

from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

__all__ = [
    "read_pdf",
]


async def read_pdf(
    source: BytesIO | str,
) -> str:
    return await get_running_loop().run_in_executor(
        None,
        _read_pdf,
        source,
    )


def _read_pdf(
    source: BytesIO | str,
) -> str:
    output: StringIO = StringIO()
    resource_manager = PDFResourceManager()
    interpreter = PDFPageInterpreter(
        resource_manager,
        TextConverter(
            resource_manager,
            output,
            laparams=LAParams(),
        ),
    )

    parser: PDFParser
    match source:
        case str(path):
            with open(path, "rb") as file:
                parser = PDFParser(BytesIO(file.read()))

        case data:
            parser = PDFParser(data)

    for page in PDFPage.create_pages(PDFDocument(parser)):
        interpreter.process_page(page)

    return regex.sub(  # replace multiple repetitive whitespaces
        r"(?:(?![\n\r])\s)+",
        " ",
        regex.sub(  # replace multiple repetitive newlines
            r"\n\s+",
            "\n",
            output.getvalue(),
        ),
    ).strip()
