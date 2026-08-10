import asyncio
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
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
# ПУТИ
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
ASSETS_PATH = BASE_DIR / "assets"


# =========================================================
# КАРТИНКИ ПЕРСОНАЖА
# =========================================================

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
# ЗАГРУЗКА И ПЕРЕКОДИРОВКА КАРТИНКИ
# =========================================================

def load_character_image(character: str) -> BufferedInputFile:
    """
    Загружает картинку персонажа и принудительно
    пересохраняет её в нормальный JPEG.

    Это исправляет Telegram IMAGE_PROCESS_FAILED,
    который возникал на Drinking.jpeg.
    """

    image_path = CHARACTER_IMAGES.get(
        character,
        CHARACTER_IMAGES["idle"],
    )

    if not image_path.exists():
        logging.error(
            "Character image not found: %s",
            image_path,
        )

        raise FileNotFoundError(
            f"Character image not found: {image_path}"
        )

    try:
        with Image.open(image_path) as image:

            logging.info(
                "Loading character image: %s | format=%s | mode=%s | size=%s",
                image_path.name,
                image.format,
                image.mode,
                image.size,
            )

            # Исправляем возможную ориентацию EXIF.
            image = ImageOps.exif_transpose(image)

            # JPEG не поддерживает alpha.
            if image.mode in ("RGBA", "LA"):
                background = Image.new(
                    "RGB",
                    image.size,
                    "white",
                )

                alpha = image.getchannel("A")

                background.paste(
                    image,
                    mask=alpha,
                )

                image = background

            elif image.mode != "RGB":
                image = image.convert("RGB")

            output = BytesIO()

            image.save(
                output,
                format="JPEG",
                quality=95,
                optimize=True,
                progressive=False,
            )

            output.seek(0)

            filename = f"{character}.jpg"

            return BufferedInputFile(
                output.read(),
                filename=filename,
            )

    except Exception as error:
        logging.exception(
            "Failed to process character image %s: %s",
            image_path,
            error,
        )

        raise


# =========================================================
# БЕЗОПАСНОЕ РЕДАКТИРОВАНИЕ ЭКРАНА
# =========================================================

async def edit_screen(
    message: Message,
    caption: str,
    keyboard=None,
    character: str = "idle",
):
    """
    Пытается заменить существующую фотографию.

    Если Telegram не принимает новое изображение,
    удаляем старое сообщение и создаём новое.

    Возвращает Message, которое сейчас является
    актуальным экраном.
    """

    photo = load_character_image(character)

    # -----------------------------------------------------
    # 1. Пытаемся заменить существующую фотографию
    # -----------------------------------------------------

    if message.photo:

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

            logging.info(
                "Screen edited successfully: character=%s message_id=%s",
                character,
                message.message_id,
            )

            return message

        except TelegramBadRequest as error:

            error_text = str(error)

            # Telegram иногда говорит, что сообщение
            # вообще не изменилось.
            if "message is not modified" in error_text.lower():

                logging.info(
                    "Screen was not modified: message_id=%s",
                    message.message_id,
                )

                try:
                    await message.edit_reply_markup(
                        reply_markup=keyboard
                    )
                except Exception:
                    pass

                return message

            logging.warning(
                "edit_media failed for %s: %s",
                character,
                error,
            )

        except Exception as error:

            logging.exception(
                "Unexpected edit_media error: %s",
                error,
            )

    # -----------------------------------------------------
    # 2. Если редактирование не получилось —
    #    создаём новое сообщение
    # -----------------------------------------------------

    try:

        new_message = await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

        logging.info(
            "Created new screen: character=%s new_message_id=%s",
            character,
            new_message.message_id,
        )

        # Старое сообщение можно удалить после
        # успешного создания нового.
        try:
            await message.delete()
        except Exception:
            pass

        return new_message

    except Exception as error:

        logging.exception(
            "Creating new screen failed: %s",
            error,
        )

        # Если Telegram вообще не смог отправить картинку,
        # пытаемся хотя бы поменять текст существующего
        # сообщения.
        try:

            if message.photo:

                await message.edit_caption(
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                )

                return message

        except Exception:
            pass

        return message


# =========================================================
# ОБНОВЛЕНИЕ ЭКРАНА + FSM
# =========================================================

async def render_screen(
    message: Message,
    state: FSMContext,
    caption: str,
    keyboard=None,
    character: str = "idle",
):
    """
    Общая функция для экранов.

    ВАЖНО:
    если edit_screen создаст новое сообщение,
    main_message_id автоматически обновится.
    """

    result = await edit_screen(
        message=message,
        caption=caption,
        keyboard=keyboard,
        character=character,
    )

    await state.update_data(
        main_message_id=result.message_id
    )

    return result


# =========================================================
# ФОРМАТ ДАТЫ
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

    date_text = (
        f"{dt.day} "
        f"{months[dt.month - 1]}"
    )

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

    await render_screen(
        message=message,
        state=state,
        caption=caption,
        keyboard=main_keyboard(),
        character=character,
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

    await render_screen(
        message=callback.message,
        state=state,
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

    # На этом этапе фото уже существует,
    # поэтому используем актуальное сообщение.
    try:

        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=main_message_id,
            caption=caption,
            reply_markup=coffee_size_keyboard(),
            parse_mode=ParseMode.HTML,
        )

    except TelegramBadRequest as error:

        logging.warning(
            "Coffee size caption edit failed: %s",
            error,
        )

        # Если старое сообщение потерялось,
        # создаём новый экран.
        try:

            new_message = await message.answer_photo(
                photo=load_character_image(
                    "holding_coffee"
                ),
                caption=caption,
                reply_markup=coffee_size_keyboard(),
                parse_mode=ParseMode.HTML,
            )

            await state.update_data(
                main_message_id=new_message.message_id
            )

        except Exception as new_error:

            logging.exception(
                "Failed to create coffee size screen: %s",
                new_error,
            )


# =========================================================
# РАЗМЕР КОФЕ
# =========================================================

@dp.callback_query(
    F.data.startswith("size:")
)
async def coffee_size_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    size = callback.data.split(":", 1)[1]

    logging.info(
        "Coffee size selected: %s",
        size,
    )

    await state.update_data(
        coffee_size=size
    )

    await state.set_state(
        AddCoffee.coffee_shop
    )

    await callback.answer(
        f"Размер {size} выбран ☕️"
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

    # =====================================================
    # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ
    # =====================================================
    #
    # edit_screen теперь:
    #
    # 1. перекодирует Drinking.jpeg;
    # 2. пытается заменить картинку;
    # 3. если Telegram отвечает IMAGE_PROCESS_FAILED,
    #    создаёт новое сообщение;
    # 4. возвращает новое Message;
    # 5. main_message_id обновляется.
    #

    result = await render_screen(
        message=callback.message,
        state=state,
        caption=caption,
        keyboard=back_keyboard(),
        character="drinking",
    )

    logging.info(
        "Coffee size step completed. "
        "Next state: coffee_shop. "
        "message_id=%s",
        result.message_id,
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
        logging.error(
            "main_message_id missing in coffee_shop_handler"
        )
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

    # Получаем chat_id и message_id.
    # Это позволяет продолжить работу даже если
    # предыдущий экран был создан заново.
    try:

        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=main_message_id,
            caption=caption,
            reply_markup=rating_keyboard(),
            parse_mode=ParseMode.HTML,
        )

    except TelegramBadRequest as error:

        logging.warning(
            "Coffee shop screen edit failed: %s",
            error,
        )

        # Если старое сообщение исчезло —
        # создаём новый экран.
        try:

            new_message = await message.answer_photo(
                photo=load_character_image(
                    "drinking"
                ),
                caption=caption,
                reply_markup=rating_keyboard(),
                parse_mode=ParseMode.HTML,
            )

            await state.update_data(
                main_message_id=new_message.message_id
            )

        except Exception as new_error:

            logging.exception(
                "Failed to create rating screen: %s",
                new_error,
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

    value = callback.data.split(":", 1)[1]

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

    result = await render_screen(
        message=callback.message,
        state=state,
        caption=caption,
        keyboard=main_keyboard(),
        character="happy",
    )

    await state.clear()

    # После clear сохраняем актуальный message_id.
    await state.update_data(
        main_message_id=result.message_id
    )


# =========================================================
# СТАТИСТИКА
# =========================================================

@dp.callback_query(
    F.data == "statistics"
)
async def statistics_handler(
    callback: CallbackQuery,
    state: FSMContext,
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

    await render_screen(
        message=callback.message,
        state=state,
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
    state: FSMContext,
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

        await render_screen(
            message=message,
            state=state,
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

    await render_screen(
        message=message,
        state=state,
        caption=caption,
        keyboard=keyboard,
        character="sitting",
    )


# =========================================================
# ИСТОРИЯ — CALLBACK
# =========================================================

@dp.callback_query(
    F.data == "history"
)
async def history_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    await render_history(
        message=callback.message,
        telegram_id=callback.from_user.id,
        state=state,
    )


# =========================================================
# УДАЛЕНИЕ
# =========================================================

@dp.callback_query(
    F.data.startswith("delete:")
)
async def delete_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    try:

        coffee_id = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка записи.",
            show_alert=True,
        )

        return

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
        state=state,
    )


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logging.info(
        "☕ Coffee Diary bot started"
    )

    logging.info(
        "Assets path: %s",
        ASSETS_PATH,
    )

    for name, path in CHARACTER_IMAGES.items():

        if path.exists():

            logging.info(
                "Character available: %s -> %s",
                name,
                path,
            )

        else:

            logging.error(
                "Character MISSING: %s -> %s",
                name,
                path,
            )

    logging.info(
        "Start polling"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
