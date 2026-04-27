import httpx
from typing import List, Dict
from app.core.config import settings

async def ask_ai_microservice(
    question: str, 
    user_id: int, 
    user_role: str, 
    allowed_dbs: List[str], 
    chat_history: List[Dict[str, str]]
) -> str:
    """
    Sends the real request to the AI Microservice, including history and RBAC context.
    """
    
    # CRITICAL FIX: The AI Developer expects a "flat" JSON structure, 
    # not nested inside a 'user_context' object!
    payload = {
        "query": question,
        "user_id": str(user_id),          
        "role": user_role,           
        "allowed_dbs": allowed_dbs,  
        "chat_history": chat_history
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(settings.AI_MICROSERVICE_URL, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # ADD THIS PRINT STATEMENT
            print(f"========== RAW AI RESPONSE ==========")
            print(data)
            print(f"=====================================")
            
            # For now, keep this the same
            return data.get("response", "I could not generate an answer at this time.")
            
    except httpx.ConnectError:
        return "System Error: The AI Microservice is currently offline or unreachable."
    except httpx.TimeoutException:
        return "System Error: The AI Microservice took too long to respond. Please try a simpler query."
    except httpx.HTTPStatusError as e:
        print(f"AI Service HTTP Error: {e.response.status_code} - {e.response.text}")
        return "System Error: The AI Microservice encountered an internal error while processing your request."
    except Exception as e:
        print(f"Unexpected AI Service Error: {str(e)}")
        return "System Error: An unexpected error occurred communicating with the AI engine."