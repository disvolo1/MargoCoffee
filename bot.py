import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from aiohttp import web
from PIL import Image

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from config import BOT_TOKEN
from database import (
    add_coffee,
    delete_coffee,
    get_all_coffees,
    get_statistics,
    get_today_coffees,
)
from keyboards import (
    back_keyboard,
    coffee_size_keyboard,
    main_keyboard,
    rating_keyboard,
)
from states import AddCoffee


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set. "
        "Add BOT_TOKEN to Render Environment Variables."
    )


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()


# ============================================================
# LOCKS
# ============================================================

SCREEN_LOCKS = defaultdict(asyncio.Lock)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ASSETS_PATH = BASE_DIR / "assets"


# ============================================================
# CHARACTER IMAGES
# ============================================================

CHARACTER_IMAGES = {
    "idle": ASSETS_PATH / "idle.jpeg",
    "sitting": ASSETS_PATH / "sitting.jpeg",
    "holding_coffee": ASSETS_PATH / "holding_coffee.jpeg",
    "drinking": ASSETS_PATH / "Drinking.jpeg",
    "happy": ASSETS_PATH / "Happy.jpeg",
    "surprised": ASSETS_PATH / "surprised.jpeg",
    "achievement": ASSETS_PATH / "achievment.jpeg",
}


# ============================================================
# IMAGE LOADER
# ============================================================

def load_character_image(character: str = "idle") -> BufferedInputFile:
    """
    Загружает изображение персонажа и пересохраняет его
    в нормальный RGB JPEG.

    Это помогает избежать Telegram IMAGE_PROCESS_FAILED.
    """

    image_path = CHARACTER_IMAGES.get(
        character,
        CHARACTER_IMAGES["idle"],
    )

    if not image_path.exists():
        logger.error(
            "Character image not found: %s",
            image_path,
        )

        raise FileNotFoundError(
            f"Character image not found: {image_path}"
        )

    try:
        with Image.open(image_path) as image:

            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")

            if image.mode == "RGBA":

                background = Image.new(
                    "RGB",
                    image.size,
                    "white",
                )

                background.paste(
                    image,
                    mask=image.getchannel("A"),
                )

                image = background

            else:
                image = image.convert("RGB")

            output = BytesIO()

            image.save(
                output,
                format="JPEG",
                quality=95,
                optimize=True,
            )

            output.seek(0)

            return BufferedInputFile(
                output.read(),
                filename=f"{character}.jpg",
            )

    except Exception:

        logger.exception(
            "Failed to process image: %s",
            image_path,
        )

        with image_path.open("rb") as file:

            return BufferedInputFile(
                file.read(),
                filename=image_path.name,
            )


# ============================================================
# SAFE TELEGRAM TEXT
# ============================================================

def safe_text(value) -> str:
    """
    Безопасное преобразование значения в строку.
    """

    if value is None:
        return ""

    return str(value)


# ============================================================
# DATE
# ============================================================

def parse_datetime(value: str) -> datetime:
    """
    Парсит дату из Supabase/ISO.

    Если timezone отсутствует — считаем UTC.
    """

    if not value:
        return datetime.now(timezone.utc)

    value = str(value)

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    except ValueError:

        logger.warning(
            "Could not parse datetime: %s",
            value,
        )

        return datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt


def format_datetime(value: str) -> tuple[str, str]:

    dt = parse_datetime(value)

    months = [
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]

    date_text = (
        f"{dt.day} "
        f"{months[dt.month - 1]}"
    )

    time_text = dt.strftime("%H:%M")

    return date_text, time_text


# ============================================================
# EDIT SCREEN
# ============================================================

async def edit_screen(
    message: Message,
    caption: str,
    keyboard=None,
    character: str = "idle",
):
    """
    Универсальное обновление главного экрана.

    Если сообщение содержит фото:
        пытаемся заменить фото + caption.

    Если Telegram не принимает новую картинку:
        меняем только caption.

    Если сообщение не содержит фото:
        удаляем его и создаём новое фото.

    Если фото вообще не удалось отправить:
        создаём обычное текстовое сообщение.
    """

    lock = SCREEN_LOCKS[
        (
            message.chat.id,
            message.message_id,
        )
    ]

    async with lock:

        photo = None

        try:
            photo = load_character_image(
                character
            )

        except Exception:

            logger.exception(
                "Could not load character: %s",
                character,
            )

        # ----------------------------------------------------
        # EXISTING PHOTO MESSAGE
        # ----------------------------------------------------

        if message.photo:

            if photo is not None:

                try:

                    media = InputMediaPhoto(
                        media=photo,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )

                    await message.edit_media(
                        media=media,
                        reply_markup=keyboard,
                    )

                    return message

                except Exception as error:

                    error_text = str(error)

                    if (
                        "message is not modified"
                        in error_text.lower()
                    ):
                        return message

                    logger.warning(
                        "edit_media failed: %s",
                        error,
                    )

            # ------------------------------------------------
            # FALLBACK: EDIT CAPTION ONLY
            # ------------------------------------------------

            try:

                await message.edit_caption(
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                )

                return message

            except Exception as error:

                if (
                    "message is not modified"
                    not in str(error).lower()
                ):

                    logger.warning(
                        "edit_caption failed: %s",
                        error,
                    )

                return message

        # ----------------------------------------------------
        # MESSAGE WITHOUT PHOTO
        # ----------------------------------------------------

        try:
            await message.delete()

        except Exception:
            pass

        # ----------------------------------------------------
        # CREATE PHOTO
        # ----------------------------------------------------

        if photo is not None:

            try:

                new_message = (
                    await message.answer_photo(
                        photo=photo,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML,
                    )
                )

                return new_message

            except Exception as error:

                logger.warning(
                    "answer_photo failed: %s",
                    error,
                )

        # ----------------------------------------------------
        # FINAL FALLBACK: TEXT
        # ----------------------------------------------------

        return await message.answer(
            caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )


# ============================================================
# MAIN SCREEN
# ============================================================

async def show_main_screen(
    message: Message,
    telegram_id: int,
    state: FSMContext,
    character: str = "idle",
):
    """
    Показывает главный экран.
    """

    coffees = await get_today_coffees(
        telegram_id
    )

    count = len(coffees)

    if coffees:

        last = coffees[0]

        _, time_text = format_datetime(
            last["created_at"]
        )

        coffee_name = safe_text(
            last.get("coffee_name")
        )

        coffee_size = safe_text(
            last.get("coffee_size")
        )

        coffee_shop = safe_text(
            last.get("coffee_shop")
        )

        last_coffee = (
            f"<b>{coffee_name}</b> · "
            f"{coffee_size}\n"
            f"📍 {coffee_shop} · "
            f"{time_text}"
        )

    else:

        last_coffee = (
            "Сегодня кофе ещё не было."
        )

    caption = (
        "☕️ <b>Coffee Diary</b>\n\n"
        f"Сегодня — <b>{count}</b>\n\n"
        "Последний кофе:\n"
        f"{last_coffee}\n\n"
        "Что будем делать?"
    )

    result = await edit_screen(
        message=message,
        caption=caption,
        keyboard=main_keyboard(),
        character=character,
    )

    await state.update_data(
        main_message_id=result.message_id
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    telegram_id = message.from_user.id

    coffees = await get_today_coffees(
        telegram_id
    )

    count = len(coffees)

    if coffees:

        last = coffees[0]

        _, time_text = format_datetime(
            last["created_at"]
        )

        last_coffee = (
            f"<b>{safe_text(last.get('coffee_name'))}</b> · "
            f"{safe_text(last.get('coffee_size'))}\n"
            f"📍 {safe_text(last.get('coffee_shop'))} · "
            f"{time_text}"
        )

    else:

        last_coffee = (
            "Сегодня кофе ещё не было."
        )

    caption = (
        "☕️ <b>Coffee Diary</b>\n\n"
        f"Сегодня — <b>{count}</b>\n\n"
        "Последний кофе:\n"
        f"{last_coffee}\n\n"
        "Добро пожаловать."
    )

    try:

        photo = load_character_image(
            "idle"
        )

        sent_message = (
            await message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=main_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        )

    except Exception:

        logger.exception(
            "Could not send start photo"
        )

        sent_message = await message.answer(
            caption,
            reply_markup=main_keyboard(),
            parse_mode=ParseMode.HTML,
        )

    await state.update_data(
        main_message_id=sent_message.message_id
    )


# ============================================================
# BACK
# ============================================================

@dp.callback_query(
    F.data == "back_main"
)
async def back_main_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    await state.clear()

    await show_main_screen(
        message=callback.message,
        telegram_id=callback.from_user.id,
        state=state,
        character="idle",
    )


# ============================================================
# ADD COFFEE
# ============================================================

@dp.callback_query(
    F.data == "add_coffee"
)
async def add_coffee_start(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    await state.update_data(
        main_message_id=callback.message.message_id
    )

    await state.set_state(
        AddCoffee.coffee_name
    )

    caption = (
        "☕️ <b>Добавляем кофе</b>\n\n"
        "Как называется кофе?\n\n"
        "<i>Можно написать любое название</i>"
    )

    result = await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="holding_coffee",
    )

    await state.update_data(
        main_message_id=result.message_id
    )


# ============================================================
# COFFEE NAME
# ============================================================

@dp.message(
    AddCoffee.coffee_name
)
async def coffee_name_handler(
    message: Message,
    state: FSMContext,
):

    if not message.text:
        return

    coffee_name = message.text.strip()

    if not coffee_name:
        return

    await state.update_data(
        coffee_name=coffee_name
    )

    await state.set_state(
        AddCoffee.coffee_size
    )

    try:
        await message.delete()

    except Exception:
        pass

    data = await state.get_data()

    main_message_id = data.get(
        "main_message_id"
    )

    if not main_message_id:
        return

    caption = (
        f"☕️ <b>{coffee_name}</b>\n\n"
        "Какой размер?"
    )

    try:

        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=main_message_id,
            caption=caption,
            reply_markup=coffee_size_keyboard(),
            parse_mode=ParseMode.HTML,
        )

    except Exception as error:

        logger.exception(
            "Coffee name screen error: %s",
            error,
        )


# ============================================================
# SIZE
# ============================================================

@dp.callback_query(
    F.data.startswith("size:")
)
async def coffee_size_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    size = callback.data.split(
        ":",
        1,
    )[1]

    await state.update_data(
        coffee_size=size
    )

    await state.set_state(
        AddCoffee.coffee_shop
    )

    data = await state.get_data()

    coffee_name = data.get(
        "coffee_name",
        "Кофе",
    )

    caption = (
        f"☕️ <b>{coffee_name} · {size}</b>\n\n"
        "В какой кофейне ты его пил?\n\n"
        "<i>Напиши название кофейни</i>"
    )

    result = await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="drinking",
    )

    await state.update_data(
        main_message_id=result.message_id
    )


# ============================================================
# COFFEE SHOP
# ============================================================

@dp.message(
    AddCoffee.coffee_shop
)
async def coffee_shop_handler(
    message: Message,
    state: FSMContext,
):

    if not message.text:
        return

    coffee_shop = message.text.strip()

    if not coffee_shop:
        return

    await state.update_data(
        coffee_shop=coffee_shop
    )

    await state.set_state(
        AddCoffee.rating
    )

    try:
        await message.delete()

    except Exception:
        pass

    data = await state.get_data()

    main_message_id = data.get(
        "main_message_id"
    )

    if not main_message_id:
        return

    coffee_name = data.get(
        "coffee_name",
        "Кофе",
    )

    coffee_size = data.get(
        "coffee_size",
        "M",
    )

    caption = (
        f"☕️ <b>{coffee_name} · {coffee_size}</b>\n"
        f"📍 {coffee_shop}\n\n"
        "Как оценишь кофе?"
    )

    try:

        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=main_message_id,
            caption=caption,
            reply_markup=rating_keyboard(),
            parse_mode=ParseMode.HTML,
        )

    except Exception as error:

        logger.exception(
            "Coffee shop screen error: %s",
            error,
        )


# ============================================================
# RATING
# ============================================================

@dp.callback_query(
    F.data.startswith("rating:")
)
async def rating_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    value = callback.data.split(
        ":",
        1,
    )[1]

    if value == "none":
        rating = None
    else:

        try:
            rating = int(value)

        except ValueError:

            await callback.answer(
                "Некорректная оценка.",
                show_alert=True,
            )

            return

    data = await state.get_data()

    coffee_name = data.get(
        "coffee_name"
    )

    coffee_size = data.get(
        "coffee_size"
    )

    coffee_shop = data.get(
        "coffee_shop"
    )

    if not coffee_name:

        await callback.answer(
            "Не найдено название кофе.",
            show_alert=True,
        )

        return

    if not coffee_size:

        await callback.answer(
            "Не найден размер.",
            show_alert=True,
        )

        return

    if not coffee_shop:

        await callback.answer(
            "Не найдена кофейня.",
            show_alert=True,
        )

        return

    try:

        await add_coffee(
            telegram_id=callback.from_user.id,
            coffee_name=coffee_name,
            coffee_size=coffee_size,
            coffee_shop=coffee_shop,
            rating=rating,
        )

    except Exception:

        logger.exception(
            "Failed to save coffee"
        )

        await callback.answer(
            "Не удалось сохранить кофе.",
            show_alert=True,
        )

        return

    if rating is not None:

        rating_text = (
            f"⭐️ {rating}/5"
        )

    else:

        rating_text = (
            "Без оценки"
        )

    caption = (
        "☕️ <b>Кофе записан</b>\n\n"
        f"<b>{coffee_name}</b> · "
        f"{coffee_size}\n"
        f"📍 {coffee_shop}\n"
        f"{rating_text}"
    )

    result = await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=main_keyboard(),
        character="happy",
    )

    await state.clear()

    await state.update_data(
        main_message_id=result.message_id
    )


# ============================================================
# STATISTICS
# ============================================================

@dp.callback_query(
    F.data == "statistics"
)
async def statistics_handler(
    callback: CallbackQuery,
):

    await callback.answer()

    try:

        stats = await get_statistics(
            callback.from_user.id
        )

    except Exception:

        logger.exception(
            "Statistics error"
        )

        await callback.answer(
            "Не удалось загрузить статистику.",
            show_alert=True,
        )

        return

    if not stats or stats["total"] == 0:

        caption = (
            "📊 <b>Статистика</b>\n\n"
            "Пока здесь пусто.\n\n"
            "Добавь первый кофе ☕️"
        )

    else:

        average_rating = stats.get(
            "average_rating"
        )

        if average_rating is not None:

            average_rating_text = (
                f"⭐️ {average_rating}/5"
            )

        else:

            average_rating_text = (
                "⭐️ Нет оценок"
            )

        caption = (
            "📊 <b>Статистика</b>\n\n"
            f"☕️ Всего кофе — "
            f"<b>{stats.get('total', 0)}</b>\n\n"
            f"☕ Любимый кофе\n"
            f"<b>{safe_text(stats.get('favorite_coffee'))}</b>\n\n"
            f"🏪 Любимая кофейня\n"
            f"<b>{safe_text(stats.get('favorite_shop'))}</b>\n\n"
            f"📏 Любимый размер\n"
            f"<b>{safe_text(stats.get('favorite_size'))}</b>\n\n"
            f"🏪 Кофеен посещено — "
            f"<b>{stats.get('shops_count', 0)}</b>\n\n"
            f"{average_rating_text}"
        )

    await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="sitting",
    )


# ============================================================
# HISTORY
# ============================================================

async def render_history(
    message: Message,
    telegram_id: int,
):

    try:

        coffees = await get_all_coffees(
            telegram_id
        )

    except Exception:

        logger.exception(
            "History loading error"
        )

        await message.answer(
            "Не удалось загрузить историю."
        )

        return

    if not coffees:

        caption = (
            "📖 <b>История</b>\n\n"
            "Здесь пока ничего нет.\n\n"
            "Добавь свой первый кофе ☕️"
        )

        await edit_screen(
            message=message,
            caption=caption,
            keyboard=back_keyboard(),
            character="sitting",
        )

        return

    coffees = coffees[:10]

    lines = [
        "📖 <b>История</b>",
        "",
    ]

    current_date = None

    for coffee in coffees:

        date_text, time_text = format_datetime(
            coffee.get("created_at")
        )

        if date_text != current_date:

            if current_date is not None:
                lines.append("")

            lines.append(
                f"<b>{date_text}</b>"
            )

            current_date = date_text

        rating = coffee.get(
            "rating"
        )

        if rating is not None:

            rating_text = (
                f" · ⭐️ {rating}"
            )

        else:

            rating_text = ""

        lines.append(
            f"{time_text} · "
            f"<b>{safe_text(coffee.get('coffee_name'))}</b> · "
            f"{safe_text(coffee.get('coffee_size'))}"
        )

        lines.append(
            f"📍 {safe_text(coffee.get('coffee_shop'))}"
            f"{rating_text}"
        )

    caption = "\n".join(lines)

    buttons = []

    for coffee in coffees:

        coffee_id = coffee.get(
            "id"
        )

        if coffee_id is None:
            continue

        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"🗑 "
                        f"{safe_text(coffee.get('coffee_name'))} "
                        f"· "
                        f"{safe_text(coffee.get('coffee_size'))}"
                    ),
                    callback_data=(
                        f"delete:{coffee_id}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="← Назад",
                callback_data="back_main",
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await edit_screen(
        message=message,
        caption=caption,
        keyboard=keyboard,
        character="sitting",
    )


@dp.callback_query(
    F.data == "history"
)
async def history_handler(
    callback: CallbackQuery,
):

    await callback.answer()

    await render_history(
        message=callback.message,
        telegram_id=callback.from_user.id,
    )


# ============================================================
# DELETE
# ============================================================

@dp.callback_query(
    F.data.startswith("delete:")
)
async def delete_handler(
    callback: CallbackQuery,
):

    try:

        coffee_id = int(
            callback.data.split(
                ":",
                1,
            )[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Некорректная запись.",
            show_alert=True,
        )

        return

    try:

        await delete_coffee(
            telegram_id=callback.from_user.id,
            coffee_id=coffee_id,
        )

    except Exception:

        logger.exception(
            "Delete coffee error"
        )

        await callback.answer(
            "Не удалось удалить запись.",
            show_alert=True,
        )

        return

    await callback.answer(
        "Запись удалена 🗑"
    )

    await render_history(
        message=callback.message,
        telegram_id=callback.from_user.id,
    )


# ============================================================
# ERROR HANDLER
# ============================================================

@dp.errors()
async def global_error_handler(
    event,
):
    """
    Логируем необработанные ошибки,
    чтобы Render не терял причину сбоя.
    """

    logger.exception(
        "Unhandled dispatcher error: %s",
        event.exception,
    )


# ============================================================
# HTTP HEALTH SERVER
# ============================================================

async def health_handler(
    request: web.Request,
):

    return web.Response(
        text="Coffee Diary bot is running ☕️",
        status=200,
    )


async def start_web_server():

    port = int(
        os.getenv(
            "PORT",
            "8080",
        )
    )

    app = web.Application()

    app.router.add_get(
        "/",
        health_handler,
    )

    app.router.add_get(
        "/health",
        health_handler,
    )

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=port,
    )

    await site.start()

    logger.info(
        "HTTP health server started on port %s",
        port,
    )

    return runner


# ============================================================
# TELEGRAM POLLING
# ============================================================

async def start_bot():

    """
    Запускает polling.

    Важно:
    Unauthorized НЕ пытаемся бесконечно лечить перезапуском.
    Если токен отозван/неверный — Render должен показать
    понятную ошибку.
    """

    try:

        me = await bot.get_me()

        logger.info(
            "Telegram bot connected: @%s (id=%s)",
            me.username,
            me.id,
        )

    except Exception:

        logger.exception(
            "❌ Telegram authentication failed. "
            "Check BOT_TOKEN in Render Environment Variables."
        )

        raise

    logger.info(
        "🚀 Start polling"
    )

    await dp.start_polling(
        bot,
        handle_signals=True,
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    logger.info(
        "☕ Coffee Diary bot starting..."
    )

    web_runner = None

    try:

        web_runner = await start_web_server()

        await start_bot()

    except Exception:

        logger.exception(
            "❌ Bot stopped because of an error."
        )

        raise

    finally:

        if web_runner is not None:

            logger.info(
                "Stopping HTTP health server..."
            )

            try:
                await web_runner.cleanup()

            except Exception:

                logger.exception(
                    "Failed to cleanup HTTP server"
                )

        logger.info(
            "Closing Telegram bot session..."
        )

        try:
            await bot.session.close()

        except Exception:

            logger.exception(
                "Failed to close Telegram session"
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped manually."
        )

    except Exception:

        logger.exception(
            "Fatal bot error."
        )
