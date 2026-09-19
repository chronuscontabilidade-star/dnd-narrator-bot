import asyncio
import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from google import genai
except Exception:  # pragma: no cover - SDK optional in offline environments
    genai = None

log = logging.getLogger(__name__)

try:
    from .game.adventure import AdventureState, adventure_generation_prompt, empty_adventure_state
except ImportError:  # suporte ao modo script: python dnd_bot/bot.py
    from game.adventure import AdventureState, adventure_generation_prompt, empty_adventure_state

SYSTEM_PROMPT = """Você é um Mestre de RPG experiente e criativo especializado em D&D 5e.
Você narra aventuras imersivas em português do Brasil com descrições vívidas e tensão dramática.
Sempre mantenha consistência com o contexto da aventura e as ações anteriores.
Seja criativo, mas não invente fatos que contradigam o estado atual da sessão.
Retorne sempre JSON válido, sem markdown, sem explicações extras.
"""


class Narrator:
    def __init__(self, api_key: str):
        self.api_key = api_key or ""
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.alt_api_key = os.getenv("AI_API_KEY", "")
        self.alt_base_url = (os.getenv("AI_BASE_URL", "") or "").rstrip("/")
        self.alt_model = os.getenv("AI_MODEL", "")
        self.bastiao_api_key = os.getenv("BASTIAO_API_KEY", "")
        self.bastiao_base_url = (os.getenv("BASTIAO_BASE_URL", "") or "").rstrip("/")
        self.bastiao_model = os.getenv("BASTIAO_MODEL", "")
        self.image_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
        self.client = genai.Client(api_key=self.api_key) if self.api_key and genai is not None else None
        self._provider_cooldowns = {}
        self._cooldown_seconds = int(os.getenv("AI_PROVIDER_COOLDOWN_SECONDS", "60"))
