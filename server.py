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
            print(f"[DEBUG SERVER] Received event type: {type(event)}")
            if hasattr(event, 'text'): print(f"  -> text: {event.text[:50]}...")
            if hasattr(event, 'content'): print(f"  -> content parts: {len(event.content.parts) if event.content and event.content.parts else 0}")
            
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

        # --- PERSISTENCE ---
        # Explicitly save the turn to Supabase with the correct workflow tag
        try:
            current_session = await session_service.get_session(app_name="cloudinha-server", session_id=session_id, user_id=user_id)
            if hasattr(current_session, "insert_messages"):
                user_content = Content(role="user", parts=[Part(text=request.chatInput)])
                agent_content = Content(role="model", parts=[Part(text=response_text)])
                current_session.insert_messages([user_content, agent_content])
            else:
                 print("Warning: current_session does not support insert_messages")
        except Exception as save_err:
             print(f"Error saving chat history: {save_err}")
             import traceback
             traceback.print_exc()

        return {"response": response_text}

    except Exception as e:
        print(f"Error processing request: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
