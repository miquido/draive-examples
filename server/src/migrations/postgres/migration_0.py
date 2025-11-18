from draive.postgres import PostgresConnection


async def migration(connection: PostgresConnection) -> None:
    # MEMORIES
    await connection.execute(
        """\
        CREATE TABLE memories (
            identifier UUID NOT NULL,
            created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (identifier)
        );
        """
    )
    await connection.execute(
        """\
        CREATE TABLE memories_variables (
            memories UUID NOT NULL REFERENCES memories (identifier) ON DELETE CASCADE,
            variables JSONB NOT NULL DEFAULT '{}'::jsonb,
            created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            memories_variables_idx

        ON
            memories_variables (memories, created DESC);
        """
    )
    await connection.execute(
        """\
        CREATE TABLE memories_elements (
            identifier UUID NOT NULL DEFAULT gen_random_uuid(),
            memories UUID NOT NULL REFERENCES memories (identifier) ON DELETE CASCADE,
            content JSONB NOT NULL,
            created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (identifier)
        );
        """
    )
    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            memories_elements_idx

        ON
            memories_elements (
                memories,
                created DESC
            );
        """
    )

    # CONFIGURATIONS
    await connection.execute(
        """\
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
        CREATE INDEX IF NOT EXISTS
            configurations_identifier_created_idx

        ON
            configurations (identifier, created DESC);
        """
    )
    await connection.execute(
        """
        INSERT INTO
            configurations (
                identifier,
                content
            )

        VALUES (
            'conversation-response',
            '{"model": "gpt-5-mini"}'::jsonb
        );
        """
    )
    # TEMPLATES
    await connection.execute(
        """\
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
        CREATE INDEX IF NOT EXISTS
            templates_idx

        ON
            templates (identifier, created DESC);
        """
    )
    await connection.execute(
        """
        INSERT INTO
            templates (
                identifier,
                description,
                content
            )

        VALUES (
            'conversation-response-instructions',
            'Default conversation instructions template content',
            'You are a helpful assistant.'
        );
        """
    )
