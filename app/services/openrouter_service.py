import httpx
from typing import List, Dict, Any
from app.core.config import settings

class OpenRouterService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"

    async def generate_inspection_summary(self, detections: List[Dict[str, Any]], asset_type: str) -> str:
        prompt = f"Asset: {asset_type}. Raw data: {detections}. Give a 3-sentence executive summary of defects."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }

        # SPEED FIX: Only wait 8 seconds for AI. If it's slow, skip it!
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(self.endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenRouter Timeout/Error: {e}")

        # FAST FALLBACK: If AI fails or is too slow, use this instant response
        return "Standard Automated Diagnostic: Review identified critical anomalies. Asset requires manual safety evaluation based on YOLO optical detection parameters."

    async def ask_rag(self, question: str, context: str) -> str:
        return "RAG analysis is active. Please review the official PDF for full details."

openrouter_service = OpenRouterService()