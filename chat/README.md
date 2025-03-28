# ChainlitChat

## Setup

To setup the project please use `make venv` command. Make sure to activate virtual environment by using `. ./.venv/bin/activate`. Preparing environment prepares a copy of a .env file where you can fill your configuration including api keys or urls for required services.

## Environment variables

### General

`PYTHONOPTIMIZE=0` - python interpreter optimization level, ensure running `PYTHONOPTIMIZE=2` in production otherwise application will run in debug mode.

`DEBUG_LOGGING=1` - enable or disable additional debug logging.

### Chat service

`CHAT_PORT=8888` - port used to run chat server.

`CHAT_PASSWORD=password` - password for default user.

### OpenAI

`OPENAI_API_KEY=` - API key to access OpenAI services.

### Postgres

`POSTGRES_DATABASE=postgres` - name of used postgres database.

`POSTGRES_HOST=localhost` - hostname of postgres service.

`POSTGRES_PORT=5432` - port of postgres service.

`POSTGRES_USER=postgres` - user to access postgres database.

`POSTGRES_PASSWORD=postgres` - password to access postgres database.

`POSTGRES_SSLMODE=disable` - SSL mode, see more at https://www.postgresql.org/docs/current/libpq-ssl.html#LIBPQ-SSL-SSLMODE-STATEMENTS.
