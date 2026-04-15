import argparse
from asyncio import run
from collections.abc import AsyncGenerator, MutableSequence, Sequence
from typing import Annotated

from draive import (
    Description,
    Meta,
    ModelOutput,
    MultimodalContent,
    State,
    Step,
    StepState,
    Toolbox,
    ctx,
    setup_logging,
    step,
    tool,
)
from draive.gemini import Gemini, GeminiConfig
from draive.steps.types import StepStream

from integrations.pdf import PDFPage, read_pdf

setup_logging("processing")


async def processing(
    subject: str,
    pdf_path: str,
) -> None:
    async with ctx.scope(
        "processing",
        GeminiConfig(model="gemini-3-flash-preview"),
        disposables=(Gemini(),),
    ):
        result: MultimodalContent = await Step.sequence(
            preprocessor(
                read_pdf(
                    pdf_path,
                    render=True,
                )
            ),
            analysis(subject=subject),
        ).run()

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
) -> Step:
    @step
    async def processing(state: StepState) -> StepState:
        processed: MutableSequence[ProcessedPage] = []

        @tool(description="Access the contents of the previous page")
        async def previous_page() -> str:
            if not processed:
                return "N/A"

            return processed[-1].content

        async def process_page(page: PDFPage) -> ProcessedPage:
            content: MultimodalContent = await (
                Step.looping_completion(
                    instruction=PAGE_PROCESS_INSTRUCTION,
                    tools=Toolbox.of(
                        previous_page,
                    ),
                    output="text",
                    input=MultimodalContent.of(
                        f'<DOCUMENT page="{page.page}">\n<TEXT>\n',
                        page.text,
                        "\n</TEXT>\n<RENDER>\n",
                        page.render if page.render is not None else "N/A",
                        "\n</RENDER>\n</DOCUMENT>",
                    ),
                )
                .with_retry(limit=2)
                .run()
            )

            return ProcessedPage(
                page=page.page,
                content=f'<DOCUMENT page="{page.page}">\n{content.to_str()}\n</DOCUMENT>',
                meta=page.meta,
            )

        async for page in pdf_pages:
            # do not run concurrently - we want to allow previous page access
            processed.append(await process_page(page))

        return state.updating_artifacts(ProcessedDocument(pages=processed))

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
    subject: Annotated[str, Description("Subject to be consulted")],
    context: Annotated[str, Description("Additional context required to understand the subject")],
) -> MultimodalContent:
    with ctx.updating(
        GeminiConfig(
            model="gemini-3-flash-preview",
            thinking_budget=1024,
        )
    ):
        return (
            await Step.generating_completion(
                instruction=CONSULT_PROCESS_INSTRUCTION,
                input=f"<SUBJECT>\n{subject}\n</SUBJECT>\n<CONTEXT>\n{context}\n</CONTEXT>",
            )
            .with_retry(limit=1)
            .run()
        )


CONSULT_PROCESS_INSTRUCTION: str = """\
You are a domain expert in all fields. Consult given SUBJECT providing exhaustive yet concise\
 insight and explanation including expertise and professional feedback.
"""


def analysis(subject: str) -> Step:
    analysis_finished: bool = False

    @Step
    async def emit_output(
        state: StepState,
    ) -> StepStream:
        if isinstance(state.context[-1], ModelOutput):
            for part in state.context[-1].content.parts:
                yield part

        yield state

    @Step
    async def analyze_step_stage(
        state: StepState,
    ) -> StepStream:
        @tool(description="Mark analysis completed when found all required details")
        async def finish_analysis() -> str:
            nonlocal analysis_finished
            analysis_finished = True
            return "Analysis has been marked as completed, provide your full final findings"

        @tool(description="Access the contents of the document page")
        async def read_page(
            page: Annotated[int, Description("Page number, indexed from 0")],
        ) -> str:
            document: ProcessedDocument = state.get(
                ProcessedDocument,
                required=True,
            )

            if page >= len(document.pages):
                return f"Invalid page number - there are {len(document.pages)} pages available"

            return document.pages[page].content

        yield (
            await Step.looping_completion(
                instruction=ANALYSIS_PROCESS_INSTRUCTION.format(subject=subject),
                tools=Toolbox.of(
                    read_page,
                    consult,
                    finish_analysis,
                    suggesting=True,
                ),
                input="Continue the analysis",
            )
            .with_retry(limit=3)
            .process(state)
        )

    async def analysis_stage_condition(
        state: StepState,
        iteration: int,
    ) -> bool:
        return not analysis_finished

    return Step.sequence(
        Step.loop(
            analyze_step_stage,
            condition=analysis_stage_condition,
        ),
        emit_output,
    )


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
When your analysis is fully complete mark it as complete using the `finish_analysis` tool,\
 then present your findings.
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
