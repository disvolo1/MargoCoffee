from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="☕️ Добавить кофе",
                    callback_data="add_coffee",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 История",
                    callback_data="history",
                ),
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="statistics",
                ),
            ],
        ]
    )


def coffee_size_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="S",
                    callback_data="size:S",
                ),
                InlineKeyboardButton(
                    text="M",
                    callback_data="size:M",
                ),
                InlineKeyboardButton(
                    text="L",
                    callback_data="size:L",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="back_main",
                )
            ],
        ]
    )


def rating_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐️ 1",
                    callback_data="rating:1",
                ),
                InlineKeyboardButton(
                    text="⭐️ 2",
                    callback_data="rating:2",
                ),
                InlineKeyboardButton(
                    text="⭐️ 3",
                    callback_data="rating:3",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐️ 4",
                    callback_data="rating:4",
                ),
                InlineKeyboardButton(
                    text="⭐️ 5",
                    callback_data="rating:5",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Без оценки",
                    callback_data="rating:none",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="back_main",
                )
            ],
        ]
    )


def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="back_main",
                )
            ]
        ]
    )
