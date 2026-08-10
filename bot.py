import asyncio
import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    BufferedInputFile,
    InputMediaPhoto,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import BOT_TOKEN
from database import (
    add_coffee,
    get_today_coffees,
    get_all_coffees,
    get_statistics,
    delete_coffee,
)
from keyboards import (
    main_keyboard,
    coffee_size_keyboard,
    rating_keyboard,
    back_keyboard,
)
from states import AddCoffee


# =========================================================
# НАСТРОЙКИ
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()


# =========================================================
# ПУТИ К ФАЙЛАМ
# =========================================================

# Папка, в которой находится bot.py
BASE_DIR = Path(__file__).resolve().parent

# Папка assets рядом с bot.py
ASSETS_PATH = BASE_DIR / "assets"


# =========================================================
# КАРТИНКИ ПЕРСОНАЖА
# =========================================================

# ВАЖНО:
# Расширение .jpeg должно полностью совпадать
# с названиями файлов в GitHub.
#
# Также Linux на Render различает регистр букв.
#
# Например:
# Drinking.jpeg
# и
# drinking.jpeg
# это разные файлы.

CHARACTER_IMAGES = {
    "idle": ASSETS_PATH / "idle.jpeg",
    "sitting": ASSETS_PATH / "sitting.jpeg",
    "holding_coffee": ASSETS_PATH / "holding_coffee.jpeg",
    "drinking": ASSETS_PATH / "Drinking.jpeg",
    "happy": ASSETS_PATH / "Happy.jpeg",
    "surprised": ASSETS_PATH / "surprised.jpeg",
    "achievement": ASSETS_PATH / "achievment.jpeg",
}


# =========================================================
# ЗАГРУЗКА КАРТИНКИ
# =========================================================

def load_character_image(character: str) -> BufferedInputFile:
    """
    Загружает изображение персонажа из папки assets.

    Используем абсолютный путь через Path, чтобы
    корректно работало на Render.
    """

    image_path = CHARACTER_IMAGES.get(
        character,
        CHARACTER_IMAGES["idle"],
    )

    # Проверяем существование файла заранее.
    if not image_path.exists():
        logging.error(
            "Character image not found: %s",
            image_path,
        )

        raise FileNotFoundError(
            f"Character image not found: {image_path}"
        )

    # Читаем изображение в память.
    with image_path.open("rb") as file:
        image_bytes = file.read()

    return BufferedInputFile(
        image_bytes,
        filename=image_path.name,
    )


# =========================================================
# РЕДАКТИРОВАНИЕ ГЛАВНОГО ЭКРАНА
# =========================================================

async def edit_screen(
    message: Message,
    caption: str,
    keyboard=None,
    character: str = "idle",
):
    """
    Редактирует существующее сообщение.

    Если сообщение уже содержит фотографию —
    заменяем фотографию, текст и клавиатуру.

    Если фотографии нет —
    удаляем старое сообщение и создаём новое.
    """

    try:
        photo = load_character_image(character)

        # Если главное сообщение уже содержит фотографию,
        # просто заменяем фото + текст + клавиатуру.
        if message.photo:

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

        # На случай, если старое сообщение
        # оказалось не фотографией.

        await message.delete()

        new_message = await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

        return new_message

    except Exception as error:

        logging.exception(
            "Screen edit error: %s",
            error,
        )

        return message


# =========================================================
# ФОРМАТИРОВАНИЕ ДАТЫ
# =========================================================

def format_datetime(value: str) -> tuple[str, str]:

    dt = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

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

    date_text = f"{dt.day} {months[dt.month - 1]}"
    time_text = dt.strftime("%H:%M")

    return date_text, time_text


# =========================================================
# ГЛАВНЫЙ ЭКРАН
# =========================================================

async def show_main_screen(
    message: Message,
    telegram_id: int,
    state: FSMContext,
    character: str = "idle",
):

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
            f"<b>{last['coffee_name']}</b> · "
            f"{last['coffee_size']}\n"
            f"📍 {last['coffee_shop']} · "
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


# =========================================================
# START
# =========================================================

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
            f"<b>{last['coffee_name']}</b> · "
            f"{last['coffee_size']}\n"
            f"📍 {last['coffee_shop']} · "
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

    photo = load_character_image("idle")

    sent_message = await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.HTML,
    )

    await state.update_data(
        main_message_id=sent_message.message_id
    )


# =========================================================
# НАЗАД
# =========================================================

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


# =========================================================
# ДОБАВИТЬ КОФЕ
# =========================================================

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
        "<i>Например: капучино, "
        "флэт уайт, эспрессо</i>"
    )

    await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="holding_coffee",
    )


# =========================================================
# НАЗВАНИЕ КОФЕ
# =========================================================

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

    # Удаляем сообщение пользователя
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

        logging.exception(
            "Coffee name screen error: %s",
            error,
        )


# =========================================================
# РАЗМЕР
# =========================================================

@dp.callback_query(
    F.data.startswith("size:")
)
async def coffee_size_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    size = callback.data.split(":")[1]

    await state.update_data(
        coffee_size=size
    )

    await state.set_state(
        AddCoffee.coffee_shop
    )

    await callback.answer()

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

    await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="drinking",
    )


# =========================================================
# КОФЕЙНЯ
# =========================================================

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

        logging.exception(
            "Coffee shop screen error: %s",
            error,
        )


# =========================================================
# ОЦЕНКА
# =========================================================

@dp.callback_query(
    F.data.startswith("rating:")
)
async def rating_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    value = callback.data.split(":")[1]

    if value == "none":
        rating = None
    else:
        rating = int(value)

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

    await add_coffee(
        telegram_id=callback.from_user.id,
        coffee_name=coffee_name,
        coffee_size=coffee_size,
        coffee_shop=coffee_shop,
        rating=rating,
    )

    await callback.answer(
        "Кофе записан ☕️"
    )

    if rating:

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

    await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=main_keyboard(),
        character="happy",
    )

    await state.clear()

    await state.update_data(
        main_message_id=callback.message.message_id
    )


# =========================================================
# СТАТИСТИКА
# =========================================================

@dp.callback_query(
    F.data == "statistics"
)
async def statistics_handler(
    callback: CallbackQuery,
):

    await callback.answer()

    stats = await get_statistics(
        callback.from_user.id
    )

    if stats["total"] == 0:

        caption = (
            "📊 <b>Статистика</b>\n\n"
            "Пока здесь пусто.\n\n"
            "Добавь первый кофе ☕️"
        )

    else:

        if stats["average_rating"] is not None:

            average_rating = (
                f"⭐️ {stats['average_rating']}/5"
            )

        else:

            average_rating = (
                "⭐️ Нет оценок"
            )

        caption = (
            "📊 <b>Статистика</b>\n\n"
            f"☕️ Всего кофе — "
            f"<b>{stats['total']}</b>\n\n"
            f"☕ Любимый кофе\n"
            f"<b>{stats['favorite_coffee']}</b>\n\n"
            f"🏪 Любимая кофейня\n"
            f"<b>{stats['favorite_shop']}</b>\n\n"
            f"📏 Любимый размер\n"
            f"<b>{stats['favorite_size']}</b>\n\n"
            f"🏪 Кофеен посещено — "
            f"<b>{stats['shops_count']}</b>\n\n"
            f"{average_rating}"
        )

    await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="sitting",
    )


# =========================================================
# ИСТОРИЯ
# =========================================================

async def render_history(
    message: Message,
    telegram_id: int,
):

    coffees = await get_all_coffees(
        telegram_id
    )

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
            coffee["created_at"]
        )

        if date_text != current_date:

            if current_date is not None:
                lines.append("")

            lines.append(
                f"<b>{date_text}</b>"
            )

            current_date = date_text

        rating = coffee.get("rating")

        if rating:
            rating_text = f" · ⭐️ {rating}"
        else:
            rating_text = ""

        lines.append(
            f"{time_text} · "
            f"<b>{coffee['coffee_name']}</b> · "
            f"{coffee['coffee_size']}"
        )

        lines.append(
            f"📍 {coffee['coffee_shop']}"
            f"{rating_text}"
        )

    caption = "\n".join(lines)

    buttons = []

    for coffee in coffees:

        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"🗑 {coffee['coffee_name']} "
                    f"· {coffee['coffee_size']}"
                ),
                callback_data=(
                    f"delete:{coffee['id']}"
                ),
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="← Назад",
            callback_data="back_main",
        )
    ])

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


# =========================================================
# УДАЛЕНИЕ
# =========================================================

@dp.callback_query(
    F.data.startswith("delete:")
)
async def delete_handler(
    callback: CallbackQuery,
):

    coffee_id = int(
        callback.data.split(":")[1]
    )

    await delete_coffee(
        telegram_id=callback.from_user.id,
        coffee_id=coffee_id,
    )

    await callback.answer(
        "Запись удалена 🗑"
    )

    await render_history(
        message=callback.message,
        telegram_id=callback.from_user.id,
    )


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logging.info(
        "☕ Coffee Diary bot started"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
