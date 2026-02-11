import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

def require_env(var_name: str, value: str):
    if not value:
        raise RuntimeError(f"Missing required env var: {var_name}")
