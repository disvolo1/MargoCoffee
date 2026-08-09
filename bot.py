import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile

from config import BOT_TOKEN
from database import add_coffee, get_today_coffees
from keyboards import (
    main_keyboard,
    coffee_size_keyboard,
    rating_keyboard,
    back_keyboard,
)
from states import AddCoffee


logging.basicConfig(level=logging.INFO)


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# ---------------------------------------------------------
# НАСТРОЙКИ
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------------------------------------

async def send_or_edit_character(
    message: Message,
    text: str,
    keyboard=None,
    state: str = "idle",
):
    """
    Пока используем отдельное фото + текст.
    Позже сделаем полноценное редактирование media,
    чтобы персонаж менялся в том же сообщении.
    """

    image_path = CHARACTER_IMAGES.get(state)

    if not image_path:
        await message.edit_text(
            text,
            reply_markup=keyboard
        )
        return

    try:
        photo = FSInputFile(image_path)

        # Если сообщение уже является фото,
        # редактируем caption.
        if message.photo:
            from aiogram.types import InputMediaPhoto

            media = InputMediaPhoto(
                media=photo,
                caption=text,
                parse_mode=ParseMode.HTML
            )

            await message.edit_media(
                media=media,
                reply_markup=keyboard
            )

        else:
            # Если это обычное текстовое сообщение,
            # заменяем его фото.
            await message.delete()

            await message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )

    except Exception as error:
        logging.error(
            "Character update error: %s",
            error
        )

        try:
            await message.edit_text(
                text,
                reply_markup=keyboard
            )
        except Exception:
            pass


async def show_main(
    message: Message,
    telegram_id: int,
    state: str = "idle",
):
    coffees = get_today_coffees(telegram_id)

    count = len(coffees)

    if coffees:
        last = coffees[0]

        last_time = datetime.fromisoformat(
            last["created_at"].replace("Z", "+00:00")
        ).strftime("%H:%M")

        last_coffee = (
            f"<b>{last['coffee_name']}</b> · "
            f"{last['coffee_size']}\n"
            f"📍 {last['coffee_shop']} · {last_time}"
        )
    else:
        last_coffee = "Сегодня кофе ещё не было."

    text = (
        "☕️ <b>Coffee Diary</b>\n\n"
        f"Сегодня — <b>{count}</b>\n\n"
        f"Последний кофе:\n{last_coffee}\n\n"
        "Что будем делать?"
    )

    await send_or_edit_character(
        message=message,
        text=text,
        keyboard=main_keyboard(),
        state=state,
    )


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    coffees = get_today_coffees(
        message.from_user.id
    )

    count = len(coffees)

    if coffees:
        last = coffees[0]

        last_time = datetime.fromisoformat(
            last["created_at"].replace("Z", "+00:00")
        ).strftime("%H:%M")

        last_coffee = (
            f"<b>{last['coffee_name']}</b> · "
            f"{last['coffee_size']}\n"
            f"📍 {last['coffee_shop']} · {last_time}"
        )
    else:
        last_coffee = "Сегодня кофе ещё не было."

    text = (
        "☕️ <b>Coffee Diary</b>\n\n"
        f"Сегодня — <b>{count}</b>\n\n"
        f"Последний кофе:\n{last_coffee}\n\n"
        "Добро пожаловать."
    )

    await message.answer_photo(
        photo=FSInputFile(
            CHARACTER_IMAGES["idle"]
        ),
        caption=text,
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------
# НАЗАД НА ГЛАВНУЮ
# ---------------------------------------------------------

@dp.callback_query(F.data == "back_main")
async def back_main_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    await callback.answer()

    await show_main(
        callback.message,
        callback.from_user.id,
        state="idle",
    )


# ---------------------------------------------------------
# ДОБАВЛЕНИЕ КОФЕ
# ---------------------------------------------------------

@dp.callback_query(F.data == "add_coffee")
async def add_coffee_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    await callback.answer()

    await state.set_state(
        AddCoffee.coffee_name
    )

    text = (
        "☕️ <b>Добавляем кофе</b>\n\n"
        "Как называется кофе?\n\n"
        "<i>Например: капучино, флэт уайт, эспрессо</i>"
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------
# НАЗВАНИЕ КОФЕ
# ---------------------------------------------------------

@dp.message(AddCoffee.coffee_name)
async def coffee_name_handler(
    message: Message,
    state: FSMContext,
):
    coffee_name = message.text.strip()

    if not coffee_name:
        return

    await state.update_data(
        coffee_name=coffee_name
    )

    await state.set_state(
        AddCoffee.coffee_size
    )

    # Удаляем пользовательское сообщение,
    # чтобы чат оставался чистым.
    try:
        await message.delete()
    except Exception:
        pass

    # Находим последнее сообщение бота
    # через сохранённый message_id.
    data = await state.get_data()

    message_id = data.get(
        "main_message_id"
    )

    if message_id:
        try:
            await bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message_id,
                caption=(
                    f"☕️ <b>{coffee_name}</b>\n\n"
                    "Какой размер?"
                ),
                reply_markup=coffee_size_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as error:
            logging.error(error)


# ---------------------------------------------------------
# РАЗМЕР
# ---------------------------------------------------------

@dp.callback_query(F.data.startswith("size:"))
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
        "Кофе"
    )

    text = (
        f"☕️ <b>{coffee_name} · {size}</b>\n\n"
        "В какой кофейне ты его пил?\n\n"
        "<i>Напиши название кофейни</i>"
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------
# КОФЕЙНЯ
# ---------------------------------------------------------

@dp.message(AddCoffee.coffee_shop)
async def coffee_shop_handler(
    message: Message,
    state: FSMContext,
):
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

    coffee_name = data.get(
        "coffee_name",
        "Кофе"
    )

    coffee_size = data.get(
        "coffee_size",
        "M"
    )

    message_id = data.get(
        "main_message_id"
    )

    if message_id:
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=message_id,
            caption=(
                f"☕️ <b>{coffee_name} · {coffee_size}</b>\n"
                f"📍 {coffee_shop}\n\n"
                "Как оценишь кофе?"
            ),
            reply_markup=rating_keyboard(),
            parse_mode=ParseMode.HTML,
        )


# ---------------------------------------------------------
# ОЦЕНКА
# ---------------------------------------------------------

@dp.callback_query(F.data.startswith("rating:"))
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

    if not coffee_name or not coffee_size or not coffee_shop:
        await callback.answer(
            "Не хватает данных.",
            show_alert=True
        )
        return

    add_coffee(
        telegram_id=callback.from_user.id,
        coffee_name=coffee_name,
        coffee_size=coffee_size,
        coffee_shop=coffee_shop,
        rating=rating,
    )

    await state.clear()

    await callback.answer(
        "Кофе записан ☕️"
    )

    rating_text = (
        f"⭐️ {rating}/5"
        if rating
        else "Без оценки"
    )

    text = (
        "☕️ <b>Кофе записан</b>\n\n"
        f"<b>{coffee_name}</b> · {coffee_size}\n"
        f"📍 {coffee_shop}\n"
        f"{rating_text}"
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------
# ЗАПУСК
# ---------------------------------------------------------

async def main():
    logging.info(
        "Coffee Diary bot started"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
