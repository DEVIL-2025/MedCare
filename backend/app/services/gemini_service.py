import os
import json
import logging
from typing import Any, Dict, List, Optional
from google import genai
from backend.app.config import settings

logger = logging.getLogger("MedCareControlTower.GeminiService")


class GeminiService:
    """
    Gemini-powered Natural Language Phrasing Service.
    Takes strictly grounded, pre-queried PostgreSQL supply chain records and generates
    natural language responses using Gemini (gemini-2.0-flash / gemini-2.5-flash).
    Enforces strict grounding constraints to prevent hallucinations.
    """

    def __init__(self, api_key: Optional[str] = None):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

        self.model_name = "gemini-2.0-flash"
        self._fallback_models = ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
        self._client: Optional[genai.Client] = None
        if self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
                logger.info("[GeminiService] Initialized Gemini client with primary model: %s", self.model_name)
            except Exception as e:
                logger.warning("[GeminiService] Failed to initialize Gemini client: %s", str(e))
                self._client = None
        else:
            logger.info("[GeminiService] No GEMINI_API_KEY configured. Assistant will use deterministic rule-based responses.")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    async def phrase_answer(
        self,
        user_query: str,
        grounded_data: Any,
        category: str = "General"
    ) -> Optional[str]:
        """
        Phrases a natural-language answer for user_query using ONLY the grounded_data provided.
        Returns None if client is unavailable or if an error occurs, allowing caller to fall back gracefully.
        """
        if not self._client:
            return None

        try:
            # Format grounded data cleanly
            if isinstance(grounded_data, (dict, list)):
                grounded_str = json.dumps(grounded_data, indent=2, default=str)
            else:
                grounded_str = str(grounded_data)

            prompt = (
                "You are the MedCare SCM Control Tower AI Assistant.\n"
                "Your task is to phrase a natural, professional, concise, executive-level answer "
                "to the user's question based EXCLUSIVELY on the verified real-time database records provided below.\n\n"
                "CRITICAL GROUNDING CONSTRAINTS:\n"
                "1. Use ONLY the facts, quantities, dates, statuses, SKUs, and DC locations present in the Verified Data section.\n"
                "2. NEVER fabricate, estimate, assume, hallucinate, or introduce any metrics or entities not found in the Verified Data.\n"
                "3. If the data is empty or indicates no records were found, clearly state that no records match in the database.\n"
                "4. Format the response using clean Markdown (bullet points, bold highlights, concise structure).\n"
                "5. Maintain an executive, clinical supply chain tone.\n\n"
                f"Query Category: {category}\n"
                f"User Question: \"{user_query}\"\n\n"
                "Verified Real-Time Data (Source: PostgreSQL):\n"
                f"{grounded_str}\n"
            )

            models_to_try = [self.model_name] + [m for m in self._fallback_models if m != self.model_name]
            
            for model_candidate in models_to_try:
                try:
                    response = await self._client.aio.models.generate_content(
                        model=model_candidate,
                        contents=prompt
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception as model_err:
                    err_msg = str(model_err)
                    if "404" in err_msg or "not found" in err_msg.lower() or "not available" in err_msg.lower():
                        continue
                    logger.warning("[GeminiService] Error with model %s: %s", model_candidate, err_msg)
                    break

            return None

        except Exception as e:
            logger.warning("[GeminiService] Error generating natural language phrasing: %s", str(e))
            return None


gemini_service = GeminiService()
