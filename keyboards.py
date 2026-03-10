from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb(locale: str = "ru") -> InlineKeyboardMarkup:
    if locale == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📔 Create deal", callback_data="menu:deal_create"),
                ],
                [
                    InlineKeyboardButton(text="🌟 Profile", callback_data="menu:profile"),
                    InlineKeyboardButton(text="📥 Requisites", callback_data="menu:requisites"),
                ],
                [
                    InlineKeyboardButton(text="ℹ️ About", callback_data="menu:about"),
                    InlineKeyboardButton(text="🏴 Language", callback_data="menu:language"),
                ],
                [
                    InlineKeyboardButton(text="💁‍♂️ Support", callback_data="menu:support"),
                ],
            ],
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📔Создать сделку", callback_data="menu:deal_create"),
            ],
            [
                InlineKeyboardButton(text="🌟Профиль", callback_data="menu:profile"),
                InlineKeyboardButton(text="📥Реквизиты", callback_data="menu:requisites"),
            ],
            [
                InlineKeyboardButton(text="ℹ️Подробнее", callback_data="menu:about"),
                InlineKeyboardButton(text="🏴Язык", callback_data="menu:language"),
            ],
            [
                InlineKeyboardButton(text="💁‍♂️Поддержка", callback_data="menu:support"),
            ],
        ],
    )


def language_choice_kb() -> InlineKeyboardMarkup:
    return language_choice_kb_with_origin()


def language_choice_kb_with_origin(origin: str = "start") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"lang:ru:{origin}"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data=f"lang:en:{origin}"),
            ]
        ]
    )


def profile_kb(locale: str = "ru") -> InlineKeyboardMarkup:
    if locale == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📥 Requisites", callback_data="menu:requisites")],
                [InlineKeyboardButton(text="⬅️ Back to menu", callback_data="nav:main_menu")],
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥Реквизиты", callback_data="menu:requisites")],
            [InlineKeyboardButton(text="⬅️В меню", callback_data="nav:main_menu")],
        ]
    )


def requisites_menu_kb(locale: str = "ru") -> InlineKeyboardMarkup:
    if locale == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🪙 Add/Edit TON wallet", callback_data="req:ton")],
                [InlineKeyboardButton(text="💳 Add/Edit card", callback_data="req:card")],
                [InlineKeyboardButton(text="🔄 Add/Edit SBP phone", callback_data="req:sbp")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="nav:main_menu")],
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🪙 Добавить/Изменить TON-кошелёк", callback_data="req:ton")],
            [InlineKeyboardButton(text="💳 Добавить/Изменить карту", callback_data="req:card")],
            [InlineKeyboardButton(text="🔄 Добавить/Изменить СБП", callback_data="req:sbp")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:main_menu")],
        ]
    )

