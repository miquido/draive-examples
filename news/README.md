# News

Example project for running agents workflow focused on creating a news page. Uses chat interface for interaction and rendering.

## Setup

To setup the project please use `make venv` command. Python 3.12+ is required, you can specify path to it by using additional argument `make venv PYTHON_ALIAS=path/to/python`. Make sure to activate virtual environment by using `. ./.venv/bin/activate`. Preparing environment prepares a copy of a .env file where you can fill your configuration including api keys or urls for required services.

## Run

When the environment is ready you can use `make run` command to run the chat. Make sure to provide all environment variables before running.
