"""
Custom 9Router / OpenAI-Compatible LLM Judge for DeepEval
Configured for 9Router endpoint at http://localhost:20128/v1 with model 'deepeval'.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional
from deepeval.models.base_model import DeepEvalBaseLLM
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel


class CustomRAGJudgeLLM(DeepEvalBaseLLM):
    """Custom LLM judge wrapper for DeepEval connecting to 9Router or OpenAI."""

    def __init__(
        self,
        model: str = "deepeval",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        *args,
        **kwargs,
    ):
        self.model_name = os.getenv("DEEPEVAL_LLM_MODEL") or model
        self.api_key = (
            api_key
            or os.getenv("DEEPEVAL_LLM_API_KEY")
            or os.getenv("AI_PROXY_API_KEY")
            or "sk-b958727376b1a4a8-d7aagg-4c5fcc2f"
        )
        self.base_url = (
            base_url
            or os.getenv("DEEPEVAL_LLM_BASE_URL")
            or os.getenv("AI_PROXY_BASE_URL")
            or "http://localhost:20128/v1"
        )

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        super().__init__(model=self.model_name, *args, **kwargs)

    def load_model(self):
        return self.client

    def _clean_json_string(self, text: str) -> str:
        """Extract clean JSON string from LLM response."""
        clean = text.strip()
        # Strip markdown code blocks
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines).strip()
        
        # Regex search for JSON object or array if extra preamble exists
        match = re.search(r"(\{.*\}|\[.*\])", clean, re.DOTALL)
        if match:
            return match.group(1).strip()
        return clean

    def generate(self, prompt: str, schema: Optional[type[BaseModel]] = None) -> str:
        client = self.load_model()
        messages = [{"role": "user", "content": prompt}]
        
        if schema is not None:
            messages = [
                {
                    "role": "system",
                    "content": "You are an evaluation judge. Respond strictly in valid JSON format matching the schema. Do not include markdown codeblocks or conversational text."
                },
                {"role": "user", "content": prompt},
            ]

        try:
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0,
            )
            raw = response.choices[0].message.content or ""
            return self._clean_json_string(raw)
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

    async def a_generate(self, prompt: str, schema: Optional[type[BaseModel]] = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        if schema is not None:
            messages = [
                {
                    "role": "system",
                    "content": "You are an evaluation judge. Respond strictly in valid JSON format matching the schema. Do not include markdown codeblocks or conversational text."
                },
                {"role": "user", "content": prompt},
            ]

        try:
            response = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0,
            )
            raw = response.choices[0].message.content or ""
            return self._clean_json_string(raw)
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

    def get_model_name(self) -> str:
        return self.model_name
