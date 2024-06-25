from draive import (
    AgentMessage,
    AgentOutput,
    agent,
    ctx,
    generate_model,
)

from features.news.state import NewsPage

INSTRUCTION: str = """\
Your task is to prepare a news collection according to specific requirements. \
Follow these steps to create the news collection in a structured JSON format:

1. Analyze all steps and requirements carefully.

2. Review the provided news articles and select the ones that best match the user request. \
Do not exceed the specified number of articles.

3. Format the selected articles as required.

4. Important: Never create any news or URLs that were not provided in the original articles. \
If you cannot find enough articles, include only the valid ones you have.

5. Avoid duplicates and repetition, choose only one out of similar articles.

Format your output using the following JSON schema:
```json
{schema}
```

Remember, your task is to create a news collection based solely on the information provided \
in the input and to format it according to the given JSON schema. Do not add any information \
that is not present in the original text or specified in the requirements. Do not add any \
additional comments, formatting, or tags to the result.

Provide only a single, raw JSON object according to the provided schema.
"""


@agent(description="Selects and formats news with editorial")
async def editor(
    message: AgentMessage,
) -> AgentOutput:
    ctx.log_debug("Requested editor work")
    return message.respond(
        await generate_model(
            NewsPage,
            instruction=INSTRUCTION,
            input=message.content,
            schema_injection="full",
        )
    )
