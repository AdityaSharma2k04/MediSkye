
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from dotenv import load_dotenv, find_dotenv
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def fetch_models(api_key: str) -> list[dict[str, Any]]:
    """Fetch every page returned by the Gemini models endpoint."""
    models: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        params = {"key": api_key}
        if page_token:
            params["pageToken"] = page_token

        request = Request(f"{API_URL}?{urlencode(params)}")
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)

        models.extend(payload.get("models", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            return models


def model_short_name(model: dict[str, Any]) -> str:
    return model.get("name", "").removeprefix("models/")


def print_table(models: list[dict[str, Any]]) -> None:
    rows = []
    for model in sorted(models, key=model_short_name):
        methods = ", ".join(model.get("supportedGenerationMethods", [])) or "—"
        rows.append((model_short_name(model), model.get("displayName", "—"), methods))

    headers = ("MODEL", "DISPLAY NAME", "SUPPORTED METHODS")
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def line(values: tuple[str, str, str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    print(line(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(line(row))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List Gemini models accessible to GEMINI_API_KEY."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output the complete API response data as JSON."
    )
    args = parser.parse_args()

    load_dotenv(find_dotenv())

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "GOOGLE_API_KEY or GEMINI_API_KEY is not set. Please set it in your .env file.",
            file=sys.stderr,
        )
        return 2

    try:
        models = fetch_models(api_key)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"Gemini API returned HTTP {error.code}: {detail}", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Could not reach the Gemini API: {error.reason}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(models, indent=2))
    elif models:
        print(f"Found {len(models)} model(s) available to this API key:\n")
        print_table(models)
    else:
        print("The API returned no models for this key.")
    return 0


if __name__ == "__main__":
    sys.exit(main())