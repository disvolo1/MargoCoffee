import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    FSInputFile,
    InputMediaPhoto,
)

from config import BOT_TOKEN
from database import (
    add_coffee,
    get_today_coffees,
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

ASSETS_PATH = "assets"

CHARACTER_IMAGES = {
    "idle": f"{ASSETS_PATH}/idle.png",
    "sitting": f"{ASSETS_PATH}/sitting.png",
    "holding_coffee": f"{ASSETS_PATH}/holding_coffee.png",
    "drinking": f"{ASSETS_PATH}/Drinking.png",
    "happy": f"{ASSETS_PATH}/Happy.png",
    "surprised": f"{ASSETS_PATH}/surprised.png",
    "achievement": f"{ASSETS_PATH}/achievment.png",
}


# =========================================================
# РАБОТА С ГЛАВНЫМ СООБЩЕНИЕМ
# =========================================================

async def edit_screen(
    message: Message,
    caption: str,
    keyboard=None,
    character: str = "idle",
):
    """
    Редактирует существующее сообщение бота.

    Если это сообщение с фотографией —
    меняем фотографию + caption.

    Если это обычное сообщение —
    заменяем его на фотографию.
    """

    image_path = CHARACTER_IMAGES.get(
        character,
        CHARACTER_IMAGES["idle"],
    )

    try:
        photo = FSInputFile(image_path)

        # Уже есть фото
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

        else:
            # Теоретически сюда попадать не должны,
            # потому что главный экран всегда фото.
            await message.delete()

            new_message = await message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )

            return new_message

    except Exception as error:
        logging.error(
            "Error editing screen: %s",
            error,
        )

    return message


# =========================================================
# ПОЛУЧЕНИЕ ID ГЛАВНОГО СООБЩЕНИЯ
# =========================================================

async def get_main_message_id(
    state: FSMContext,
):
    data = await state.get_data()

    return data.get("main_message_id")


# =========================================================
# ГЛАВНЫЙ ЭКРАН
# =========================================================

async def show_main_screen(
    message: Message,
    telegram_id: int,
    state: FSMContext,
    character: str = "idle",
):
    coffees = get_today_coffees(
        telegram_id
    )

    count = len(coffees)

    if coffees:
        last = coffees[0]

        created_at = datetime.fromisoformat(
            last["created_at"].replace(
                "Z",
                "+00:00",
            )
        )

        time_text = created_at.strftime(
            "%H:%M"
        )

        last_coffee = (
            f"<b>{last['coffee_name']}</b> · "
            f"{last['coffee_size']}\n"
            f"📍 {last['coffee_shop']} · {time_text}"
        )

    else:
        last_coffee = (
            "Сегодня кофе ещё не было."
        )

    caption = (
        "☕️ <b>Coffee Diary</b>\n\n"
        f"Сегодня — <b>{count}</b>\n\n"
        f"Последний кофе:\n"
        f"{last_coffee}\n\n"
        "Что будем делать?"
    )

    result = await edit_screen(
        message=message,
        caption=caption,
        keyboard=main_keyboard(),
        character=character,
    )

    # Если edit_screen создал новое сообщение,
    # сохраняем его ID.
    if result:
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

    coffees = get_today_coffees(
        telegram_id
    )

    count = len(coffees)

    if coffees:
        last = coffees[0]

        created_at = datetime.fromisoformat(
            last["created_at"].replace(
                "Z",
                "+00:00",
            )
        )

        time_text = created_at.strftime(
            "%H:%M"
        )

        last_coffee = (
            f"<b>{last['coffee_name']}</b> · "
            f"{last['coffee_size']}\n"
            f"📍 {last['coffee_shop']} · {time_text}"
        )

    else:
        last_coffee = (
            "Сегодня кофе ещё не было."
        )

    caption = (
        "☕️ <b>Coffee Diary</b>\n\n"
        f"Сегодня — <b>{count}</b>\n\n"
        f"Последний кофе:\n"
        f"{last_coffee}\n\n"
        "Добро пожаловать."
    )

    sent_message = await message.answer_photo(
        photo=FSInputFile(
            CHARACTER_IMAGES["idle"]
        ),
        caption=caption,
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.HTML,
    )

    # Запоминаем главное сообщение
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

    # Сохраняем ID главного сообщения
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

    main_message_id = (
        await get_main_message_id(state)
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
        logging.error(
            "Error after coffee name: %s",
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

    main_message_id = (
        await get_main_message_id(state)
    )

    if not main_message_id:
        return

    data = await state.get_data()

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
        logging.error(
            "Error after coffee shop: %s",
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

    # Сохраняем кофе
    add_coffee(
        telegram_id=callback.from_user.id,
        coffee_name=coffee_name,
        coffee_size=coffee_size,
        coffee_shop=coffee_shop,
        rating=rating,
    )

    await state.clear()

    # Возвращаем ID главного сообщения
    await state.update_data(
        main_message_id=callback.message.message_id
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


# =========================================================
# СТАТИСТИКА — ПОКА ЗАГЛУШКА
# =========================================================

@dp.callback_query(
    F.data == "statistics"
)
async def statistics_handler(
    callback: CallbackQuery,
):
    await callback.answer()

    caption = (
        "📊 <b>Статистика</b>\n\n"
        "Сейчас собираем твою кофейную историю.\n\n"
        "Здесь появятся:\n"
        "☕ количество кофе\n"
        "🏪 любимые кофейни\n"
        "⭐ средняя оценка\n"
        "📏 любимый размер\n"
        "☕ любимый напиток"
    )

    await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="sitting",
    )


# =========================================================
# ИСТОРИЯ — ПОКА ЗАГЛУШКА
# =========================================================

@dp.callback_query(
    F.data == "history"
)
async def history_handler(
    callback: CallbackQuery,
):
    await callback.answer()

    caption = (
        "📖 <b>История</b>\n\n"
        "История кофе появится здесь."
    )

    await edit_screen(
        message=callback.message,
        caption=caption,
        keyboard=back_keyboard(),
        character="sitting",
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
