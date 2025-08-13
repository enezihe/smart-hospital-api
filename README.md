# Smart Hospital API

A minimal Flask API is provided. It is intended for demo and course assignment use.

## Features

- A health check endpoint is exposed at `/health`.
- A sample endpoint is exposed at `/patients` that returns a static list.
- CORS is enabled.
- Environment variables can be loaded through `.env`.

## Requirements

- Python 3.10+  
- pip

The dependencies are listed in `requirements.txt`.

## Installation

1. The repository is cloned or downloaded.
2. A virtual environment is created (optional but recommended).
3. Dependencies are installed from `requirements.txt`.

Example:

```bash
# (optional) create and activate virtual env
python3 -m venv .venv
source .venv/bin/activate   # on macOS/Linux
# .venv\Scripts\activate    # on Windows PowerShell

# install deps
pip install -r requirements.txt

