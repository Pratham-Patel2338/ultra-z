import asyncio
import logging
import time
from typing import AsyncGenerator

import aiohttp

from app.core.config import settings
from app.core.logging_config import setup_logging

logger = setup_logging(__name__)


class OllamaService:
    """
    Production-grade Ollama integration service.

    Features:
    - Async HTTP client for non-blocking LLM calls
    - Automatic retry with exponential backoff
    - Streaming and non-streaming responses
    - Proper error handling and logging
    - Configurable timeouts
    - System prompts and chat history support
    """

    def __init__(
        self,
        base_url: str = settings.ollama_base_url,
        model: str = settings.ollama_chat_model,
        timeout: int = settings.ollama_timeout,
        retry_attempts: int = settings.ollama_retry_attempts,
        retry_delay: float = settings.ollama_retry_delay,
    ):
        """
        Initialize Ollama service.

        Args:
            base_url: Ollama server base URL
            model: Model name to use (e.g., 'llama2', 'llama3')
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """Strip common Ollama tags so base-model comparisons are stable."""
        return model_name.split(":", 1)[0].strip().lower()

    def _model_matches(self, installed_name: str) -> bool:
        """Return True when the configured model matches an installed Ollama model."""
        requested = self.model.strip().lower()
        installed = installed_name.strip().lower()
        requested_base = self._normalize_model_name(requested)
        installed_base = self._normalize_model_name(installed)
        return (
            requested == installed
            or requested == installed_base
            or requested_base == installed
            or requested_base == installed_base
            or requested_base in installed
        )

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _call_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict | None:
        """
        Make HTTP call with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for aiohttp request

        Returns:
            Response JSON or None on failure
        """
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        delay = self.retry_delay

        for attempt in range(self.retry_attempts):
            try:
                async with session.request(
                    method,
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    **kwargs,
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(
                            f"Ollama request failed with status {response.status}: {await response.text()}"
                        )
                        if attempt < self.retry_attempts - 1:
                            await asyncio.sleep(delay)
                            delay *= 2
                        continue
            except asyncio.TimeoutError:
                logger.error(f"Ollama request timeout (attempt {attempt + 1}/{self.retry_attempts})")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
            except aiohttp.ClientError as e:
                logger.error(f"Ollama connection error (attempt {attempt + 1}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
            except Exception as e:
                logger.error(f"Unexpected error in Ollama request: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2

        logger.error(f"Ollama request failed after {self.retry_attempts} attempts")
        return None

    async def _stream_call_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Make streaming HTTP call with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for aiohttp request

        Yields:
            Streamed response text chunks
        """
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        delay = self.retry_delay

        for attempt in range(self.retry_attempts):
            try:
                async with session.request(
                    method,
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    **kwargs,
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                yield line.decode("utf-8")
                        return
                    else:
                        logger.warning(
                            f"Ollama stream request failed with status {response.status}"
                        )
                        if attempt < self.retry_attempts - 1:
                            await asyncio.sleep(delay)
                            delay *= 2
            except asyncio.TimeoutError:
                logger.error(f"Ollama stream request timeout (attempt {attempt + 1}/{self.retry_attempts})")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
            except aiohttp.ClientError as e:
                logger.error(f"Ollama stream connection error (attempt {attempt + 1}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
            except Exception as e:
                logger.error(f"Unexpected error in Ollama stream request: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2

        logger.error(f"Ollama stream request failed after {self.retry_attempts} attempts")

    async def health_check(self) -> bool:
        """
        Check if Ollama server is healthy and model is available.

        Returns:
            True if server is reachable and model is loaded, False otherwise
        """
        try:
            result = await self._call_with_retry("GET", "/api/tags")
            if result and "models" in result:
                models = [m.get("name", "") for m in result["models"]]
                is_available = any(self._model_matches(model_name) for model_name in models)
                if is_available:
                    logger.info(f"Ollama health check passed. Model '{self.model}' is available.")
                    return True
                else:
                    logger.warning(f"Model '{self.model}' not found in Ollama. Available models: {models}")
                    return False
            return False
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def test_llm(self) -> str:
        """Send a simple test prompt to verify Ollama is available."""
        logger.info("Connecting to Ollama")
        try:
            response = await self.generate("Say only OK.")
            if response:
                logger.info("Ollama connected")
                logger.info("Warmup completed")
                return response
            logger.error("Ollama unavailable: empty response")
            return ""
        except Exception as exc:
            logger.error("Ollama unavailable: %s", exc, exc_info=True)
            raise

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        top_p: float = 0.8,
    ) -> str:
        """
        Generate response from Ollama (non-streaming).

        Args:
            prompt: User prompt/message
            system_prompt: System instruction for the model
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter

        Returns:
            Generated response text or empty string on error
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
            "options": {
                "num_predict": 60,
                "keep_alive": "30m",
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        logger.info(f"Generating response from Ollama (model: {self.model})")
        start = time.perf_counter()

        result = await self._call_with_retry(
            "POST",
            "/api/generate",
            json=payload,
        )
        elapsed = time.perf_counter() - start
        logger.info("LLM stage completed in %.3f sec", elapsed)
        
        if result and "response" in result:
            response_text = result["response"].strip()
            logger.info(f"Successfully generated response ({len(response_text)} chars)")
            return response_text
        else:
            logger.error("Ollama generate failed: No response in result")
            return ""

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        top_p: float = 0.8,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response from Ollama.

        Args:
            prompt: User prompt/message
            system_prompt: System instruction for the model
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter

        Yields:
            Response text chunks as they arrive
        """
        import json

        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "options": {
                "num_predict": 60,
                "keep_alive": "30m",
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        logger.info(f"Starting streaming response from Ollama (model: {self.model})")

        async for chunk in self._stream_call_with_retry(
            "POST",
            "/api/generate",
            json=payload,
        ):
            try:
                data = json.loads(chunk)
                if "response" in data:
                    yield data["response"]
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Error processing stream chunk: {e}")
                continue

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.3,
        top_p: float = 0.8,
    ) -> str:
        """
        Chat-based completion with message history.

        Args:
            messages: List of message dicts with 'role' (user/assistant) and 'content'
            system_prompt: System instruction for the model
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter

        Returns:
            Generated response text or empty string on error
        """
        chat_messages = list(messages)
        if system_prompt:
            chat_messages = [{"role": "system", "content": system_prompt}] + chat_messages

        payload = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
            "options": {
                "num_predict": 60,
                "keep_alive": "30m",
            },
        }

        logger.info(f"Starting chat with Ollama (model: {self.model}, messages: {len(messages)})")
        start = time.perf_counter()

        result = await self._call_with_retry(
            "POST",
            "/api/chat",
            json=payload,
        )
        elapsed = time.perf_counter() - start
        logger.info("LLM stage completed in %.3f sec", elapsed)

        if result and "message" in result and "content" in result["message"]:
            response_text = result["message"]["content"].strip()
            logger.info(f"Successfully generated chat response ({len(response_text)} chars)")
            return response_text
        else:
            logger.error("Ollama chat failed: No message content in result")
            return ""

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.5,
        top_p: float = 0.9,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat-based completion with message history.

        Args:
            messages: List of message dicts with 'role' (user/assistant) and 'content'
            system_prompt: System instruction for the model
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter

        Yields:
            Response text chunks as they arrive
        """
        import json

        chat_messages = list(messages)
        if system_prompt:
            chat_messages = [{"role": "system", "content": system_prompt}] + chat_messages

        payload = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "options": {
                "num_predict": 60,
                "keep_alive": "30m",
            },
        }

        logger.info(f"Starting streaming chat with Ollama (model: {self.model}, messages: {len(messages)})")

        async for chunk in self._stream_call_with_retry(
            "POST",
            "/api/chat",
            json=payload,
        ):
            try:
                data = json.loads(chunk)
                if "message" in data and "content" in data["message"]:
                    yield data["message"]["content"]
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Error processing stream chunk: {e}")
                continue
