"""OpenRouter VLM client for vision-language model queries.

Handles image encoding, retries, fallback models, and JSON parsing.
"""

from __future__ import annotations

import base64
import json
import re
import time

import httpx
from loguru import logger


class OpenRouterVLM:
    """Client for OpenRouter VLM API with retry and fallback support."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        primary_model: str = "qwen/qwen3.5-35b-a3b",
        fallback_model: str = "qwen/qwen2.5-vl-7b-instruct",
        temperature: float = 0.2,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.temperature = temperature
        self.max_retries = max_retries
        self.client = httpx.Client(timeout=120.0)

    def query_with_image(
        self,
        image_b64: str,
        prompt: str,
        model: str | None = None,
        expect_json: bool = True,
    ) -> dict | str:
        """Send an image + text prompt to the VLM.

        Args:
            image_b64: Base64-encoded JPEG image.
            prompt: Text prompt.
            model: Override model (default: primary_model).
            expect_json: If True, parse response as JSON.

        Returns:
            Parsed JSON dict or raw text string.
        """
        model = model or self.primary_model
        return self._query(image_b64, prompt, model, expect_json)

    def _query(
        self,
        image_b64: str,
        prompt: str,
        model: str,
        expect_json: bool,
    ) -> dict | str:
        """Execute VLM query with retry logic."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": 4096,
                    },
                )
                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"]

                if expect_json:
                    return self._parse_json(text)
                return text.strip()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    wait = min(2 ** (attempt + 1), 30)
                    logger.warning(f"Rate limited, waiting {wait}s")
                    time.sleep(wait)
                elif attempt < self.max_retries - 1:
                    # Try fallback model on error
                    if model != self.fallback_model:
                        logger.warning(f"Falling back to {self.fallback_model}")
                        model = self.fallback_model
                    time.sleep(1)
                else:
                    raise
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                else:
                    raise

        raise last_error

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from VLM response, handling markdown code blocks."""
        # Try direct parse
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse JSON from VLM response: {text[:200]}")
        return {"raw_text": text, "parse_error": True}

    def close(self):
        self.client.close()


def encode_frame_to_b64(frame) -> str:
    """Encode an OpenCV frame (numpy array) to base64 JPEG."""
    import cv2

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")
