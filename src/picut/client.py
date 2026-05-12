"""Vertex AI client factory using Application Default Credentials."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


def make_client() -> genai.Client:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    if not project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not set. "
            "Copy .env.example to .env and fill in your project ID."
        )
    return genai.Client(vertexai=True, project=project, location=location)
