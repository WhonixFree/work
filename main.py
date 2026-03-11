import asyncio
import logging
import os
import re
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from db import (
    get_platform_stats,
    get_user_locale,
    get_user_profile,
    debit_user_balance,
    credit_user_balance,
    init_db,
    set_user_card_number,
    set_user_locale,
    set_user_sbp_phone,
    set_user_ton_wallet,
    upsert_user,
    create_deal,
    get_deal,
    get_deal_by_public_id,
    attach_buyer_to_deal,
    update_deal_status,
    update_user_stats,
)
from keyboards import (
    language_choice_kb_with_origin,
    main_menu_kb,
    profile_kb,
    requisites_menu_kb,
    about_return_to_menu,
    language_choice_kb_with_back_to_menu,
    select_payment_metod,
    buyer_deal_confirm_kb,
)

TON_RATE_RUB = 250.0
CHAT_HISTORY: dict[int, set[int]] = defaultdict(set)


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

class DealForm(StatesGroup):
    choose_method = State()
    ton_amount = State()
    card_amount = State()
    sbp_amount = State()
    item_description = State()
    confirm = State()

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
    rating = profile["avg_rating"] or 0
    total_Deals = profile["total_deals"] or 0
    success_deals = profile["success_deals"] or 0

    if locale == "en":
        return (
            f"{t(locale, 'profile_title')}\n\n"
            f"🆔 Unique ID: {user_id}\n"
            f"💰 Balance: {balance:.1f} ₽\n"
            f"⭐ Rating: ★★★★★ ({rating}/5) | Deals total: {total_Deals} | Successful: {success_deals}\n\n"
            f"💰 Payout requisites:\n"
            f"🪙 TON wallet: {'❌ Not set' if not ton else ton}\n"
            f"💳 Card: {'❌ Not set' if not card else card}\n"
            f"🔄 SBP: {'❌ Not set' if not sbp else sbp}"
        )

    return (
        f"{t(locale, 'profile_title')}\n\n"
        f"🆔 Уникальный ID: {user_id}\n"
        f"💰 Баланс: {balance:.1f} ₽\n"
        f"⭐ Рейтинг: ★★★★★ ({rating}/5) | Всего сделок:  {total_Deals} | Успешных: {success_deals}\n\n"
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


async def safe_delete_message(message: Message | None) -> None:
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        # Игнорируем любые ошибки удаления (например, уже удалено)
        pass


async def send_user_message(message: Message, text: str, reply_markup=None) -> Message:
    """
    Отправляет одно актуальное сообщение от бота пользователю:
    перед отправкой удаляет все ранее сохранённые сообщения (и бота, и пользователя)
    в этом чате, включая текущее пользовательское сообщение.
    """
    if not message.from_user:
        return await message.answer(text, reply_markup=reply_markup)

    user_id = message.from_user.id
    chat_id = message.chat.id

    # Добавляем текущее сообщение пользователя в историю на удаление
    CHAT_HISTORY[chat_id].add(message.message_id)

    # Удаляем все старые сообщения в этом чате, которые мы помним
    for msg_id in list(CHAT_HISTORY[chat_id]):
        try:
            await message.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    CHAT_HISTORY[chat_id].clear()

    # Отправляем новое сообщение бота и запоминаем его id
    sent = await message.answer(text, reply_markup=reply_markup)
    CHAT_HISTORY[chat_id].add(sent.message_id)
    return sent


async def send_callback_message(callback: CallbackQuery, text: str, reply_markup=None) -> Message:
    """
    Аналог send_user_message, но для колбеков:
    удаляем все запомненные сообщения в этом чате (включая сообщение с кнопкой),
    затем шлём новое сообщение бота.
    """
    if not callback.message or not callback.from_user:
        return await callback.message.answer(text, reply_markup=reply_markup)  # type: ignore[union-attr]

    chat_id = callback.message.chat.id
    # Добавляем сообщение с кнопкой в историю
    CHAT_HISTORY[chat_id].add(callback.message.message_id)

    for msg_id in list(CHAT_HISTORY[chat_id]):
        try:
            await callback.message.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    CHAT_HISTORY[chat_id].clear()

    sent = await callback.message.answer(text, reply_markup=reply_markup)
    CHAT_HISTORY[chat_id].add(sent.message_id)
    return sent

async def on_start(message: Message) -> None:
    upsert_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )

    # Deep-link: /start deal=<public_id>
    text = (message.text or "").strip()
    payload = ""
    if " " in text:
        payload = text.split(" ", 1)[1].strip()
    if payload.startswith("deal="):
        public_id = payload[len("deal="):].strip()
        deal = get_deal_by_public_id(public_id)
        if not deal:
            await send_user_message(message, "❌ Сделка не найдена или ссылка неверная.")
            return

        status = (deal["status"] or "").lower()
        if status in ("completed", "paid", "done", "success"):
            amount = float(deal["amount"])
            currency = (deal["currency"] or "").strip()
            amount_display = f"{amount:.9f}".rstrip("0").rstrip(".") if currency == "TON" else f"{amount:.2f}"
            currency_symbol = "TON" if currency == "TON" else ("₽" if currency == "RUB" else currency or "—")
            item = (deal["item_description"] or "").strip() or "."
            await send_user_message(
                message,
                f"🛒 Сделка {public_id}\n"
                f"📋 Товар: {item}\n"
                f"💵 Сумма: {amount_display} {currency_symbol}\n\n"
                f"✅ Сделка уже оплачена и завершена."
            )
            return

        seller_profile = get_user_profile(int(deal["user_id"]))
        if not seller_profile:
            await send_user_message(message, "❌ Продавец не найден. Попробуйте позже.")
            return

        attach_buyer_to_deal(public_id, message.from_user.id)

        rating = float(seller_profile["avg_rating"] or 0.0)
        total_deals = int(seller_profile["total_deals"] or 0)
        success_deals = int(seller_profile["success_deals"] or 0)
        stars = "★" * 5

        payment_method = (deal["payment_method"] or "").lower()
        requisites_lines: list[str] = []
        if payment_method == "ton":
            requisites_lines.append(f"🪙 TON: {seller_profile['ton_wallet'] or '❌ Не указано'}")
        elif payment_method == "card":
            requisites_lines.append(f"💳 Карта: {seller_profile['card_number'] or '❌ Не указано'}")
        elif payment_method == "sbp":
            requisites_lines.append(f"🔄 СБП: {seller_profile['sbp_phone'] or '❌ Не указано'}")
        else:
            requisites_lines.append("❓ Реквизиты: не определены")

        amount = float(deal["amount"])
        currency = (deal["currency"] or "").strip()
        amount_display = f"{amount:.9f}".rstrip("0").rstrip(".") if currency == "TON" else f"{amount:.2f}"
        currency_symbol = "TON" if currency == "TON" else ("₽" if currency == "RUB" else currency or "—")

        item = (deal["item_description"] or "").strip() or "."

        text_out = (
            f"🛒 Сделка {public_id}\n"
            f"⭐ Рейтинг продавца: {stars} ({rating:.1f}/5) | Всего сделок: {total_deals} | Успешных: {success_deals}\n\n"
            f"📦 Тип: {payment_method.upper() if payment_method else '—'}\n"
            f"📋 Товар: {item}\n"
            f"💵 Сумма: {amount_display} {currency_symbol}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 Реквизиты для оплаты:\n"
            + "\n".join(requisites_lines) + "\n\n"
            f"💰 Сумма к оплате: {amount_display} {currency_symbol}\n\n"
            f"⚠️ После оплаты нажмите кнопку подтверждения"
        )
        await send_user_message(message, text_out, reply_markup=buyer_deal_confirm_kb(public_id))
        return

    locale = get_user_locale(message.from_user.id)
    if not locale:
        await send_user_message(message, t("ru", "choose_lang"), reply_markup=language_choice_kb_with_origin("start"))
        return

    await send_user_message(message, t(locale, "welcome"), reply_markup=main_menu_kb(locale))


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
        await send_callback_message(callback, t(locale, key), reply_markup=main_menu_kb(locale))


async def on_menu_click(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)

    if callback.data == "nav:main_menu":
        await send_callback_message(callback, t(locale, "main_menu"), reply_markup=main_menu_kb(locale))
        return

    if callback.data == "menu:language":
        await send_callback_message(
            callback,
            t(locale, "choose_lang"),
            reply_markup=language_choice_kb_with_back_to_menu("menu"),
        )
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
            await send_callback_message(callback, render_profile(locale, profile), reply_markup=profile_kb(locale))
        return

    if callback.data == "menu:requisites":
        await send_callback_message(
            callback,
            t(locale, "requisites_choose"),
            reply_markup=requisites_menu_kb(locale),
        )
        return

    if callback.data == "menu:about":
        await send_callback_message(
            callback,
            render_about(locale),
            reply_markup=about_return_to_menu(locale),
        )
        return

    await send_callback_message(callback, t(locale, "section_wip"), reply_markup=main_menu_kb(locale))


async def on_requisites_action(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)

    if callback.data == "req:ton":
        await state.set_state(RequisitesForm.ton)
        await send_callback_message(callback, t(locale, "enter_ton"))
        return
    if callback.data == "req:card":
        await state.set_state(RequisitesForm.card)
        await send_callback_message(callback, t(locale, "enter_card"))
        return
    if callback.data == "req:sbp":
        await state.set_state(RequisitesForm.sbp)
        await send_callback_message(callback, t(locale, "enter_sbp"))
        return


async def on_enter_ton(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)
    value = (message.text or "").strip()
    if not RE_TON.fullmatch(value):
        await send_user_message(message, t(locale, "invalid_ton"))
        return
    set_user_ton_wallet(message.from_user.id, value)
    await state.clear()
    await send_user_message(message, t(locale, "saved"))
    profile = get_user_profile(message.from_user.id)
    if profile:
        await send_user_message(message, render_profile(locale, profile), reply_markup=profile_kb(locale))


async def on_enter_card(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)
    value = (message.text or "").strip().replace(" ", "")
    if not is_mir_card(value):
        await send_user_message(message, t(locale, "invalid_card"))
        return
    set_user_card_number(message.from_user.id, value)
    await state.clear()
    await send_user_message(message, t(locale, "saved"))
    profile = get_user_profile(message.from_user.id)
    if profile:
        await send_user_message(message, render_profile(locale, profile), reply_markup=profile_kb(locale))


async def on_enter_sbp(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)
    value = (message.text or "").strip().replace(" ", "")
    if not RE_SBP.fullmatch(value):
        await send_user_message(message, t(locale, "invalid_sbp"))
        return
    set_user_sbp_phone(message.from_user.id, value)
    await state.clear()
    await send_user_message(message, t(locale, "saved"))
    profile = get_user_profile(message.from_user.id)
    if profile:
        await send_user_message(message, render_profile(locale, profile), reply_markup=profile_kb(locale))


async def on_deal_create(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)

    profile = get_user_profile(callback.from_user.id)
    if not profile:
        await send_callback_message(
            callback,
            "❌ Ошибка профиля. Попробуйте позже." if locale == "ru"
            else "❌ Profile error. Please try again later.",
        )
        return

    has_ton = profile["ton_wallet"] is not None
    has_card = profile["card_number"] is not None
    has_sbp = profile["sbp_phone"] is not None

    if callback.data == "deal_create":
        await state.clear()

        if not (has_ton or has_card or has_sbp):
            if locale == "en":
                await send_callback_message(
                    callback,
                    "⚠️ You need to add at least one payment method before creating a deal.\n\n"
                    "Add:\n"
                    "• TON wallet, or\n"
                    "• Card number, or\n"
                    "• SBP phone number",
                    reply_markup=requisites_menu_kb(locale),
                )
            else:
                await send_callback_message(
                    callback,
                    "⚠️ Перед созданием сделки нужно добавить хотя бы один метод оплаты.\n\n"
                    "Добавьте:\n"
                    "• TON-кошелёк, или\n"
                    "• Номер карты, или\n"
                    "• Номер СБП",
                    reply_markup=requisites_menu_kb(locale),
                )
            return

        await send_callback_message(
            callback,
            make_order(locale),
            reply_markup=select_payment_metod(locale, has_ton, has_card, has_sbp),
        )
        return

    if callback.data == "deal_create:pay:ton":
        if not has_ton:
            await callback.answer("❌ TON-кошелёк не добавлен!", show_alert=True)
            return
        await state.set_state(DealForm.ton_amount)
        await send_callback_message(callback, "💰 Введите сумму в TON:")
        return

    if callback.data == "deal_create:pay:card":
        if not has_card:
            await callback.answer("❌ Карта не добавлена!", show_alert=True)
            return
        await state.set_state(DealForm.card_amount)
        await send_callback_message(callback, "💰 Введите сумму в рублях:")
        return

    if callback.data == "deal_create:pay:sbp":
        if not has_sbp:
            await callback.answer("❌ СБП не добавлен!", show_alert=True)
            return
        await state.set_state(DealForm.sbp_amount)
        await send_callback_message(callback, "💰 Введите сумму для СБП:")
        return

def make_order(locale: str) -> str:
    if locale == "en":
        return "💰 Select payment method:"

    return "💰 Выберите метод оплаты:"

async def on_enter_payment_amount(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)

    current_state = await state.get_state()
    method_map = {
        DealForm.ton_amount.state: ("ton", "TON"),
        DealForm.card_amount.state: ("card", "RUB"),
        DealForm.sbp_amount.state: ("sbp", "RUB"),
    }

    method_info = method_map.get(current_state)
    if not method_info:
        await state.clear()
        await send_user_message(message, t(locale, "section_wip"), reply_markup=main_menu_kb(locale))
        return

    payment_method, currency = method_info

    try:
        amount_str = (message.text or "").strip().replace(",", ".")
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
        if payment_method == "ton":
            if "." in amount_str and len(amount_str.split(".")[-1]) > 9:
                raise ValueError("Too many decimals for TON")
    except (ValueError, TypeError):
        error_text = (
            "❌ Invalid amount. Enter a positive number (e.g., 100 or 10.5)."
            if locale == "en"
            else "❌ Неверная сумма. Введите положительное число (например, 100 или 10.5)."
        )
        if payment_method == "ton":
            error_text = (
                "❌ Invalid TON amount. Use up to 9 decimals (e.g., 1.5 or 0.123456789)."
                if locale == "en"
                else "❌ Неверная сумма TON. Используйте до 9 знаков после запятой (например, 1.5 или 0.123456789)."
            )
        await send_user_message(message, error_text)
        return

    await state.update_data(
        amount=amount,
        payment_method=payment_method,
        currency=currency
    )

    await state.set_state(DealForm.item_description)

    amount_display = f"{amount:.9f}".rstrip("0").rstrip(".") if payment_method == "ton" else f"{amount:.2f}"
    currency_symbol = "TON" if payment_method == "ton" else "₽"

    if locale == "en":
        prompt_text = (
            f"📝 Specify what you are offering in this deal for {amount_display} {currency_symbol}\n\n"
            f"Example:\n"
            f"https://t.me/nft/PlushPepe-1\n"
            f"https://t.me/nft/DurovsCap-1"
        )
    else:
        prompt_text = (
            f"📝 Укажите, что вы предлагаете в этой сделке за {amount_display} {currency_symbol}\n\n"
            f"Пример:\n"
            f"https://t.me/nft/PlushPepe-1\n"
            f"https://t.me/nft/DurovsCap-1"
        )

    await send_user_message(message, prompt_text)


async def on_enter_deal_item(message: Message, state: FSMContext) -> None:
    locale = get_user_locale(message.from_user.id) or guess_locale_from_tg(message.from_user.language_code)

    item_text = (message.text or "").strip()
    if not item_text:
        await send_user_message(
            message,
            "❌ Please send a valid link or description." if locale == "en"
            else "❌ Отправьте корректную ссылку или описание.",
        )
        return

    await state.update_data(item_description=item_text)

    data = await state.get_data()
    amount = data.get("amount")
    payment_method = data.get("payment_method")
    currency = data.get("currency")
    item = data.get("item_description")

    amount_display = f"{amount:.9f}".rstrip("0").rstrip(".") if payment_method == "ton" else f"{amount:.2f}"
    currency_symbol = "TON" if payment_method == "ton" else "₽"

    await state.set_state(DealForm.confirm)

    if locale == "en":
        confirmation_text = (
            f"📋 Deal confirmation\n\n"
            f"💰 Amount: {amount_display} {currency_symbol}\n"
            f"🔄 Payment method: {payment_method.upper()}\n"
            f"🎁 Your offer: {item}\n\n"
            f"Please confirm the deal:"
        )
        confirm_btn = "✅ Confirm deal"
        cancel_btn = "❌ Cancel"
    else:
        confirmation_text = (
            f"📋 Подтверждение сделки\n\n"
            f"💰 Сумма: {amount_display} {currency_symbol}\n"
            f"🔄 Способ оплаты: {payment_method.upper()}\n"
            f"🎁 Ваш товар: {item}\n\n"
            f"Подтверждаете сделку?"
        )
        confirm_btn = "✅ Подтвердить сделку"
        cancel_btn = "❌ Отмена"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=confirm_btn, callback_data="deal:confirm:yes")],
        [InlineKeyboardButton(text=cancel_btn, callback_data="deal:confirm:no")],
    ])

    await send_user_message(message, confirmation_text, reply_markup=keyboard)


async def on_deal_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)
    data = await state.get_data()

    if callback.data == "deal:confirm:yes":
        try:
            deal_id, public_id = create_deal(
                tg_id=callback.from_user.id,
                payment_method=data["payment_method"],
                amount=data["amount"],
                currency=data["currency"],
                item_description=data["item_description"],
            )

            amount = data["amount"]
            payment_method = data["payment_method"]
            amount_display = f"{amount:.9f}".rstrip("0").rstrip(".") if payment_method == "ton" else f"{amount:.2f}"
            currency_symbol = "TON" if payment_method == "ton" else "₽"

            me = await callback.bot.get_me()
            bot_username = me.username or os.getenv("BOT_USERNAME") or ""
            deal_link = ""
            if bot_username:
                deal_link = f"https://t.me/{bot_username}?start=deal={public_id}"

            if locale == "ru":
                success_text = (
                    f"✅ Сделка #{deal_id} успешно создана!\n\n"
                    f"💰 Сумма: {amount_display} {currency_symbol}\n"
                    f"🔄 Оплата: {payment_method.upper()}\n"
                    f"🎁 Товар: {data['item_description']}\n\n"
                )
                if deal_link:
                    success_text += f"🔗 Ссылка для покупателя:\n{deal_link}\n\n"
                else:
                    success_text += "⚠️ Не удалось определить username бота для ссылки. Задай `BOT_USERNAME` в `.env`.\n\n"
                success_text += "Ожидайте подтверждения от контрагента. Статус можно проверить в разделе «Мои сделки»."
            else:
                success_text = (
                    f"✅ Deal #{deal_id} created successfully!\n\n"
                    f"💰 Amount: {amount_display} {currency_symbol}\n"
                    f"🔄 Payment: {payment_method.upper()}\n"
                    f"🎁 Item: {data['item_description']}\n\n"
                )
                if deal_link:
                    success_text += f"🔗 Link for buyer:\n{deal_link}\n\n"
                else:
                    success_text += "⚠️ Can't determine bot username for link. Set `BOT_USERNAME` in `.env`.\n\n"
                success_text += "Waiting for counterparty confirmation. Check status in «My deals» section."

            await send_callback_message(callback, success_text, reply_markup=about_return_to_menu(locale))

        except Exception as e:
            logging.error(f"Failed to create deal for user {callback.from_user.id}: {e}")
            await send_callback_message(
                callback,
                "❌ Произошла ошибка при создании сделки. Попробуйте позже." if locale == "ru"
                else "❌ Failed to create deal. Please try again later.",
            )
        await state.clear()
        return

    # Отмена сделки
    await send_callback_message(
        callback,
        "❌ Сделка отменена." if locale == "ru" else "❌ Deal cancelled.",
        reply_markup=about_return_to_menu(locale),
    )
    await state.clear()


async def on_buyer_paid(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)

    data = callback.data or ""
    public_id = data.split(":", 1)[1] if ":" in data else ""
    public_id = public_id.strip()
    if not public_id:
        await send_callback_message(callback, "❌ Некорректная сделка.")
        return

    deal = get_deal_by_public_id(public_id)
    if not deal:
        await send_callback_message(callback, "❌ Сделка не найдена.")
        return

    status = (deal["status"] or "").lower()
    if status in ("completed", "paid", "done", "success"):
        amount = float(deal["amount"])
        currency = (deal["currency"] or "").strip()
        amount_display = f"{amount:.9f}".rstrip("0").rstrip(".") if currency == "TON" else f"{amount:.2f}"
        currency_label = "TON" if currency == "TON" else ("₽" if currency == "RUB" else (currency or "—"))
        item = (deal["item_description"] or "").strip() or "."
        await send_callback_message(
            callback,
            f"🛒 Сделка {public_id}\n"
            f"📋 Товар: {item}\n"
            f"💵 Сумма: {amount_display} {currency_label}\n\n"
            f"✅ Сделка уже оплачена и завершена.",
        )
        return

    attach_buyer_to_deal(public_id, callback.from_user.id)

    buyer_profile = get_user_profile(callback.from_user.id)
    buyer_balance = float(buyer_profile["balance"] or 0.0) if buyer_profile else 0.0
    amount = float(deal["amount"])
    currency = (deal["currency"] or "").strip()
    amount_display = f"{amount:.9f}".rstrip("0").rstrip(".") if currency == "TON" else f"{amount:.2f}"
    currency_label = "TON" if currency == "TON" else ("₽" if currency == "RUB" else (currency or "—"))

    debit_amount_rub = amount * TON_RATE_RUB if currency == "TON" else amount
    new_balance = debit_user_balance(callback.from_user.id, debit_amount_rub)
    if new_balance is None:
        await send_callback_message(
            callback,
            "❌ Недостаточно средств на балансе!\n\n"
            f"💰 Ваш баланс: {buyer_balance:.1f} ₽\n"
            f"💵 Сумма к оплате: {amount_display} {currency_label}",
            reply_markup=about_return_to_menu(locale),
        )
        return

    update_deal_status(int(deal["id"]), "completed")

    await send_callback_message(
        callback,
        "✅ Продавец уведомлен об оплате. Ожидайте передачи товара.\n\n"
        f"💰 Ваш баланс: {new_balance:.1f} ₽",
        reply_markup=about_return_to_menu(locale),
    )

    item = (deal["item_description"] or "").strip() or "."
    try:
        seller_locale = get_user_locale(int(deal["user_id"])) or "ru"
        await callback.bot.send_message(
            int(deal["user_id"]),
            "💰 Покупатель  оплатил сделку!\n\n"
            f"ID сделки: {public_id}\n"
            f"Сумма: {amount_display} {currency_label}\n"
            f"Товар: {item}\n\n"
            "✅ Покупатель оплатил товар, средства списаны с его баланса и зарезервированы.\n\n"
            "‼️ Передайте товар администратору XPay @Dirdols, после вам будут автоматически перечислены деньги на реквизиты указанные в профиле!\n\n"
            "❌ Внимание: в случае передачи подарка на аккаунт покупателя, средства будут заморожены и сделка будет отменена, если покупатель просит передать нфт на его аккаунт - это мошенник!",
            reply_markup=about_return_to_menu(seller_locale),
        )
    except Exception as e:
        logging.warning(f"Failed to notify seller for deal {public_id}: {e}")


async def on_add_money(message: Message) -> None:
    if not message.from_user:
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await send_user_message(
            message,
            "❌ Укажите сумму после команды, например: /money 50000",
        )
        return

    try:
        amount = float(parts[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await send_user_message(
            message,
            "❌ Неверная сумма. Используйте положительное число, например: /money 50000",
        )
        return

    # гарантируем, что пользователь есть в БД
    upsert_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )

    new_balance = credit_user_balance(message.from_user.id, amount)
    if new_balance is None:
        await send_user_message(
            message,
            "❌ Не удалось обновить баланс. Попробуйте позже.",
        )
        return

    await send_user_message(
        message,
        f"💰 На ваш счёт зачислено {amount:.1f} ₽\n\n"
        f"💼 Текущий баланс: {new_balance:.1f} ₽",
    )

async def on_nav_back(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    locale = get_user_locale(callback.from_user.id) or guess_locale_from_tg(callback.from_user.language_code)
    await send_callback_message(callback, t(locale, "main_menu"), reply_markup=main_menu_kb(locale))

async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    load_dotenv()

    token = os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or "8798624773:AAEdDIzIyKgtguK1Kdko-diKumYowuD8CD0"
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в окружении/.env")

    init_db()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(on_start, CommandStart())
    dp.message.register(on_add_money, Command("money"))
    dp.callback_query.register(on_language_choose, F.data.startswith("lang:"))
    dp.callback_query.register(on_menu_click, F.data.startswith("menu:"))
    dp.callback_query.register(on_requisites_action, F.data.startswith("req:"))
    dp.message.register(on_enter_ton, RequisitesForm.ton)
    dp.message.register(on_enter_card, RequisitesForm.card)
    dp.message.register(on_enter_sbp, RequisitesForm.sbp)
    dp.callback_query.register(on_nav_back, F.data == "nav")
    dp.callback_query.register(on_deal_create,F.data.startswith("deal_create"))
    dp.callback_query.register(on_deal_confirm, F.data.startswith("deal:confirm:"))
    dp.callback_query.register(on_buyer_paid, F.data.startswith("deal_buyer_paid:"))

    dp.message.register(on_enter_payment_amount, DealForm.ton_amount)
    dp.message.register(on_enter_payment_amount, DealForm.card_amount)
    dp.message.register(on_enter_payment_amount, DealForm.sbp_amount)
    dp.message.register(on_enter_deal_item, DealForm.item_description)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
