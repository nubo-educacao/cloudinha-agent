import os
from dotenv import load_dotenv

load_dotenv()

service_key = os.getenv("SUPABASE_SERVICE_KEY")
anon_key = os.getenv("SUPABASE_KEY")

print(f"SUPABASE_SERVICE_KEY set: {bool(service_key)}")
if service_key:
    print(f"Service Key length: {len(service_key)}")
    print(f"Service Key prefix: {service_key[:5]}...")

print(f"SUPABASE_KEY set: {bool(anon_key)}")
if anon_key:
    # Check if they are identical
    if service_key == anon_key:
        print("WARNING: SUPABASE_SERVICE_KEY is identical to SUPABASE_KEY (Anon). RLS will NOT be bypassed.")
    else:
        print("Keys are different.")
