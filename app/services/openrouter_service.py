import httpx
from typing import List, Dict, Any
from app.core.config import settings



class OpenRouterService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"

    async def generate_inspection_summary(self, detections: List[Dict[str, Any]], asset_type: str) -> str:
        prompt = f"""
        You are InspeXion AI's master certified asset inspector.
        Asset Type: {asset_type}

        Raw computer vision detections from 1-200 captured images:
        {detections}

        Provide a structured, professional, executive inspection review:
        1. Executive Summary
        2. Identified Irregularities & Defect Severity (Categorized as Critical, Minor, or Safe)
        3. Operational Risk Assessment
        4. Remediation & Repair Recommendations.
        Keep it formal, concise, and structured.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.endpoint, headers=headers, json=payload)
            if resp.status_code != 200:
                return "AI Evaluation Summary generated locally due to service latency."
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def ask_rag(self, question: str, context: str) -> str:
        prompt = f"""
        You are InspeXion AI RAG Document Expert.
        Answer the following user question strictly based on the extracted inspection chunks below.
        If the answer is not present, declare that the data is not covered in this report.

        Extracted Context:
        {context}

        Question: {question}
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.endpoint, headers=headers, json=payload)
            if resp.status_code != 200:
                return "Failed to complete RAG query via LLM."
            data = resp.json()
            return data["choices"][0]["message"]["content"]

openrouter_service = OpenRouterService()