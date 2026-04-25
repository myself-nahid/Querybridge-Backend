import httpx
from typing import List

# In production, this would be the URL of the AI Team's Django microservice
# e.g., AI_SERVICE_URL = "http://ai-engine-service:8001/generate-sql-response"
AI_SERVICE_URL = "http://localhost:8001/api/ai/ask"

async def ask_ai_microservice(question: str, user_role: str, user_email: str) -> str:
    """
    Sends the user's question and RBAC context to the AI microservice.
    """
    payload = {
        "query": question,
        "context": {
            "role": user_role,
            "email": user_email
        }
    }
    
    try:
        # async httpx call to the AI engine
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Uncomment the below line when the AI team's service is live
            # response = await client.post(AI_SERVICE_URL, json=payload)
            # response.raise_for_status()
            # return response.json().get("answer", "I could not generate an answer.")
            
            # --- MOCK RESPONSE FOR NOW (Until AI team finishes their part) ---
            import asyncio
            await asyncio.sleep(1) # Simulate AI thinking time
            return f"Mock AI Response: Based on your role as {user_role}, the SQL results for '{question}' show a total of $45,000."
            
    except Exception as e:
        # Fallback error handling if AI service is down
        print(f"AI Service Error: {str(e)}")
        return "I am currently unable to reach the AI engine. Please try again later."