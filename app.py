import os
import sys
import traceback
from io import StringIO
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel


app = FastAPI(title="Code Interpreter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    code: str


class CodeResponse(BaseModel):
    error: List[int]
    result: str


class ErrorAnalysis(BaseModel):
    error_lines: List[int]


def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code)
        return {
            "success": True,
            "output": sys.stdout.getvalue(),
        }
    except Exception:
        return {
            "success": False,
            "output": traceback.format_exc(),
        }
    finally:
        sys.stdout = old_stdout


def analyze_error_with_ai(code: str, error_traceback: str) -> List[int]:
    token = os.environ.get("AIPIPE_TOKEN")
    if not token:
        raise RuntimeError("AIPIPE_TOKEN environment variable is not configured.")

    client = OpenAI(
        api_key=token,
        base_url="https://aipipe.org/openai/v1",
    )

    prompt = f"""Analyze this Python code and traceback.
Identify the exact source-code line number(s) where the error occurred.
Return only JSON with the field error_lines.

CODE:
{code}

TRACEBACK:
{error_traceback}
"""

    response = client.chat.completions.create(
        model="openai/gpt-4.1-nano",
        messages=[
            {
                "role": "system",
                "content": "Identify the exact Python source-code line numbers responsible for the error.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "error_analysis",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "error_lines": {
                            "type": "array",
                            "items": {"type": "integer"},
                        }
                    },
                    "required": ["error_lines"],
                    "additionalProperties": False,
                },
            },
        },
    )

    return ErrorAnalysis.model_validate_json(
        response.choices[0].message.content
    ).error_lines


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):
    execution = execute_python_code(request.code)

    if execution["success"]:
        return {
            "error": [],
            "result": execution["output"],
        }

    error_lines = analyze_error_with_ai(
        request.code,
        execution["output"],
    )

    return {
        "error": error_lines,
        "result": execution["output"],
    }
