from typing import List, Dict, Any, Optional
import os
from datetime import datetime
from google.adk.sessions import Session, BaseSessionService
from google.genai.types import Content, Part
from supabase import Client

from pydantic import ConfigDict

class SupabaseSession(Session):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')
    
    user_id: str
    client: Any = None 
    _messages: List[Content] = []

    def set_client(self, client: Any):
        self.client = client

    def load(self) -> List[Content]:
        """Loads messages from Supabase."""
        if not self.client:
             print("Warning: Supabase client not set in session.")
             return []
        try:
            response = self.client.table("chat_messages") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .order("created_at", desc=False) \
                .execute()
            
            messages = []
            data = response.data or []
            for record in data:
                role = "user" if record["sender"] == "user" else "model"
                content = Content(
                    role=role,
                    parts=[Part(text=record["content"])]
                )
                messages.append(content)
            
            self._messages = messages
            return messages
        except Exception as e:
            print(f"Error loading session from Supabase: {e}")
            return []
        except Exception as e:
            print(f"Error loading session from Supabase: {e}")
            return []

    def save(self, messages: List[Content]):
        """Saves new messages to Supabase."""
        if not self.client:
             return

        if not self._messages:
             existing_count = 0
        else:
             existing_count = len(self._messages)
             
        new_messages = messages[existing_count:]
        
        if not new_messages:
            return

        formatted_records = []
        for msg in new_messages:
            sender = "user" if msg.role == "user" else "cloudinha"
            
            # Extract text from parts
            text_content = ""
            if msg.parts:
                for part in msg.parts:
                    if hasattr(part, 'text') and part.text:
                        text_content += part.text
            
            if not text_content:
                continue

            record = {
                "user_id": self.user_id,
                "sender": sender,
                "content": text_content,
            }
            formatted_records.append(record)
        
        if formatted_records:
            try:
                self.client.table("chat_messages").insert(formatted_records).execute()
                # Update local cache
                self._messages.extend(new_messages)
            except Exception as e:
                print(f"Error saving to Supabase: {e}")

class SupabaseSessionService(BaseSessionService):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')
    
    client: Any = None
    _sessions: Dict[str, SupabaseSession] = {}
        
    def set_client(self, client: Any):
        self.client = client

    async def create_session(self, app_name: str, session_id: str, user_id: Optional[str] = None) -> Session:
        if not user_id:
             user_id = session_id 
        
        # Pydantic initialization
        session = SupabaseSession(id=session_id, appName=app_name, user_id=user_id)
        if self.client:
            session.set_client(self.client)
            
        self._sessions[session_id] = session
        return session

    async def get_session(self, app_name: str, session_id: str, user_id: Optional[str] = None) -> Session:
        if session_id in self._sessions:
             return self._sessions[session_id]
        
        return await self.create_session(app_name, session_id, user_id)

    async def list_sessions(self, app_name: str) -> List[Session]:
        return list(self._sessions.values())

    async def delete_session(self, app_name: str, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
