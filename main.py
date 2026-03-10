import asyncio
import logging
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from db import (
    get_platform_stats,
    get_user_locale,
    get_user_profile,
    init_db,
    set_user_card_number,
    set_user_locale,
    set_user_sbp_phone,
    set_user_ton_wallet,
    upsert_user,
)
from keyboards import (
    language_choice_kb_with_origin,
    main_menu_kb,
    profile_kb,
    requisites_menu_kb,
)


TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "choose_lang": "Выбери язык / Choose language",
        "welcome": "Привет! Это бот гаранта.\n\nВыбери действие в меню ниже:",
        "main_menu": "Главное меню\n\nВ нашем боте доступен следующий функционал:",
        "section_wip": "Раздел в разработке. Опиши, что должно быть тут.",
        "profile_title": "👤 Ваш профиль",
        "requisites_choose": "Выберите действие:",
        "enter_ton": "Отправьте адрес TON-кошелька (например: EQ... или UQ...).",
        "enter_card": "Отправьте номер карты (16 цифр). Поддерживаются только российские карты платёжной системы МИР.",
        "enter_sbp": "Отправьте номер телефона СБП (начинается на +7 или 8 и дальше 10 цифр). Поддерживаются только российские номера.",
        "saved": "✅ Сохранено.",
        "invalid_ton": "❌ Неверный TON-адрес. Формат: начинается с EQ или UQ и далее 46 символов (A-Z a-z 0-9 _ -).",
        "invalid_card": "❌ Неверный номер карты. Нужно ровно 16 цифр, карта должна быть российской платёжной системы МИР (BIN 220000–220499).",
        "invalid_sbp": "❌ Неверный номер. Нужно +7XXXXXXXXXX или 8XXXXXXXXXX (ровно 10 цифр после префикса).",
    },
    "en": {
        "choose_lang": "Choose language / Выбери язык",
        "welcome": "Hi! This is a guarant bot.\n\nChoose an action from the menu below:",
        "main_menu": "Main menu\n\nThe following functionality is available in our bot:",
        "section_wip": "This section is under development. Tell me what should be here.",
        "profile_title": "👤 Your profile",
        "requisites_choose": "Choose an action:",
        "enter_ton": "Send your TON wallet address (e.g. EQ... or UQ...).",
        "enter_card": "Send your card number (16 digits). Only Russian MIR cards are supported.",
        "enter_sbp": "Send your SBP phone number (starts with +7 or 8, then 10 digits). Only Russian phone numbers are supported.",
        "saved": "✅ Saved.",
        "invalid_ton": "❌ Invalid TON address. Format: starts with EQ or UQ, then 46 chars (A-Z a-z 0-9 _ -).",
        "invalid_card": "❌ Invalid card number. It must be exactly 16 digits and belong to Russian MIR system (BIN 220000–220499).",
        "invalid_sbp": "❌ Invalid phone. Use +7XXXXXXXXXX or 8XXXXXXXXXX (exactly 10 digits after prefix).",
    },
}


def t(locale: str, key: str) -> str:
    return TEXTS.get(locale, TEXTS["ru"]).get(key, key)


def guess_locale_from_tg(language_code: str | None) -> str:
    if not language_code:
        return "ru"
    code = language_code.lower()
    if code.startswith("ru"):
        return "ru"
    if code.startswith("en"):
        return "en"
    return "ru"


class RequisitesForm(StatesGroup):
    ton = State()
    card = State()
    sbp = State()


RE_TON = re.compile(r"^(?:EQ|UQ)[A-Za-z0-9_-]{46}$")
RE_CARD = re.compile(r"^\d{16}$")
RE_SBP = re.compile(r"^(?:\+7|8)\d{10}$")


def is_mir_card(number: str) -> bool:
    if not RE_CARD.fullmatch(number):
        return False
    try:
        bin_code = int(number[:6])
    except ValueError:
        return False
    return 220000 <= bin_code <= 220499


def render_profile(locale: str, profile) -> str:
    user_id = profile["id"]
    balance = float(profile["balance"] or 0)
    ton = profile["ton_wallet"] or None
    card = profile["card_number"] or None
    sbp = profile["sbp_phone"] or None

    if locale == "en":
        return (
            f"{t(locale, 'profile_title')}\n\n"
            f"🆔 Unique ID: {user_id}\n"
            f"💰 Balance: {balance:.1f} ₽\n"
            f"⭐ Rating: ★★★★★ (5.0/5) | Deals total: 0 | Successful: 0\n\n"
            f"💰 Payout requisites:\n"
            f"🪙 TON wallet: {'❌ Not set' if not ton else ton}\n"
            f"💳 Card: {'❌ Not set' if not card else card}\n"
            f"🔄 SBP: {'❌ Not set' if not sbp else sbp}"
        )

    return (
        f"{t(locale, 'profile_title')}\n\n"
        f"🆔 Уникальный ID: {user_id}\n"
        f"💰 Баланс: {balance:.1f} ₽\n"
        f"⭐ Рейтинг: ★★★★★ (5.0/5) | Всего сделок: 0 | Успешных: 0\n\n"
        f"💰 Реквизиты для выплат:\n"
        f"🪙 TON-кошелек: {'❌ Не указан' if not ton else ton}\n"
        f"💳 Карта: {'❌ Не указана' if not card else card}\n"
        f"🔄СБП: {'❌ Не указана' if not sbp else sbp}"
    )


def format_int_with_space(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def render_about(locale: str) -> str:
    stats = get_platform_stats()
    total_deals = int(stats["total_deals"])
    success_deals = int(stats["success_deals"])
    total_volume_usd = float(stats["total_volume_usd"])
    avg_rating = float(stats["avg_rating"])
    online_now = int(stats["online_now"])

    if locale == "en":
        return (
            "📊 XPay statistics\n\n"
            f"🤝 Total deals: {format_int_with_space(total_deals)}\n"
            f"✅ Successful deals: {format_int_with_space(success_deals)}\n"
            f"💰 Total volume: ${format_int_with_space(int(total_volume_usd))}\n"
            f"⭐️ Average rating: {avg_rating:.1f}/5.0\n"
            f"🟢 Online now: {format_int_with_space(online_now)}\n\n"
            "📈 Our advantages:\n\n"
            "• 🔒 Escrow service for all deals\n"
            "• ⚡️ Instant goods delivery\n"
            "• 🛡️ Protection from scammers\n"
            "• 💎 Verified sellers\n"
            "• 📞 24/7 Support\n"
            "• ⭐️ 99.8% positive reviews"
        )

    return (
        "📊 Статистика XPay\n\n"
        f"🤝 Всего сделок: {format_int_with_space(total_deals)}\n"
        f"✅ Успешных сделок: {format_int_with_space(success_deals)}\n"
        f"💰 Общий объем: ${format_int_with_space(int(total_volume_usd))}\n"
        f"⭐️ Средний рейтинг: {avg_rating:.1f}/5.0\n"
        f"🟢 Онлайн сейчас: {format_int_with_space(online_now)}\n\n"
        "📈 Наши преимущества:\n\n"
        "• 🔒 Гарант-сервис на все сделки\n"
        "• ⚡️ Мгновенная доставка товаров\n"
        "• 🛡️ Защита от мошенников\n"
        "• 💎 Проверенные продавцы\n"
        "• 📞 24/7 Поддержка\n"
        "• ⭐️ 99.8% положительных отзывов"
    )


async def on_start(message: Message) -> None:
    upsert_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )

    locale = get_user_locale(message.from_user.id)
    if not locale:
        await message.answer(t("ru", "choose_lang"), reply_markup=language_choice_kb_with_origin("start"))
        return

    await message.answer(t(locale, "welcome"), reply_markup=main_menu_kb(locale))


async def on_language_choose(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user:
        return

    parts = (callback.data or "").split(":")
    locale = parts[1] if len(parts) > 1 else ""
    origin = parts[2] if len(parts) > 2 else "start"
    if locale not in ("ru", "en"):
        locale = guess_locale_from_tg(callback.from_user.language_code)

    upsert_user(
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        language_code=callback.from_user.language_code,
    )
    set_user_locale(callback.from_user.id, locale)

    if callback.message:
        key = "main_menu" if origin == "menu" else "welcome"
        await callback.message.answer(t(locale, key), reply_markup=main_menu_kb(locale))


async def on_menu_click(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)

    if callback.data == "nav:main_menu":
        await callback.message.answer(t(locale, "main_menu"), reply_markup=main_menu_kb(locale))
        return

    if callback.data == "menu:language":
        await callback.message.answer(t(locale, "choose_lang"), reply_markup=language_choice_kb_with_origin("menu"))
        return

    if callback.data == "menu:profile":
        profile = get_user_profile(callback.from_user.id)
        if not profile:
            upsert_user(
                tg_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                language_code=callback.from_user.language_code,
            )
            profile = get_user_profile(callback.from_user.id)
        if profile:
            await callback.message.answer(render_profile(locale, profile), reply_markup=profile_kb(locale))
        return

    if callback.data == "menu:requisites":
        await callback.message.answer(t(locale, "requisites_choose"), reply_markup=requisites_menu_kb(locale))
        return

    if callback.data == "menu:about":
        await callback.message.answer(render_about(locale), reply_markup=main_menu_kb(locale))
        return

    await callback.message.answer(t(locale, "section_wip"), reply_markup=main_menu_kb(locale))


async def on_requisites_action(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)

    if callback.data == "req:ton":
        await state.set_state(RequisitesForm.ton)
        await callback.message.answer(t(locale, "enter_ton"))
        return
    if callback.data == "req:card":
        await state.set_state(RequisitesForm.card)
        await callback.message.answer(t(locale, "enter_card"))
        return
    if callback.data == "req:sbp":
        await state.set_state(RequisitesForm.sbp)
        await callback.message.answer(t(locale, "enter_sbp"))
        return


async def on_enter_ton(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)
    value = (message.text or "").strip()
    if not RE_TON.fullmatch(value):
        await message.answer(t(locale, "invalid_ton"))
        return
    set_user_ton_wallet(message.from_user.id, value)
    await state.clear()
    await message.answer(t(locale, "saved"))
    profile = get_user_profile(message.from_user.id)
    if profile:
        await message.answer(render_profile(locale, profile), reply_markup=profile_kb(locale))


async def on_enter_card(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)
    value = (message.text or "").strip().replace(" ", "")
    if not is_mir_card(value):
        await message.answer(t(locale, "invalid_card"))
        return
    set_user_card_number(message.from_user.id, value)
    await state.clear()
    await message.answer(t(locale, "saved"))
    profile = get_user_profile(message.from_user.id)
    if profile:
        await message.answer(render_profile(locale, profile), reply_markup=profile_kb(locale))


async def on_enter_sbp(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)
    value = (message.text or "").strip().replace(" ", "")
    if not RE_SBP.fullmatch(value):
        await message.answer(t(locale, "invalid_sbp"))
        return
    set_user_sbp_phone(message.from_user.id, value)
    await state.clear()
    await message.answer(t(locale, "saved"))
    profile = get_user_profile(message.from_user.id)
    if profile:
        await message.answer(render_profile(locale, profile), reply_markup=profile_kb(locale))


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    load_dotenv()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не найден BOT_TOKEN в переменных окружения")

    init_db()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(on_start, CommandStart())
    dp.callback_query.register(on_language_choose, F.data.startswith("lang:"))
    dp.callback_query.register(on_menu_click, F.data.startswith("menu:"))
    dp.callback_query.register(on_requisites_action, F.data.startswith("req:"))
    dp.message.register(on_enter_ton, RequisitesForm.ton)
    dp.message.register(on_enter_card, RequisitesForm.card)
    dp.message.register(on_enter_sbp, RequisitesForm.sbp)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
