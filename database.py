import asyncio
from datetime import datetime, timezone

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY


# =========================================================
# SUPABASE
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# =========================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# =========================================================

async def run_sync(function):
    """
    Запускает синхронный Supabase-запрос
    в отдельном потоке, чтобы не блокировать бота.
    """

    return await asyncio.to_thread(
        function
    )


# =========================================================
# ДОБАВИТЬ КОФЕ
# =========================================================

async def add_coffee(
    telegram_id: int,
    coffee_name: str,
    coffee_size: str,
    coffee_shop: str,
    rating: int | None = None,
):
    data = {
        "telegram_id": telegram_id,
        "coffee_name": coffee_name,
        "coffee_size": coffee_size,
        "coffee_shop": coffee_shop,
        "rating": rating,
    }

    def query():
        return (
            supabase
            .table("coffee_logs")
            .insert(data)
            .execute()
        )

    response = await run_sync(query)

    return response.data


# =========================================================
# КОФЕ ЗА СЕГОДНЯ
# =========================================================

async def get_today_coffees(
    telegram_id: int,
):
    now = datetime.now(timezone.utc)

    start_of_day = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    def query():
        return (
            supabase
            .table("coffee_logs")
            .select("*")
            .eq(
                "telegram_id",
                telegram_id,
            )
            .gte(
                "created_at",
                start_of_day.isoformat(),
            )
            .order(
                "created_at",
                desc=True,
            )
            .execute()
        )

    response = await run_sync(query)

    return response.data


# =========================================================
# ВСЯ ИСТОРИЯ
# =========================================================

async def get_all_coffees(
    telegram_id: int,
):
    def query():
        return (
            supabase
            .table("coffee_logs")
            .select("*")
            .eq(
                "telegram_id",
                telegram_id,
            )
            .order(
                "created_at",
                desc=True,
            )
            .execute()
        )

    response = await run_sync(query)

    return response.data


# =========================================================
# ПОЛУЧИТЬ КОНКРЕТНУЮ ЗАПИСЬ
# =========================================================

async def get_coffee(
    telegram_id: int,
    coffee_id: int,
):
    def query():
        return (
            supabase
            .table("coffee_logs")
            .select("*")
            .eq(
                "id",
                coffee_id,
            )
            .eq(
                "telegram_id",
                telegram_id,
            )
            .maybe_single()
            .execute()
        )

    response = await run_sync(query)

    return response.data


# =========================================================
# УДАЛИТЬ КОФЕ
# =========================================================

async def delete_coffee(
    telegram_id: int,
    coffee_id: int,
):
    def query():
        return (
            supabase
            .table("coffee_logs")
            .delete()
            .eq(
                "id",
                coffee_id,
            )
            .eq(
                "telegram_id",
                telegram_id,
            )
            .execute()
        )

    response = await run_sync(query)

    return response.data


# =========================================================
# КОЛИЧЕСТВО КОФЕ
# =========================================================

async def get_coffee_count(
    telegram_id: int,
):
    coffees = await get_all_coffees(
        telegram_id
    )

    return len(coffees)


# =========================================================
# СТАТИСТИКА
# =========================================================

async def get_statistics(
    telegram_id: int,
):
    coffees = await get_all_coffees(
        telegram_id
    )

    if not coffees:
        return {
            "total": 0,
            "average_rating": None,
            "favorite_coffee": None,
            "favorite_shop": None,
            "favorite_size": None,
            "shops_count": 0,
            "rated_count": 0,
        }

    total = len(coffees)

    # -----------------------------------------------------
    # ОЦЕНКИ
    # -----------------------------------------------------

    rated = [
        coffee
        for coffee in coffees
        if coffee.get("rating") is not None
    ]

    if rated:
        average_rating = round(
            sum(
                coffee["rating"]
                for coffee in rated
            ) / len(rated),
            1,
        )
    else:
        average_rating = None

    # -----------------------------------------------------
    # ЛЮБИМЫЙ КОФЕ
    # -----------------------------------------------------

    coffee_counts = {}

    for coffee in coffees:
        name = coffee["coffee_name"]

        coffee_counts[name] = (
            coffee_counts.get(name, 0) + 1
        )

    favorite_coffee = max(
        coffee_counts,
        key=coffee_counts.get,
    )

    # -----------------------------------------------------
    # ЛЮБИМАЯ КОФЕЙНЯ
    # -----------------------------------------------------

    shop_counts = {}

    for coffee in coffees:
        shop = coffee["coffee_shop"]

        shop_counts[shop] = (
            shop_counts.get(shop, 0) + 1
        )

    favorite_shop = max(
        shop_counts,
        key=shop_counts.get,
    )

    # -----------------------------------------------------
    # ЛЮБИМЫЙ РАЗМЕР
    # -----------------------------------------------------

    size_counts = {}

    for coffee in coffees:
        size = coffee["coffee_size"]

        size_counts[size] = (
            size_counts.get(size, 0) + 1
        )

    favorite_size = max(
        size_counts,
        key=size_counts.get,
    )

    # -----------------------------------------------------
    # КОЛИЧЕСТВО КОФЕЕН
    # -----------------------------------------------------

    shops_count = len(
        set(
            coffee["coffee_shop"]
            for coffee in coffees
        )
    )

    return {
        "total": total,
        "average_rating": average_rating,
        "favorite_coffee": favorite_coffee,
        "favorite_shop": favorite_shop,
        "favorite_size": favorite_size,
        "shops_count": shops_count,
        "rated_count": len(rated),
    }
