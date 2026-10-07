import os
import sys
import json
import re
import traceback
from io import StringIO
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI


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
            "output": sys.stdout.getvalue()
        }

    except Exception:
        return {
            "success": False,
            "output": traceback.format_exc()
        }

    finally:
        sys.stdout = old_stdout


def extract_traceback_lines(error_traceback: str) -> List[int]:
    """
    Fallback: extract Python source line numbers from traceback.
    """
    lines = re.findall(r'File ".*?", line (\d+)', error_traceback)

    if not lines:
        return []

    return [int(x) for x in lines]


def analyze_error_with_ai(code: str, error_traceback: str) -> List[int]:

    token = os.environ.get("AIPIPE_TOKEN")

    if not token:
        raise RuntimeError("AIPIPE_TOKEN is not configured.")

    client = OpenAI(
        api_key=token,
        base_url="https://aipipe.org/openai/v1"
    )

    prompt = f"""
Identify the exact source-code line number where the Python error occurred.

Return ONLY valid JSON in this exact format:

{{"error_lines": [3]}}

CODE:
{code}

TRACEBACK:
{error_traceback}
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-4.1-nano",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Python debugging assistant. "
                        "Identify the exact source-code line responsible "
                        "for the error."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_object"
            }
        )

        content = response.choices[0].message.content

        data = json.loads(content)

        result = ErrorAnalysis.model_validate(data)

        if result.error_lines:
            return result.error_lines

    except Exception:
        pass

    # Fallback ensures traceback line numbers are returned
    # if the AI service has a temporary/API compatibility issue.
    return extract_traceback_lines(error_traceback)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):

    execution = execute_python_code(request.code)

    # No AI call for successful code
    if execution["success"]:
        return {
            "error": [],
            "result": execution["output"]
        }

    # AI is called only when execution fails
    error_lines = analyze_error_with_ai(
        request.code,
        execution["output"]
    )

    return {
        "error": error_lines,
        "result": execution["output"]
    }
