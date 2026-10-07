# Code Interpreter API

FastAPI endpoint for the IITM assignment.

## Local run

Set AIPIPE_TOKEN, then:

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

Endpoint:
POST /code-interpreter

## Render

Build command:
pip install -r requirements.txt

Start command:
uvicorn app:app --host 0.0.0.0 --port $PORT

Environment variable:
AIPIPE_TOKEN=<your private AIPipe token>

IMPORTANT: This assignment endpoint executes submitted Python with exec().
Do not expose it publicly outside the assignment environment without a real
sandbox, resource limits, filesystem/network isolation, and authentication.
