from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import os
import sys
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

logger = logging.getLogger("cloudinha-server")
from typing import Optional, List, Any

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from google.adk.runners import Runner
from google.genai.types import Content, Part
from src.agent.agent import agent, runner, session_service
from src.agent.workflow import run_workflow

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError

app = FastAPI()

# Runner and session_service are now imported from src.agent.agent
# This ensures consistent configuration between server and agent debugging tools.

class ChatRequest(BaseModel):
    chatInput: str
    userId: Optional[str] = None
    sessionId: Optional[str] = None 

# --- Retry Logic Configuration ---
RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=10),
    "retry": retry_if_exception_type((ConnectionError, TimeoutError, OSError)) # Including OSError for socket issues
}

@retry(**RETRY_CONFIG)
async def safe_get_or_create_session(app_name: str, session_id: str, user_id: str):
    try:
        await session_service.get_session(app_name=app_name, session_id=session_id, user_id=user_id)
    except Exception:
        # If get fails, try create (with its own internal logic or just retry the whole block if connection failed)
        # But here we want to handle the specific flow of get -> (if missing) create
        # If connection fails during get, retry.
        # If get fails due to "not found", we shouldn't retry, we should create.
        # However, session_service API details aren't fully visible, assuming standard behavior.
        # For network resilience, we'll try the whole sequence.
        pass
    
    await session_service.create_session(
        app_name=app_name,
        session_id=session_id,
        user_id=user_id
    )

@retry(**RETRY_CONFIG)
async def safe_run_workflow(user_id: str, session_id: str, new_message: Content) -> str:
    response_text = ""
    async for event in run_workflow(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message
    ):
        # Inspecting event structure
        logger.info(f"[DEBUG SERVER] Received event type: {type(event)}")
        if hasattr(event, 'text'): logger.info(f"  -> text: {event.text[:50]}...")
        if hasattr(event, 'content'): logger.info(f"  -> content parts: {len(event.content.parts) if event.content and event.content.parts else 0}")
        
        if hasattr(event, 'text') and event.text:
                response_text += event.text
        elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
        # Handle SimpleTextEvent from workflow (for Auth/Block messages)
        elif hasattr(event, "text"): 
            response_text += event.text
            
    return response_text

@retry(**RETRY_CONFIG)
async def safe_save_message(app_name: str, session_id: str, user_id: str, chat_input: str, response_text: str):
    current_session = await session_service.get_session(app_name=app_name, session_id=session_id, user_id=user_id)
    if hasattr(current_session, "insert_messages"):
        user_content = Content(role="user", parts=[Part(text=chat_input)])
        agent_content = Content(role="model", parts=[Part(text=response_text)])
        current_session.insert_messages([user_content, agent_content])
    else:
        print("Warning: current_session does not support insert_messages")

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"Received request: {request}", flush=True)

    
    # Enforce Authentication
    if not request.userId or request.userId.strip() == "" or request.userId == "anon-user":
         # Even error messages should be streamed or returned as standard error for client to handle
         # For simplicity in this migration, strict auth failure can return 401 immediately
         raise HTTPException(status_code=401, detail="Desculpe, não posso falar com você se não estiver logado.")

    user_id = request.userId
    session_id = request.sessionId or f"session-{user_id}"

    # Generator function for StreamingResponse
    async def event_generator():
        try:
            # 1. Ensure/Create Session
            try:
                await safe_get_or_create_session(app_name="cloudinha-server", session_id=session_id, user_id=user_id)
            except RetryError:
                error_msg = json.dumps({"type": "error", "content": "Estou com dificuldades de conexão no momento."})
                yield error_msg + "\n"
                return

            # 2. Run Workflow
            context_header = f"context_user_id={user_id}\n---\n"
            new_message = Content(parts=[Part(text=context_header + request.chatInput)])

            full_response_text = ""
            
            # current_text_chunk moved inside loop

            try:
                async for event in run_workflow(user_id, session_id, new_message):
                    # Debug Log
                    # logger.info(f"[RAW EVENT]: {event}")
                    # Force print to terminal for debugging visibility
                    print(f"[RAW EVENT]: {event}", flush=True)



                    # Ensure chunk is clean for this event
                    current_text_chunk = ""


                    # 0. Handle Custom Dict Events (Manual Tools/Logs from workflow)
                    if isinstance(event, dict):
                        json_output = json.dumps(event)
                        print(f"[STREAM OUTPUT]: {json_output}", flush=True)
                        yield json_output + "\n"

                        continue

                        # Inspect and Serialize Events
                        # ...
                    
                    if hasattr(event, 'candidates') and event.candidates:
                         for candidate in event.candidates:
                             for part in candidate.content.parts:
                                 if part.function_call:
                                     payload = {
                                         "type": "tool_start",
                                         "tool": part.function_call.name,
                                         "args": part.function_call.args
                                     }
                                     json_output = json.dumps(payload)
                                     print(f"[STREAM OUTPUT]: {json_output}", flush=True)
                                     print(f"[DEBUG SERVER] Sending tool_start for {part.function_call.name}", flush=True)
                                     yield json_output + "\n"

                                 
                                 if part.function_response:
                                      # Ensure we get a name, even if ADK event structure varies
                                      tool_name = getattr(part.function_response, 'name', 'unknown_tool')
                                      
                                      # Serialize response content into a string for UI
                                      response_content = str(part.function_response.response)[:150] # Truncate slightly larger
                                      
                                      payload = {
                                          "type": "tool_end",
                                          "tool": tool_name,
                                          "output": response_content
                                      }
                                      json_output = json.dumps(payload)
                                      print(f"[STREAM OUTPUT]: {json_output}", flush=True)
                                      print(f"[DEBUG SERVER] Sending tool_end for {tool_name}", flush=True)
                                      yield json_output + "\n"

                                      
                                 if part.text:
                                     current_text_chunk += part.text

                    # Standard text attributes (ADK normalization)
                    if hasattr(event, 'text') and event.text:
                        current_text_chunk += event.text
                    elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                        for part in event.content.parts:
                            if part.function_call:
                                payload = {
                                    "type": "tool_start",
                                    "tool": part.function_call.name,
                                    "args": part.function_call.args
                                }
                                json_output = json.dumps(payload)
                                print(f"[STREAM OUTPUT]: {json_output}", flush=True)
                                print(f"[DEBUG SERVER] Sending tool_start for {part.function_call.name} (from content)", flush=True)
                                yield json_output + "\n"

                            if part.function_response:
                                tool_name = getattr(part.function_response, 'name', 'unknown_tool')
                                response_content = str(part.function_response.response)[:150]
                                payload = {
                                    "type": "tool_end",
                                    "tool": tool_name,
                                    "output": response_content
                                }
                                json_output = json.dumps(payload)
                                print(f"[STREAM OUTPUT]: {json_output}", flush=True)
                                print(f"[DEBUG SERVER] Sending tool_end for {tool_name} (from content)", flush=True)
                                yield json_output + "\n"

                            if hasattr(part, 'text') and part.text:
                                current_text_chunk += part.text

                    if current_text_chunk:
                        full_response_text += current_text_chunk
                        payload = {
                            "type": "text",
                            "content": current_text_chunk
                        }
                        json_output = json.dumps(payload)
                        print(f"[STREAM OUTPUT]: {json_output}", flush=True)
                        yield json_output + "\n"

                        # Reset chunk for next iteration to send only deltas
                        current_text_chunk = ""

                        
            except RetryError:
                 error_msg = json.dumps({"type": "error", "content": "Falha de conexão durante o processamento."})
                 yield error_msg + "\n"
                 return
            except Exception as e:
                 error_msg = json.dumps({"type": "error", "content": f"Erro interno: {str(e)}"})
                 yield error_msg + "\n"
                 return

            if not full_response_text:
                # If nothing came back, send a default
                payload = {"type": "text", "content": "Desculpe, não consegui processar."}
                yield json.dumps(payload) + "\n"
                full_response_text = "Desculpe, não consegui processar."

            # 3. Persist Message (Fire and forget or wait?)
            # Since we are inside a generator, we can await here.
            try:
                await safe_save_message("cloudinha-server", session_id, user_id, request.chatInput, full_response_text)
            except Exception as e:
                print(f"Error saving chat history: {e}")
                # Don't send error to user, they already got the text

        except Exception as e:
            # Catch-all for top level generator errors
            logger.error(f"Stream Error: {e}")
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
