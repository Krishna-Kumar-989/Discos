import os
import json
import httpx
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("generation.providers")

class BaseLLMProvider(ABC):
    def __init__(self, model_name: str, temperature: float, max_tokens: int):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass


class MockProvider(BaseLLMProvider):
    """Simulates a generation response for testing pipelines without API keys."""
    async def generate(self, prompt: str) -> str:
        logger.info("MockProvider: Generating mock response...")
        return f"[MOCK RESPONSE from {self.model_name}]\nBased on the provided context, I can confirm the retrieval pipeline is working. Your query was successfully injected into the prompt."


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider supporting native library or httpx fallback."""
    def __init__(self, model_name: str, temperature: float, max_tokens: int):
        super().__init__(model_name, temperature, max_tokens)
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
            
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            response = await client.chat.completions.create(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except ImportError:
            # Fallback to direct REST API call if `openai` SDK is not installed
            logger.debug("openai SDK not found. Falling back to httpx for OpenAI API.")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]


class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider supporting native library or httpx fallback."""
    def __init__(self, model_name: str, temperature: float, max_tokens: int):
        super().__init__(model_name, temperature, max_tokens)
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
            
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.api_key)
            response = await client.messages.create(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except ImportError:
            logger.debug("anthropic SDK not found. Falling back to httpx for Anthropic API.")
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider supporting native library or httpx fallback."""
    def __init__(self, model_name: str, temperature: float, max_tokens: int):

        super().__init__(model_name, temperature, max_tokens)
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            # Make async generation using the standard wrapper 
            model = genai.GenerativeModel(self.model_name)
            # Use generate_content_async if available, else fallback to thread execution
            import asyncio
            if hasattr(model, "generate_content_async"):
                response = await model.generate_content_async(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens,
                    )
                )
            else:
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens,
                    )
                )
            return response.text
        except ImportError:
            logger.debug("google.generativeai SDK not found. Falling back to httpx for Gemini API.")
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_tokens
                }
            }
          
            full_model_name = self.model_name if "models/" in self.model_name else f"models/{self.model_name}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{full_model_name}:generateContent?key={self.api_key}"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    return f"Error parsing Gemini response: {data}"


class OllamaProvider(BaseLLMProvider):
    """Ollama local provider using direct API calls."""
    def __init__(self, model_name: str, temperature: float, max_tokens: int):
        super().__init__(model_name, temperature, max_tokens)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

    async def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")


class GroqProvider(BaseLLMProvider):
    """Groq provider supporting native library or httpx fallback."""
    def __init__(self, model_name: str, temperature: float, max_tokens: int):
        super().__init__(model_name, temperature, max_tokens)
        self.api_key = os.getenv("GROQ_API_KEY", "")

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")
            

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error(f"Groq API Error Response: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


def get_provider(provider_name: str, model_name: str, temperature: float, max_tokens: int) -> BaseLLMProvider:
    """Factory to instantiate the requested LLM provider."""
    provider_name = provider_name.lower()
    if provider_name == "openai":
        return OpenAIProvider(model_name, temperature, max_tokens)
    elif provider_name == "anthropic":
        return AnthropicProvider(model_name, temperature, max_tokens)
    elif provider_name == "gemini":
        return GeminiProvider(model_name, temperature, max_tokens)
    elif provider_name == "ollama":
        return OllamaProvider(model_name, temperature, max_tokens)
    elif provider_name == "groq":
        return GroqProvider(model_name, temperature, max_tokens)
    elif provider_name == "mock":
        return MockProvider(model_name, temperature, max_tokens)
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")
