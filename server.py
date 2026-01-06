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
from src.agent.workflow import run_workflow

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
    
    # Enforce Authentication
    if not request.userId or request.userId.strip() == "" or request.userId == "anon-user":
         return {"response": "Desculpe, não posso falar com você se não estiver logado."}

    user_id = request.userId
    # Use provided sessionId or generate one based on user_id
    session_id = request.sessionId or f"session-{user_id}"

    # Ensure session exists
    try:
        await session_service.get_session(app_name="cloudinha-server", session_id=session_id, user_id=user_id)
    except Exception:
        pass

    try:
        await session_service.create_session(
            app_name="cloudinha-server",
            session_id=session_id,
            user_id=user_id
        )
    except Exception:
        pass

    try:
        response_text = ""
        
        # Preparing the message content with hidden context
        # This context is still useful for root_agent
        context_header = f"context_user_id={user_id}\n---\n"
        new_message = Content(parts=[Part(text=context_header + request.chatInput)])

        # Use the new workflow
        async for event in run_workflow(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message
        ):
            # Inspecting event structure
            if hasattr(event, 'text') and event.text:
                 response_text += event.text
            elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                 for part in event.content.parts:
                     if hasattr(part, 'text') and part.text:
                         response_text += part.text
            # Handle SimpleTextEvent from workflow (for Auth/Block messages)
            elif hasattr(event, "text"): 
                response_text += event.text

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
