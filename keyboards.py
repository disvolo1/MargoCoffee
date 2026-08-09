from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="☕ Добавить кофе",
                    callback_data="add_coffee"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="statistics"
                ),
                InlineKeyboardButton(
                    text="📖 История",
                    callback_data="history"
                )
            ]
        ]
    )


def coffee_size_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="S",
                    callback_data="size:S"
                ),
                InlineKeyboardButton(
                    text="M",
                    callback_data="size:M"
                ),
                InlineKeyboardButton(
                    text="L",
                    callback_data="size:L"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="back_main"
                )
            ]
        ]
    )


def rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐️ 1",
                    callback_data="rating:1"
                ),
                InlineKeyboardButton(
                    text="⭐️ 2",
                    callback_data="rating:2"
                ),
                InlineKeyboardButton(
                    text="⭐️ 3",
                    callback_data="rating:3"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐️ 4",
                    callback_data="rating:4"
                ),
                InlineKeyboardButton(
                    text="⭐️ 5",
                    callback_data="rating:5"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Без оценки",
                    callback_data="rating:none"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="back_main"
                )
            ]
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="back_main"
                )
            ]
        ]
    )


def history_navigation_keyboard(
    has_newer: bool = False,
    has_older: bool = False
) -> InlineKeyboardMarkup:
    buttons = []

    navigation = []

    if has_newer:
        navigation.append(
            InlineKeyboardButton(
                text="← Новее",
                callback_data="history:newer"
            )
        )

    if has_older:
        navigation.append(
            InlineKeyboardButton(
                text="Старше →",
                callback_data="history:older"
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append([
        InlineKeyboardButton(
            text="← Назад",
            callback_data="back_main"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def delete_keyboard(coffee_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"delete:{coffee_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="history"
                )
            ]
        ]
    )
