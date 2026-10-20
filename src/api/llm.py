"""Thin Groq client wrapper. No business logic — tailor.py owns prompting."""
import os

from groq import Groq

MODEL = "openai/gpt-oss-120b"


def complete(system_prompt: str, user_prompt: str) -> str:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content
