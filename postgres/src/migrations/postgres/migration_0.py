from integrations.postgres import PostgresConnection


async def execute_migration() -> None:
    # Conversation Memory #
    await PostgresConnection.execute(
        """\
CREATE TABLE IF NOT EXISTS
    conversation_messages (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        session_id UUID NOT NULL,
        role VARCHAR(64) NOT NULL,
        content TEXT NOT NULL,
        meta TEXT NOT NULL,
        PRIMARY KEY(id)
    )
;\
        """
    )
    await PostgresConnection.execute(
        """\
CREATE INDEX IF NOT EXISTS
    conversation_messages_session_index

ON
    conversation_messages (session_id)
;\
        """
    )

    # Instructions #
    await PostgresConnection.execute(
        """\
CREATE TABLE IF NOT EXISTS
    instructions (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        name VARCHAR(256) NOT NULL,
        description TEXT,
        content TEXT NOT NULL,
        arguments TEXT NOT NULL,
        meta TEXT NOT NULL,
        PRIMARY KEY(id)
    )
;\
        """
    )
    await PostgresConnection.execute(
        """\
CREATE INDEX IF NOT EXISTS
    instructions_name_index

ON
    instructions (name)
;\
        """
    )

    # arguments: Sequence[InstructionDeclarationArgument]

    # Configuration #
    await PostgresConnection.execute(
        """\
CREATE TABLE IF NOT EXISTS
    configurations (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        identifier VARCHAR(256) NOT NULL,
        created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        content TEXT NOT NULL,
        PRIMARY KEY(id)
    )
;\
        """
    )
    await PostgresConnection.execute(
        """\
CREATE INDEX IF NOT EXISTS
    configurations_identifier_index

ON
    configurations (identifier)
;\
        """
    )
