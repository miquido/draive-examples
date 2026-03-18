from draive.postgres import PostgresConnection


async def migration(connection: PostgresConnection) -> None:
    # MEMORIES
    await connection.execute(
        """\
        CREATE TABLE conversation_memory (
            thread_id TEXT NOT NULL,
            turn TEXT NOT NULL,
            identifier UUID NOT NULL,
            payload JSONB NOT NULL,
            created TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (thread_id, identifier),
            UNIQUE (thread_id, identifier)
        );
        """
    )

    await connection.execute(
        """\
        CREATE INDEX IF NOT EXISTS conversation_memory_idx
            ON conversation_memory (thread_id, created DESC, identifier DESC);
        """
    )

    # CONFIGURATIONS
    await connection.execute(
        """\
        CREATE TABLE configurations (
            identifier TEXT NOT NULL,
            name TEXT NOT NULL,
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
                name,
                content
            )

        VALUES (
            'conversation-response',
            'OpenAIResponsesConfig',
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
