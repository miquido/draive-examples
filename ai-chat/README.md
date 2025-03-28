# ChainlitChat

## Setup

To setup the project please use `make venv` command. Python 3.12+ is required, you can specify path to it by using additional argument `make venv PYTHON_ALIAS=path/to/python`. Make sure to activate virtual environment by using `. ./.venv/bin/activate`. Preparing environment prepares a copy of a .env file where you can fill your configuration including api keys or urls for required services.

## Environment variables

### General

`PYTHONOPTIMIZE=0` - python interpreter optimization level, ensure running `PYTHONOPTIMIZE=2` in production otherwise application will run in debug mode.

`DEBUG_LOGGING=1` - enable or disable additional debug logging.

### Chat service

`CHAT_PORT=8888` - port used to run chat server.

### OpenAI

`OPENAI_API_KEY=` - API key to access OpenAI services.

`OPENAI_MODEL=gpt-4o-mini` - default OpenAI model.

### Postgres

`POSTGRES_DATABASE=postgres` - name of used postgres database.

`POSTGRES_HOST=localhost` - hostname of postgres service.

`POSTGRES_PORT=5432` - port of postgres service.

`POSTGRES_USER=postgres` - user to access postgres database.

`POSTGRES_PASSWORD=postgres` - password to access postgres database.

`POSTGRES_SSLMODE=disable` - SSL mode, see more at https://www.postgresql.org/docs/current/libpq-ssl.html#LIBPQ-SSL-SSLMODE-STATEMENTS.
