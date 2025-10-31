from draive.postgres import PostgresConnection


async def migration(connection: PostgresConnection) -> None:
    # configurations #
    await connection.execute(
        """
CREATE TABLE configurations (
    identifier TEXT NOT NULL,
    content JSONB NOT NULL,
    created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (identifier, created)
);
"""
    )

    await connection.execute(
        """
INSERT INTO configurations (identifier, content)
VALUES ('OpenAIResponsesConfig', '{"model":"gpt-5"}'::jsonb);
        """
    )

    # templates #
    await connection.execute(
        """
CREATE TABLE templates (
    identifier TEXT NOT NULL,
    description TEXT DEFAULT NULL,
    content TEXT NOT NULL,
    variables JSONB NOT NULL DEFAULT '{}'::jsonb,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (identifier, created)
);
    """
    )

    await connection.execute(
        """
INSERT INTO templates (identifier, description, content)
VALUES (
    'example',
    'Example scenario prompt',
    'You are a helpful assistant answering as concisely as possible.'
);
        """
    )

    # memories #
    await connection.execute(
        """
CREATE TABLE memories (
    identifier TEXT NOT NULL,
    created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (identifier)
);
    """
    )

    await connection.execute(
        """
CREATE TABLE memories_variables (
    identifier TEXT NOT NULL REFERENCES memories (identifier) ON DELETE CASCADE,
    variables JSONB NOT NULL DEFAULT '{}'::jsonb,
    created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
        """
    )

    await connection.execute(
        """
CREATE TABLE memories_elements (
    identifier TEXT NOT NULL REFERENCES memories (identifier) ON DELETE CASCADE,
    content JSONB NOT NULL,
    created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
    """
    )
