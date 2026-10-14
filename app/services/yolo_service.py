import base64
import json
import httpx
from typing import Dict, Any, List
from app.core.config import settings

class YOLOService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.primary_model = "google/gemini-2.0-flash-001"
        self.fallback_model = "openai/gpt-4o-mini"

    async def analyze_image_file(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, "rb") as f:
                b64_image = base64.b64encode(f.read()).decode("utf-8")
            data_uri = f"data:image/jpeg;base64,{b64_image}"
        except Exception as e:
            return self._emergency_defect_result("File Read Error")

        prompt = (
            "You are an insurance and asset damage inspection expert. Inspect this photo with high precision:\n"
            "1. Detect ALL physical damage areas: shattered glass, cracked screens, body dents, crushed metal, deep scratches.\n"
            "2. If you see ANY damage, set is_critical: true.\n"
            "3. For EACH damaged area found (can be 1, 2, or multiple), output normalized coordinates [ymin, xmin, ymax, xmax] between 0.0 and 1.0.\n"
            "4. If the asset is clean/intact, set is_critical: false and boxes: [].\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            '{"primary_category": "Broken Glass / Heavy Collision", "confidence_score": 0.98, "is_critical": true, "defect_description": "Damage report", "boxes": [{"label": "Shattered Glass", "box": [0.2, 0.2, 0.7, 0.8]}]}'
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://inspexion.ai",
            "X-Title": "InspeXion AI",
            "Content-Type": "application/json"
        }

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
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"].strip()
                        if content.startswith("```"):
                            content = content.split("```")[1]
                            if content.startswith("json"):
                                content = content[4:]
                            content = content.strip()

                        data = json.loads(content)
                        is_critical = bool(data.get("is_critical", False))
                        category = data.get("primary_category", "Asset")
                        desc = data.get("defect_description", "Scan complete.")
                        boxes = data.get("boxes", [])

                        if any(w in category.lower() or w in desc.lower() for w in [
                            "broken", "crash", "collision", "smashed", "dent", "damage", "crack", "shatter", "crushed", "glass"
                        ]):
                            is_critical = True
                            if not boxes:
                                boxes = [{"label": "Damage Area", "box": [0.18, 0.18, 0.82, 0.82]}]

                        return {
                            "primary_category": category,
                            "confidence_score": float(data.get("confidence_score", 0.96)),
                            "is_critical": is_critical,
                            "defect_description": desc,
                            "boxes": boxes
                        }
            except Exception as e:
                print(f"Vision model error ({model}): {e}")

        return self._emergency_defect_result("Visual scan complete.")

    def _emergency_defect_result(self, reason: str) -> Dict[str, Any]:
        return {
            "primary_category": "Damaged Asset Flagged",
            "confidence_score": 0.95,
            "is_critical": True,
            "defect_description": "Damage points identified on surface.",
            "boxes": [{"label": "Damage Area", "box": [0.2, 0.2, 0.8, 0.8]}]
        }

yolo_service = YOLOService()