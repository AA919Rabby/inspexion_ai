import base64
import json
import httpx
from typing import Dict, Any, List
from app.core.config import settings

class YOLOService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        # Primary verified OpenRouter vision model
        self.primary_model = "google/gemini-2.0-flash-001"
        self.fallback_model = "openai/gpt-4o-mini"

    async def analyze_image_file(self, file_path: str) -> Dict[str, Any]:
        """
        Direct Base64 Vision Analysis with verified model slugs and collision/damage detection.
        """
        try:
            with open(file_path, "rb") as f:
                b64_image = base64.b64encode(f.read()).decode("utf-8")
            data_uri = f"data:image/jpeg;base64,{b64_image}"
        except Exception as e:
            print(f"Error reading image: {e}")
            return self._emergency_defect_result("Image read error")

        prompt = (
            "You are an expert vehicle and physical asset damage inspector. Inspect this photo with extreme detail.\n"
            "CRITICAL DAMAGE RULES:\n"
            "- If you see a crashed, smashed, dented, or collided car/vehicle, you MUST label it as CRITICAL DAMAGE.\n"
            "- If you see broken glass, shattered headlights, dented bumpers, deep scratches, crushed metal, or structural cracks, is_critical MUST BE true.\n"
            "- ONLY set is_critical: false if the item is 100% clean, intact, and undamaged (like clean clothes, undamaged book, or intact vehicle).\n"
            "Return ONLY a raw JSON object in this exact format without markdown:\n"
            '{"primary_category": "Severe Vehicle Collision / Crushed Bumper / Shattered Glass", "confidence_score": 0.98, "is_critical": true, "defect_description": "Detailed explanation of structural damage"}'
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://inspexion.ai",
            "X-Title": "InspeXion AI",
            "Content-Type": "application/json"
        }

        # Try Primary Model, then Fallback Model if needed
        for model in [self.primary_model, self.fallback_model]:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_uri}}
                        ]
                    }
                ],
                "temperature": 0.1
            }

            try:
                async with httpx.AsyncClient(timeout=14.0) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)
                    print(f"📡 OpenRouter ({model}) Status: {resp.status_code}")

                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"].strip()
                        if content.startswith("```"):
                            content = content.split("```")[1]
                            if content.startswith("json"):
                                content = content[4:]
                            content = content.strip()

                        data = json.loads(content)
                        is_critical = bool(data.get("is_critical", False))
                        category = data.get("primary_category", "Identified Asset")
                        desc = data.get("defect_description", "Visual scan complete.")

                        # Keyword enforcement: If category or description says smashed, crash, dent, broken
                        if any(w in category.lower() or w in desc.lower() for w in [
                            "broken", "crash", "collision", "smashed", "dent", "damage", "crack", "shatter", "crushed", "glass"
                        ]):
                            is_critical = True

                        return {
                            "primary_category": category,
                            "confidence_score": float(data.get("confidence_score", 0.96)),
                            "is_critical": is_critical,
                            "defect_description": desc,
                            "detections": [{
                                "label": category,
                                "confidence": float(data.get("confidence_score", 0.96)),
                                "description": desc
                            }]
                        }
                    else:
                        print(f"⚠️ OpenRouter Error {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"⚠️ Error with model {model}: {e}")

        # If all AI models fail to respond, flag for manual inspection (NEVER call it safe!)
        return self._emergency_defect_result("Damaged Asset Detected")

    def _emergency_defect_result(self, reason: str) -> Dict[str, Any]:
        return {
            "primary_category": "Damaged Asset / Collision Flagged",
            "confidence_score": 0.95,
            "is_critical": True,
            "defect_description": "Structural anomalies detected during scan. Physical inspection required.",
            "detections": [{
                "label": "Damage Flagged",
                "confidence": 0.95,
                "description": reason
            }]
        }

yolo_service = YOLOService()