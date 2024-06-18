# Chat

Example chat project for running local AI powered chats.

## Setup

To setup the project please use `make venv` command. Python 3.12+ is required, you can specify path tu it by using additional argument `make venv PYTHON_ALIAS=path/to/python`. Make sure to activate virtual environment by using `. ./.venv/bin/activate`. Preparing environment prepares a copy of a .env file where you can fill your configuration including api keys or urls for required services.

## Run

When the environment is ready you can use `make run` command to run the chat. Make sure to provide all environment variables before running.
