import argparse
from asyncio import run
from collections.abc import AsyncGenerator, Sequence

from draive import (
    Argument,
    Meta,
    MultimodalContent,
    Stage,
    StageState,
    State,
    Toolbox,
    ctx,
    setup_logging,
    stage,
    tool,
)
from draive.gemini import Gemini, GeminiGenerationConfig

from integrations.pdf import PDFPage, read_pdf

setup_logging("processing")


async def processing(
    subject: str,
    pdf_path: str,
) -> None:
    async with ctx.scope(
        "processing",
        GeminiGenerationConfig(model="gemini-2.5-flash"),
        disposables=(Gemini(),),
    ):
        pdf_pages: AsyncGenerator[PDFPage] = read_pdf(
            pdf_path,
            render=True,
        )
        result: MultimodalContent = await Stage.sequence(
            preprocessor(pdf_pages),
            analysis(subject=subject),
        ).execute()

        print("----------------------[ANSWER]----------------------")
        print(result.to_str())
        print("----------------------------------------------------")


class ProcessedPage(State):
    page: int
    content: str
    meta: Meta


class ProcessedDocument(State):
    pages: Sequence[ProcessedPage]


def preprocessor(
    pdf_pages: AsyncGenerator[PDFPage],
    /,
) -> Stage:
    @stage
    async def processing(state: StageState) -> StageState:
        processed: list[ProcessedPage] = []

        @tool(description="Access the contents of the previous page")
        async def previous_page() -> str:
            if not processed:
                return "N/A"

            return processed[-1].content

        async def process_page(page: PDFPage) -> ProcessedPage:
            content: MultimodalContent = (
                await Stage.completion(
                    MultimodalContent.of(
                        f'<DOCUMENT page="{page.page}">\n<TEXT>\n',
                        page.text,
                        "\n</TEXT>\n<RENDER>\n",
                        page.render if page.render is not None else "N/A",
                        "\n</RENDER>\n</DOCUMENT>",
                    ),
                    instruction=PAGE_PROCESS_INSTRUCTION,
                    tools=(previous_page,),
                    output="text",
                )
                .with_retry(limit=2)
                .execute()
            )

            return ProcessedPage(
                page=page.page,
                content=f'<DOCUMENT page="{page.page}">\n{content.to_str()}\n</DOCUMENT>',
                meta=page.meta,
            )

        async for page in pdf_pages:
            # do not run concurrently - we want to allow previous page access
            processed.append(await process_page(page))

        return state.updated(ProcessedDocument(pages=processed))

    return processing


PAGE_PROCESS_INSTRUCTION: str = """\
Carefully examine the DOCUMENT, then provide a detailed and complete text representation\
 of the DOCUMENT contents without any additional comments.
Use any appropriate formatting to make the result as readable as possible.
Include all possible details that can be read and represented by text including image descriptions\
 unreadable parts or missing elements and page continuations.
Never make up or assume any information that is not explicitly stated within the DOCUMENT.

You may access the previous page content using a dedicated tool when need to contextualize\
 content split between two pages.

Make sure to include all visible elements in the result.
"""


@tool(
    description="Consult given subject with independent consultant without access to your knowledge"
)
async def consult(
    subject: str = Argument(description="Subject to be consulted"),
    context: str = Argument(description="Additional context required to understand the subject"),
) -> MultimodalContent:
    with ctx.updated(
        GeminiGenerationConfig(
            model="gemini-2.5-pro",
            thinking_budget=1024,
        )
    ):
        return (
            await Stage.completion(
                f"<SUBJECT>\n{subject}\n</SUBJECT>\n<CONTEXT>\n{context}\n</CONTEXT>",
                instruction=CONSULT_PROCESS_INSTRUCTION,
            )
            .with_retry(limit=1)
            .execute()
        ).without_meta()


CONSULT_PROCESS_INSTRUCTION: str = """\
You are a domain expert in all fields. Consult given SUBJECT providing exhaustive yet concise\
 insight and explanation including expertise and professional feedback.
"""


class Analysis(State):
    pass


def analysis(subject: str) -> Stage:
    analysis_finished: bool = False

    @stage
    async def analyze_step_stage(
        state: StageState,
    ) -> StageState:
        @tool(
            description="Complete analysis when found all required details",
        )
        async def finish_analysis() -> str:
            nonlocal analysis_finished
            analysis_finished = True
            return "Analysis has been completed, provide your final findings"

        @tool(description="Access the contents of the document page")
        async def read_page(
            page: int = Argument(description="Page number, indexed from 0"),
        ) -> str:
            document: ProcessedDocument = state.get(
                ProcessedDocument,
                required=True,
            )

            if page >= len(document.pages):
                return f"Invalid page number - there are {len(document.pages)} pages available"

            return document.pages[page].content

        return (
            await Stage.completion(
                "Continue the analysis",
                instruction=ANALYSIS_PROCESS_INSTRUCTION.format(subject=subject),
                tools=Toolbox.of(
                    read_page,
                    consult,
                    finish_analysis,
                    suggest=True,
                ),
            )
            .with_retry(limit=3)
            .with_volatile_tools_context()(state=state)
        )

    async def analysis_stage_condition(
        state: StageState,
        iteration: int,
    ) -> bool:
        return not analysis_finished

    return Stage.loop(
        analyze_step_stage,
        condition=analysis_stage_condition,
    ).with_volatile_tools_context()


ANALYSIS_PROCESS_INSTRUCTION: str = """\
You are a professional analyst.

Analyze available document providing exhaustive yet concise\
 insight and explanation including expertise and professional feedback.\
 You can access the document content using a dedicated `read_page` tool.

Focus on the requested SUBJECT to be verified and confirmed within the document contents.

<SUBJECT>
{subject}
</SUBJECT>

Provide your finding in a clear concise way. Include your reasoning and evidence.

Continue processing and analysing until fully complete.
When your analysis is fully complete use the `finish_analysis` tool with your findings.
"""


parser = argparse.ArgumentParser(description="Process PDF document with analysis")
parser.add_argument(
    "--subject",
    type=str,
    required=True,
    help="Subject for analysis",
)
parser.add_argument(
    "--pdf-path",
    type=str,
    required=True,
    help="Path to the PDF file to process",
)
args = parser.parse_args()

run(processing(args.subject, args.pdf_path))
