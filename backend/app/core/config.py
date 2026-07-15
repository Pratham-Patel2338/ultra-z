from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ULTRA-Z Backend"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./ultra_z.db"
    admin_pin: str = "1234"
    token_secret_key: str = "change-this-secret"
    token_max_age_seconds: int = 60 * 60 * 24 * 7

    # Ollama LLM Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:3b"
    ollama_embedding_model: str = "nomic-embed-text:latest"
    ollama_vision_model: str = "llava:7b"
    ollama_timeout: int = 300
    ollama_retry_attempts: int = 3
    ollama_retry_delay: float = 1.0
    # Ollama generation tuning defaults (can be overridden via env).
    # Keep this high enough for normal assistant answers; too-low values truncate responses.
    ollama_num_predict: int = 256
    ollama_num_ctx: int = 2048
    ollama_repeat_penalty: float = 1.05

    # Speech-to-text configuration
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str | None = None

    # Text-to-speech configuration
    tts_cache_dir: str = "storage/tts_cache"
    tts_cache_ttl_hours: int = 24
    tts_cache_max_files: int = 500
    tts_default_voice: str = "auto"
    tts_engine: str = "kokoro"
    tts_use_cuda: bool = False
    tts_length_scale: float = 0.85
    tts_kokoro_model_path: str | None = None
    tts_kokoro_voices_path: str | None = None
    tts_kokoro_default_voice: str = "af_bella"
    tts_noise_scale: float = 0.55
    tts_noise_w_scale: float = 0.6
    tts_english_model_path: str | None = None
    tts_english_config_path: str | None = None
    tts_hindi_model_path: str | None = None
    tts_hindi_config_path: str | None = None
    tts_gujarati_model_path: str | None = None
    tts_gujarati_config_path: str | None = None

    # ---------------------------------------------------------------------------
    # Wake Word Detection Configuration
    # ---------------------------------------------------------------------------
    # Set wakeword_enabled=True to auto-start the background listener on startup.
    # The default model alias "arise" maps to the built-in "hey_jarvis" OWW model.
    # Provide a custom .onnx file via wakeword_custom_model_path for a true
    # "Arise"-trained trigger.
    wakeword_enabled: bool = True
    wakeword_model: str = "arise"                   # Built-in alias (see detector.py)
    wakeword_custom_model_path: str | None = None    # Path to a custom .onnx model
    wakeword_threshold: float = 0.5                  # 0.0–1.0  (lower = more sensitive)
    wakeword_sample_rate: int = 16000                # Must match OWW's 16 kHz requirement
    wakeword_chunk_size: int = 1280                  # Samples per PyAudio read (~80 ms)
    wakeword_silence_rms_threshold: float = 300.0   # Energy below this = silence
    wakeword_silence_timeout_secs: float = 1.5      # Seconds of silence to stop recording
    wakeword_max_record_secs: float = 30.0           # Hard cap on recording duration

    @property
    def ollama_model(self) -> str:
        """Backward-compatible alias for the primary chat model."""
        return self.ollama_chat_model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
