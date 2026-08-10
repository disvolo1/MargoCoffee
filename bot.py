
Снимок экрана — 2026-08-10 в 13.40.22.png
это?

Да, это именно тот экран.

Но здесь важно: кнопка Resume Web Service просто снова запустит текущий Web Service — и проблема с отсутствием порта останется.

Тебе нужно не Resume, а создать новый сервис типа Background Worker.

Сейчас у тебя:

Web Service ❌

Нужно:

Background Worker ✅

Что сделать
Нажми Delete Web Service.

В Render создай новый сервис из того же GitHub-репозитория.

При выборе типа сервиса выбери Background Worker.

Укажи:

Build Command:
pip install -r requirements.txt
Start Command:
python bot.py
Добавь те же Environment Variables:

BOT_TOKEN

SUPABASE_URL

SUPABASE_KEY

и остальные, которые у тебя были.

Deploy.

Порт указывать не нужно.

После этого в логах должно быть примерно:

☕ Coffee Diary bot started
Start polling
Run polling for bot @MargoCoffe_bot
и не должно быть:

No open ports detected
Port scan timeout reached
Received SIGTERM
Timed Out
И ещё: если после запуска нового Worker появится TelegramConflictError, значит старый экземпляр бота всё ещё где-то запущен. Тогда его нужно остановить.


а он просит деньги , а я бесплатно хочу

Да. Платить тебе не нужно. По логам проблема не в Python и не в Supabase.

У тебя сейчас создан Web Service, а бот работает через Telegram long polling и не открывает HTTP-порт. Поэтому Render ждёт порт, не находит его и через некоторое время завершает сервис:

No open ports detected
Port scan timeout reached
Timed Out

Render действительно позволяет запускать Web Service бесплатно, но он должен слушать HTTP-порт. Бесплатный Web Service также засыпает после 15 минут без входящего HTTP-трафика. 

Что сделать сейчас
Не выбирай Background Worker — он на Render сейчас не имеет Free-инстанса. 

Оставляем Free Web Service, но добавляем в bot.py маленький HTTP-сервер. Тогда Render увидит порт и перестанет считать деплой сломанным.

И главное: твои ошибки TelegramConflictError тоже нужно убрать, потому что у тебя одновременно запускалось несколько экземпляров бота. В последнем логе этой ошибки уже нет, так что сейчас основная проблема именно с портом.

Полный bot.py
Я могу дать тебе полный файл, но мне нужен текущий код bot.py, который мы делали в предыдущем сообщении. В этой переписке его содержимое сейчас не отображается целиком, а придумывать его заново опасно — можно сломать уже работающие функции дневника, JPEG и Supabase.

Пришли сюда текущий bot.py файлом — и я верну тебе полностью готовый bot.py, где я:

оставлю всю твою текущую логику;

добавлю HTTP-сервер для Render;

сервер будет слушать PORT от Render;

бот продолжит работать через polling;

исправлю запуск так, чтобы не создавать лишние экземпляры;

сохраню поддержку .jpeg, а не только .jpg;

Supabase останется как есть.

А в Render
Параметры должны быть примерно такие:

Environment: Python 3

Build Command:

pip install -r requirements.txt
Start Command:

python bot.py
Instance Type:

Free
То есть деньги платить не надо. Free Web Services официально доступны на Render. 

Пришли текущий bot.py, и я сразу пришлю тебе его полностью исправленным файлом, без необходимости собирать код по кускам.



bot (3).py
Python

Да, я получил твой текущий bot.py и исправил именно его, не переписывая логику бота с нуля.

Главная проблема была в запуске: бот работает через polling и не открывал порт, из-за чего Render завершал Web Service с Port scan timeout.

Я добавил в код:

HTTP-сервер на 0.0.0.0;

автоматическое использование переменной PORT от Render;

/ и /health для проверки сервиса;

корректное завершение HTTP-сервера;

сохранён весь твой текущий функционал;

.jpeg уже поддерживается — например idle.jpeg, sitting.jpeg, Drinking.jpeg и т.д. 


Готовый bot.py
Скачать исправленный bot.py

Что сделать на Render
Замени старый bot.py этим файлом.

Build Command:

pip install -r requirements.txt
Start Command:

python bot.py
Тип сервиса: Web Service
Тариф: Free

PORT вручную прописывать не надо — код сам возьмёт его из Render.

После нового деплоя в логах должно появиться примерно:

☕ Coffee Diary bot started
HTTP health server started on port 10000
Start polling
Run polling for bot @MargoCoffe_bot
И главное — не должно быть:

No open ports detected
Port scan timeout reached
Timed Out
Если после этого появится именно TelegramConflictError, тогда отдельно разберём второй вопрос — значит, где-то всё ещё запущена вторая копия этого же бота. 


bot_render_free.py
Код

Лимит вложений исчерпан. Перейдите на другой план, чтобы получить больше, или повторите попытку завтра после 00:06.
Перейти на Plus

Библиотека
/
bot_render_free.py


import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from aiohttp import web

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
# HTTP-СЕРВЕР ДЛЯ RENDER
# =========================================================

async def health_handler(request: web.Request):
    return web.Response(
        text="Coffee Diary bot is running ☕️",
        status=200,
    )


async def start_web_server():
    # Render передаёт порт через переменную окружения PORT.
    # Локально используем 8080.
    port = int(os.getenv("PORT", "8080"))

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=port,
    )

    await site.start()

    logging.info(
        "HTTP health server started on port %s",
        port,
    )

    return runner


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logging.info(
        "☕ Coffee Diary bot started"
    )

    # Запускаем HTTP-сервер одновременно с Telegram polling.
    # Это необходимо, если бот размещён на Render как Web Service:
    # Render должен видеть открытый порт.
    web_runner = await start_web_server()

    try:
        await dp.start_polling(
            bot,
            handle_signals=True,
        )
    finally:
        logging.info("Stopping HTTP health server...")
        await web_runner.cleanup()

        logging.info("Closing Telegram bot session...")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
Библиотека
/
bot_render_free.py


import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from aiohttp import web

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
# HTTP-СЕРВЕР ДЛЯ RENDER
# =========================================================

async def health_handler(request: web.Request):
    return web.Response(
        text="Coffee Diary bot is running ☕️",
        status=200,
    )


async def start_web_server():
    # Render передаёт порт через переменную окружения PORT.
    # Локально используем 8080.
    port = int(os.getenv("PORT", "8080"))

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=port,
    )

    await site.start()

    logging.info(
        "HTTP health server started on port %s",
        port,
    )

    return runner


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logging.info(
        "☕ Coffee Diary bot started"
    )

    # Запускаем HTTP-сервер одновременно с Telegram polling.
    # Это необходимо, если бот размещён на Render как Web Service:
    # Render должен видеть открытый порт.
    web_runner = await start_web_server()

    try:
        await dp.start_polling(
            bot,
            handle_signals=True,
        )
    finally:
        logging.info("Stopping HTTP health server...")
        await web_runner.cleanup()

        logging.info("Closing Telegram bot session...")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
