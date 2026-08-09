from datetime import datetime, timezone
from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def add_coffee(
    telegram_id: int,
    coffee_name: str,
    coffee_size: str,
    coffee_shop: str,
    rating: int | None = None
):
    data = {
        "telegram_id": telegram_id,
        "coffee_name": coffee_name,
        "coffee_size": coffee_size,
        "coffee_shop": coffee_shop,
        "rating": rating,
    }

    response = (
        supabase
        .table("coffee_logs")
        .insert(data)
        .execute()
    )

    return response.data


def get_today_coffees(telegram_id: int):
    start_of_day = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    response = (
        supabase
        .table("coffee_logs")
        .select("*")
        .eq("telegram_id", telegram_id)
        .gte("created_at", start_of_day.isoformat())
        .order("created_at", desc=True)
        .execute()
    )

    return response.data


def get_all_coffees(telegram_id: int):
    response = (
        supabase
        .table("coffee_logs")
        .select("*")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data


def delete_coffee(telegram_id: int, coffee_id: int):
    response = (
        supabase
        .table("coffee_logs")
        .delete()
        .eq("id", coffee_id)
        .eq("telegram_id", telegram_id)
        .execute()
    )

    return response.data
