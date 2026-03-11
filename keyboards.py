from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# === Главное меню бота ===
def main_menu_kb(locale: str = "ru") -> InlineKeyboardMarkup:
    if locale == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📔 Create deal", callback_data="deal_create"),
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
                    InlineKeyboardButton(text="💁‍♂️ Support", url="https://t.me/Dirdols"),
                ],
            ],
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📔Создать сделку", callback_data="deal_create"),
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
                InlineKeyboardButton(text="💁‍♂️Поддержка", url="https://t.me/Dirdols"),
            ],
        ],
    )


# === Клавиатуры выбора языка ===
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


def language_choice_kb_with_back_to_menu(origin: str = "start") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"lang:ru:{origin}"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data=f"lang:en:{origin}"),
            ],
            [InlineKeyboardButton(text="Menu/Меню", callback_data="nav")],
        ]
    )


# === Кнопка «Назад в меню» из раздела «О боте» и других экранов ===
def about_return_to_menu(locale: str = "ru") -> InlineKeyboardMarkup:
    if locale == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back to menu", callback_data="nav")]
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="nav")]
        ]
    )


# === Клавиатура профиля пользователя ===
def profile_kb(locale: str = "ru") -> InlineKeyboardMarkup:
    if locale == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📥 Requisites", callback_data="menu:requisites")],
                [InlineKeyboardButton(text="⬅️ Back to menu", callback_data="nav")],
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥Реквизиты", callback_data="menu:requisites")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="nav")],
        ]
    )


# === Меню управления реквизитами (TON, карта, СБП) ===
def requisites_menu_kb(locale: str = "ru") -> InlineKeyboardMarkup:
    if locale == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🪙 Add/Edit TON wallet", callback_data="req:ton")],
                [InlineKeyboardButton(text="💳 Add/Edit card", callback_data="req:card")],
                [InlineKeyboardButton(text="🔄 Add/Edit SBP phone", callback_data="req:sbp")],
                [InlineKeyboardButton(text="⬅️ Back to menu", callback_data="nav")],
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🪙 Добавить/Изменить TON-кошелёк", callback_data="req:ton")],
            [InlineKeyboardButton(text="💳 Добавить/Изменить карту", callback_data="req:card")],
            [InlineKeyboardButton(text="🔄 Добавить/Изменить СБП", callback_data="req:sbp")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="nav")],
        ]
    )


# === Выбор метода оплаты при создании сделки ===
def select_payment_metod(locale: str = "ru", has_ton: bool = True, has_card: bool = True, has_sbp: bool = True) -> InlineKeyboardMarkup:
    keyboard = []

    if has_ton:
        ton_text = "🪙 TON wallet" if locale == "en" else "🪙 TON-кошелёк"
        keyboard.append([InlineKeyboardButton(text=ton_text, callback_data="deal_create:pay:ton")])

    if has_card:
        card_text = "💳 Bank card" if locale == "en" else "💳 Банковская Карта"
        keyboard.append([InlineKeyboardButton(text=card_text, callback_data="deal_create:pay:card")])

    if has_sbp:
        sbp_text = "🔄 SBP" if locale == "en" else "🔄 СБП"
        keyboard.append([InlineKeyboardButton(text=sbp_text, callback_data="deal_create:pay:sbp")])

    back_text = "⬅️ Back to menu" if locale == "en" else "⬅️ В меню"
    keyboard.append([InlineKeyboardButton(text=back_text, callback_data="nav")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# === Кнопка подтверждения оплаты сделки покупателем ===
def buyer_deal_confirm_kb(public_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"deal_buyer_paid:{public_id}")],
        ]
    )
