import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL is not set")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY is not set")
