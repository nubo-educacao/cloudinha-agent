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
    active_workflow: Optional[str] = None
    _messages: List[Content] = []

    def set_client(self, client: Any):
        self.client = client

    def _get_active_workflow(self) -> Optional[str]:
        """Helper to fetch current active_workflow from user_profiles."""
        try:
            # Use limit(1) instead of maybe_single to avoid 406/NoneType issues
            res = self.client.table("user_profiles").select("active_workflow").eq("id", self.user_id).limit(1).execute()
            if res and res.data and len(res.data) > 0:
                print(f"[SupabaseSession] Fetched active_workflow: {res.data[0].get('active_workflow')}")
                return res.data[0].get("active_workflow")
        except Exception as e:
            print(f"[SupabaseSession] Error determining active workflow: {e}")
        return None

    def load(self) -> List[Content]:
        """Loads messages from Supabase."""
        if not self.client:
             print("Warning: Supabase client not set in session.")
             return []
        try:
            # Dynamic Workflow Fetch
            active_wf = self._get_active_workflow()
            print(f"[SupabaseSession] Loading with active_workflow Context: {active_wf}")

            query = self.client.table("chat_messages") \
                .select("*") \
                .eq("user_id", self.user_id)
            
            if active_wf:
                query = query.eq("workflow", active_wf)
                
            response = query.order("created_at", desc=False).execute()
            
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

    def save(self, messages: List[Content]):
        """Saves new messages to Supabase."""
        if not self.client:
             return

        # Dynamic Workflow Fetch for Saving
        active_wf = self._get_active_workflow()
        print(f"[SupabaseSession] Saving with active_workflow Context: {active_wf}")

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
                "workflow": active_wf 
            }
            formatted_records.append(record)
        
        if formatted_records:
            try:
                self.client.table("chat_messages").insert(formatted_records).execute()
                # Update local cache
                self._messages.extend(new_messages)
            except Exception as e:
                print(f"Error saving to Supabase: {e}")

    def insert_messages(self, messages: List[Content]):
        """Explicitly inserts specific messages to Supabase with current workflow tag."""
        if not self.client:
             print("Warning: Client not set for insert_messages")
             return

        # Dynamic Workflow Fetch
        active_wf = self._get_active_workflow()
        print(f"[SupabaseSession] Manual Insert with active_workflow Context: {active_wf}")

        formatted_records = []
        for msg in messages:
            sender = "user" if msg.role == "user" else "cloudinha"
            
            # Extract text
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
                "workflow": active_wf 
            }
            formatted_records.append(record)
        
        if formatted_records:
            try:
                self.client.table("chat_messages").insert(formatted_records).execute()
                # Update local cache just in case
                self._messages.extend(messages)
                print(f"[SupabaseSession] Successfully inserted {len(formatted_records)} messages.")
            except Exception as e:
                print(f"Error manually saving to Supabase: {e}")

class SupabaseSessionService(BaseSessionService):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')
    
    client: Any = None
    _sessions: Dict[str, SupabaseSession] = {}
        
    def set_client(self, client: Any):
        self.client = client

    async def create_session(self, app_name: str, session_id: str, user_id: Optional[str] = None) -> Session:
        if not user_id:
             user_id = session_id 
        
        # --- DEBUG ALIAS ---
        if user_id == "user":
            user_id = "dac47479-079f-4878-bb43-009e4879fa8b" 
        
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
