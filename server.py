from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import os
import sys
from typing import Optional, List, Any

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from google.adk.runners import Runner
from google.genai.types import Content, Part
from src.agent.agent import agent, runner, session_service

app = FastAPI()

# Runner and session_service are now imported from src.agent.agent
# This ensures consistent configuration between server and agent debugging tools.

class ChatRequest(BaseModel):
    chatInput: str
    userId: Optional[str] = None
    history: Optional[List[Any]] = None
    sessionId: Optional[str] = None 

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"Received request: {request}")
    
    # Use provided userId or default to 'anon'
    user_id = request.userId or "anon-user"
    
    # Use provided sessionId or generate one based on user_id (simple fallback)
    session_id = request.sessionId or f"session-{user_id}"

    # Ensure session exists
    # Ensure session exists
    try:
        # Check if session exists
        await session_service.get_session(app_name="cloudinha-server", session_id=session_id, user_id=user_id)
    except Exception:
        # Create if not found (or if get_session failed for other reasons, though ideally we check specific error)
        # However, since get_session might fail if not found, we try to create.
        # But if it failed due to other reasons, create might also fail. 
        # Better pattern: Try create, ignore AlreadyExists.
        pass

    try:
        await session_service.create_session(
            app_name="cloudinha-server",
            session_id=session_id,
            user_id=user_id
        )
    except Exception as e:
        # If it already exists, that's fine.
        # The ADK might raise specific error, but generic catch is safe here for "ensure exists" logic 
        # if we assume the only error we care about ignoring is "already exists".
        # Let's check the error message to be safe or just print it for debug if needed.
        # print(f"Session creation note: {e}")
        pass



    try:
        response_text = ""
        
        # Preparing the message content with hidden context
        context_header = f"context_user_id={user_id}\n---\n"
        new_message = Content(parts=[Part(text=context_header + request.chatInput)])

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message
        ):
            # Inspecting event structure
            # Based on common ADK patterns, looking for ModelResponse or nested text
            if hasattr(event, 'text') and event.text:
                 response_text += event.text
            elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                 for part in event.content.parts:
                     if hasattr(part, 'text') and part.text:
                         response_text += part.text
            # If event is a list of parts or similar structure (adjust as needed)
            
            # Debugging event structure if response is empty
            # print(f"Event: {event}")

        if not response_text:
            response_text = "Desculpe, não consegui processar sua solicitação."

        return {"response": response_text}

    except Exception as e:
        print(f"Error processing request: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
