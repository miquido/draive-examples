from integrations.postgres import PostgresConnection


async def execute_migration() -> None:
    await PostgresConnection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            users (
                id UUID NOT NULL DEFAULT gen_random_uuid(),
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                identifier TEXT NOT NULL,
                metadata JSONB,
                PRIMARY KEY (id),
                UNIQUE (identifier)
            )
        ;
        """
    )

    await PostgresConnection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            threads (
                id UUID NOT NULL DEFAULT gen_random_uuid(),
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                user_id UUID,
                name TEXT,
                tags TEXT[],
                metadata JSONB,
                PRIMARY KEY (id),
                CONSTRAINT fk_thread_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ;
        """  # noqa: E501
    )

    await PostgresConnection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            elements (
                id UUID NOT NULL DEFAULT gen_random_uuid(),
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                thread_id UUID NOT NULL,
                message_id UUID NOT NULL,
                type TEXT,
                mime TEXT,
                name TEXT,
                url TEXT,
                content BYTEA,
                display TEXT,
                size TEXT,
                PRIMARY KEY (id),
                CONSTRAINT fk_element_thread FOREIGN KEY (thread_id) REFERENCES threads (id) ON DELETE CASCADE
            )
        ;
        """  # noqa: E501
    )

    await PostgresConnection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            steps (
                id UUID NOT NULL DEFAULT gen_random_uuid(),
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                thread_id UUID NOT NULL,
                parent_id UUID,
                type TEXT,
                name TEXT,
                streaming BOOLEAN,
                wait_for_answer BOOLEAN,
                is_error BOOLEAN,
                tags TEXT[],
                input TEXT,
                output TEXT,
                generation JSONB,
                show_input TEXT,
                indent INT,
                metadata JSONB,
                start_time TIMESTAMP WITH TIME ZONE,
                end_time TIMESTAMP WITH TIME ZONE,
                PRIMARY KEY (id),
                CONSTRAINT fk_step_thread FOREIGN KEY (thread_id) REFERENCES threads (id) ON DELETE CASCADE
            )
        ;
        """  # noqa: E501
    )
