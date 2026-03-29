#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║          🌸  IRIS-BOT  —  Telegram Chat Manager             ║
║         Полный аналог Iris с расширенным функционалом        ║
╠══════════════════════════════════════════════════════════════╣
║  Установка:                                                  ║
║    pip install python-telegram-bot==20.7                     ║
║                                                              ║
║  Запуск:                                                     ║
║    BOT_TOKEN=xxx BOT_OWNER=yyy python iris_bot.py            ║
╚══════════════════════════════════════════════════════════════╝

ФУНКЦИОНАЛ:
  👑 Управление правами    — модераторы, права, иерархия
  🛡 Антиспам / Антифлуд  — умное определение, авто-действия
  ⚠️  Система варнов       — настраиваемый лимит и действие
  🔇 Мут / Бан / Кик      — с временными ограничениями
  🔒 Локи                 — запрет типов контента
  🔗 Антилинк             — блокировка ссылок и инвайтов
  ⬛ Чёрный список        — слова/фразы с авто-действием
  📝 Заметки              — сохранение и вызов через #тег
  🎯 Фильтры              — авто-ответы на ключевые слова
  🎉 Приветствие          — кастомное с кнопками
  🤖 Капча                — верификация новых участников
  📌 Пины                 — управление закреплёнными
  📋 Правила              — /rules с форматированием
  📊 Статистика           — /stats чата и участников
  🌐 Мультиязычность      — RU / EN
  💤 AFK-статус           — отметка отсутствия
  🗑 Purge                — массовое удаление сообщений
  🔕 Slowmode             — встроенный медленный режим
  📣 Логирование          — события в отдельный канал
  🚨 Репорт               — жалобы пользователей
  📎 ID / Info            — информация о юзерах и чате
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from telegram import (
    Bot, Update, User, Chat, Message,
    ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMember, ChatMemberAdministrator, ChatMemberOwner,
    ChatMemberMember, ChatMemberRestricted, ChatMemberBanned,
)
from telegram.constants import ParseMode, ChatMemberStatus, ChatType
from telegram.error import TelegramError, BadRequest, Forbidden
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, ConversationHandler,
    filters, ContextTypes,
)

# ══════════════════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════════════
BOT_TOKEN  = os.getenv("BOT_TOKEN",  "8698186618:AAE4fxuq1ZYOlNuedNkuqSvDKMNuHadd_9Q")
BOT_OWNER  = int(os.getenv("BOT_OWNER", "7950038145"))   # Ваш Telegram ID
DATA_FILE  = "iris_data.json"
LOG_FILE   = "iris.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("IrisBot")

# ══════════════════════════════════════════════════════════════
#  БАЗА ДАННЫХ (JSON — без внешних зависимостей)
# ══════════════════════════════════════════════════════════════
def load_db() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(db: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

DB: dict = load_db()

def chat_db(chat_id: int) -> dict:
    cid = str(chat_id)
    if cid not in DB:
        DB[cid] = _default_chat()
        save_db(DB)
    return DB[cid]

def _default_chat() -> dict:
    return {
        "settings": {
            # Приветствие / прощание
            "welcome_enabled": True,
            "welcome_text": "👋 Добро пожаловать, {mention}!\nРады видеть тебя в <b>{chat}</b>!",
            "welcome_buttons": [],         # [[{"text":"..","url":".."}]]
            "welcome_delete_after": 0,     # секунды (0 = не удалять)
            "goodbye_enabled": False,
            "goodbye_text": "👋 {name} покинул(а) нас.",
            # Капча
            "captcha": False,
            "captcha_timeout": 90,
            "captcha_kick": True,
            # Анти-флуд
            "antiflood": False,
            "antiflood_limit": 5,
            "antiflood_window": 5,
            "antiflood_action": "mute",    # delete | mute | kick | ban
            "antiflood_mute_time": 300,
            # Анти-ссылки
            "antilink": False,
            "antilink_action": "delete",   # delete | warn | mute | kick | ban
            "antilink_whitelist": [],
            # Антиспам (дублирующиеся сообщения)
            "antispam": False,
            "antispam_action": "mute",
            # Варны
            "max_warns": 3,
            "warn_action": "kick",         # kick | ban | mute
            "warn_mute_time": 3600,
            # Медленный режим (бот-сторона)
            "slowmode": 0,
            # Правила
            "rules": "",
            # Лог-канал
            "log_channel": None,
            # Язык
            "language": "ru",
            # Авто-удаление системных сообщений о вступлении/выходе
            "clean_service": False,
            # Репорты
            "report_enabled": True,
            "report_admin_only": False,
        },
        "moderators": [],      # user_ids с расширенными правами
        "warns":      {},      # {user_id: [{"reason":..,"by":..,"date":..}]}
        "notes":      {},      # {name: {"text":..,"file_id":..,"type":..}}
        "filters":    {},      # {keyword: {"text":..,"buttons":..}}
        "blacklist":  [],      # [word/phrase]
        "blacklist_action": "delete",
        "blacklist_warns": False,
        "locks": {
            "text": False, "media": False, "photo": False, "video": False,
            "audio": False, "document": False, "sticker": False, "gif": False,
            "voice": False, "video_note": False, "contact": False,
            "location": False, "poll": False, "forward": False,
            "link": False, "invite": False, "game": False, "inline": False,
        },
        "flood_tracker":   {},   # {user_id: [timestamps]}
        "captcha_pending": {},   # {user_id: {"msg_id":..,"timeout_at":..}}
        "afk":             {},   # {user_id: {"reason":..,"since":..}}
        "disabled":        [],   # отключённые команды
        "slowmode_tracker":{},   # {user_id: last_message_time}
        "stats": {
            "messages": 0, "joins": 0, "leaves": 0,
            "bans": 0, "kicks": 0, "mutes": 0, "warns_total": 0,
            "deleted": 0,
        },
    }

# ══════════════════════════════════════════════════════════════
#  ЛОКАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════
T = {
    "ru": {
        "no_perm":       "❌ У тебя нет прав для этой команды.",
        "only_groups":   "❌ Эта команда только для групп.",
        "user_not_found":"❌ Пользователь не найден. Ответь на его сообщение или укажи @username / ID.",
        "cant_action_admin":"❌ Нельзя применить действие к администратору.",
        "cant_action_self":"❌ Нельзя применить это к себе.",
        "done":          "✅ Готово.",
        "warn_added":    "⚠️ <b>{name}</b> получил предупреждение <b>{cur}/{max}</b>\nПричина: {reason}",
        "warn_action":   "🔨 Достигнут лимит варнов — применено: <b>{action}</b>",
        "warn_cleared":  "✅ Варны <b>{name}</b> сброшены.",
        "warns_list":    "📋 Варны <b>{name}</b> ({cur}/{max}):\n{list}",
        "no_warns":      "✅ У <b>{name}</b> нет варнов.",
        "banned":        "🔨 <b>{name}</b> забанен.\nПричина: {reason}",
        "unbanned":      "✅ <b>{name}</b> разбанен.",
        "kicked":        "👢 <b>{name}</b> кикнут.\nПричина: {reason}",
        "muted":         "🔇 <b>{name}</b> замьючен{time}.\nПричина: {reason}",
        "unmuted":       "🔊 <b>{name}</b> размьючен.",
        "pinned":        "📌 Сообщение закреплено.",
        "unpinned":      "📌 Сообщение откреплено.",
        "rules_empty":   "📋 Правила ещё не установлены.",
        "rules_set":     "✅ Правила обновлены.",
        "note_saved":    "📝 Заметка <code>#{name}</code> сохранена.",
        "note_deleted":  "🗑 Заметка <code>#{name}</code> удалена.",
        "note_notfound": "❌ Заметка <code>#{name}</code> не найдена.",
        "notes_empty":   "📝 Заметок нет.",
        "filter_saved":  "🎯 Фильтр <code>{kw}</code> сохранён.",
        "filter_deleted":"🗑 Фильтр <code>{kw}</code> удалён.",
        "filter_notfound":"❌ Фильтр <code>{kw}</code> не найден.",
        "filters_empty": "🎯 Фильтров нет.",
        "bl_added":      "⬛ Слово добавлено в чёрный список.",
        "bl_removed":    "✅ Слово удалено из чёрного списка.",
        "bl_empty":      "⬛ Чёрный список пуст.",
        "bl_triggered":  "⬛ Обнаружено запрещённое слово.",
        "lock_on":       "🔒 Заблокировано: <b>{lock}</b>",
        "lock_off":      "🔓 Разблокировано: <b>{lock}</b>",
        "locked_msg":    "🔒 Этот тип контента заблокирован в чате.",
        "mod_added":     "⭐ <b>{name}</b> назначен модератором.",
        "mod_removed":   "✅ <b>{name}</b> снят с должности модератора.",
        "mod_list":      "⭐ Модераторы чата:\n{list}",
        "mod_empty":     "⭐ Модераторов нет.",
        "afk_set":       "💤 <b>{name}</b> ушёл(ла) в AFK{reason}",
        "afk_back":      "👋 <b>{name}</b> вернулся(лась)!",
        "afk_mention":   "💤 <b>{name}</b> сейчас AFK{reason}",
        "purge_done":    "🗑 Удалено {count} сообщений.",
        "report_sent":   "🚨 Жалоба отправлена администраторам.",
        "report_msg":    "🚨 <b>Жалоба</b>\nЧат: {chat}\nОт: {from_user}\nНа: {on_user}\nСообщение: {msg_link}",
        "antiflood_msg": "⚡ <b>{name}</b> флудит! Действие: <b>{action}</b>",
        "antilink_msg":  "🔗 Ссылки запрещены в этом чате.",
        "antispam_msg":  "♻️ Дублирующиеся сообщения запрещены.",
        "captcha_msg":   "🤖 <b>{mention}</b>, нажми кнопку ниже в течение {timeout} сек., чтобы подтвердить, что ты человек!",
        "captcha_pass":  "✅ Проверка пройдена! Добро пожаловать!",
        "captcha_fail":  "❌ <b>{name}</b> не прошёл капчу и был кикнут.",
        "slowmode_msg":  "🐌 Медленный режим: подожди {sec} сек.",
        "setting_on":    "✅ <b>{setting}</b> включено.",
        "setting_off":   "❌ <b>{setting}</b> выключено.",
    },
    "en": {
        "no_perm":       "❌ You don't have permission for this command.",
        "only_groups":   "❌ This command is for groups only.",
        "user_not_found":"❌ User not found. Reply to their message or provide @username / ID.",
        "cant_action_admin":"❌ Cannot perform action on an administrator.",
        "cant_action_self":"❌ Cannot perform this action on yourself.",
        "done":          "✅ Done.",
        "warn_added":    "⚠️ <b>{name}</b> received warning <b>{cur}/{max}</b>\nReason: {reason}",
        "warn_action":   "🔨 Warn limit reached — action applied: <b>{action}</b>",
        "warn_cleared":  "✅ Warns for <b>{name}</b> cleared.",
        "warns_list":    "📋 Warns for <b>{name}</b> ({cur}/{max}):\n{list}",
        "no_warns":      "✅ <b>{name}</b> has no warnings.",
        "banned":        "🔨 <b>{name}</b> banned.\nReason: {reason}",
        "unbanned":      "✅ <b>{name}</b> unbanned.",
        "kicked":        "👢 <b>{name}</b> kicked.\nReason: {reason}",
        "muted":         "🔇 <b>{name}</b> muted{time}.\nReason: {reason}",
        "unmuted":       "🔊 <b>{name}</b> unmuted.",
        "pinned":        "📌 Message pinned.",
        "unpinned":      "📌 Message unpinned.",
        "rules_empty":   "📋 Rules not set yet.",
        "rules_set":     "✅ Rules updated.",
        "note_saved":    "📝 Note <code>#{name}</code> saved.",
        "note_deleted":  "🗑 Note <code>#{name}</code> deleted.",
        "note_notfound": "❌ Note <code>#{name}</code> not found.",
        "notes_empty":   "📝 No notes.",
        "filter_saved":  "🎯 Filter <code>{kw}</code> saved.",
        "filter_deleted":"🗑 Filter <code>{kw}</code> deleted.",
        "filter_notfound":"❌ Filter <code>{kw}</code> not found.",
        "filters_empty": "🎯 No filters.",
        "bl_added":      "⬛ Word added to blacklist.",
        "bl_removed":    "✅ Word removed from blacklist.",
        "bl_empty":      "⬛ Blacklist is empty.",
        "bl_triggered":  "⬛ Forbidden word detected.",
        "lock_on":       "🔒 Locked: <b>{lock}</b>",
        "lock_off":      "🔓 Unlocked: <b>{lock}</b>",
        "locked_msg":    "🔒 This content type is locked in this chat.",
        "mod_added":     "⭐ <b>{name}</b> appointed as moderator.",
        "mod_removed":   "✅ <b>{name}</b> removed from moderators.",
        "mod_list":      "⭐ Chat moderators:\n{list}",
        "mod_empty":     "⭐ No moderators.",
        "afk_set":       "💤 <b>{name}</b> is now AFK{reason}",
        "afk_back":      "👋 <b>{name}</b> is back!",
        "afk_mention":   "💤 <b>{name}</b> is AFK{reason}",
        "purge_done":    "🗑 Deleted {count} messages.",
        "report_sent":   "🚨 Report sent to administrators.",
        "report_msg":    "🚨 <b>Report</b>\nChat: {chat}\nFrom: {from_user}\nOn: {on_user}\nMessage: {msg_link}",
        "antiflood_msg": "⚡ <b>{name}</b> is flooding! Action: <b>{action}</b>",
        "antilink_msg":  "🔗 Links are not allowed in this chat.",
        "antispam_msg":  "♻️ Duplicate messages are not allowed.",
        "captcha_msg":   "🤖 <b>{mention}</b>, click the button below within {timeout} sec to verify you're human!",
        "captcha_pass":  "✅ Verification passed! Welcome!",
        "captcha_fail":  "❌ <b>{name}</b> failed captcha and was kicked.",
        "slowmode_msg":  "🐌 Slow mode: wait {sec} sec.",
        "setting_on":    "✅ <b>{setting}</b> enabled.",
        "setting_off":   "❌ <b>{setting}</b> disabled.",
    },
}

def tr(chat_id: int, key: str, **kwargs) -> str:
    lang = chat_db(chat_id).get("settings", {}).get("language", "ru")
    tmpl = T.get(lang, T["ru"]).get(key, T["ru"].get(key, key))
    return tmpl.format(**kwargs)

# ══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════
def mention(user: User) -> str:
    name = user.full_name or user.username or str(user.id)
    return f'<a href="tg://user?id={user.id}">{name}</a>'

def user_link(user: User) -> str:
    return mention(user)

def parse_time(s: str) -> Optional[int]:
    """Парсит '30s', '5m', '2h', '1d' → секунды."""
    m = re.fullmatch(r"(\d+)([smhd]?)", s.strip().lower())
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400, "": 1}[u]

def fmt_time(seconds: int) -> str:
    if seconds < 60:    return f"{seconds}с"
    if seconds < 3600:  return f"{seconds//60}м"
    if seconds < 86400: return f"{seconds//3600}ч"
    return f"{seconds//86400}д"

async def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[User]:
    msg = update.effective_message
    if msg.reply_to_message:
        return msg.reply_to_message.from_user
    if context.args:
        arg = context.args[0]
        try:
            uid = int(arg)
            return await context.bot.get_chat(uid)
        except (ValueError, TelegramError):
            try:
                username = arg.lstrip("@")
                return await context.bot.get_chat(f"@{username}")
            except TelegramError:
                return None
    return None

async def get_member_status(bot: Bot, chat_id: int, user_id: int) -> Optional[ChatMember]:
    try:
        return await bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        return None

async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    if user_id == BOT_OWNER:
        return True
    m = await get_member_status(bot, chat_id, user_id)
    return m is not None and m.status in (
        ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
    )

async def is_mod_or_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    if await is_admin(bot, chat_id, user_id):
        return True
    data = chat_db(chat_id)
    return user_id in data.get("moderators", [])

async def bot_can(bot: Bot, chat_id: int, perm: str) -> bool:
    me = await get_member_status(bot, chat_id, bot.id)
    if me is None:
        return False
    return getattr(me, perm, False)

async def safe_delete(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramError:
        pass

async def send_log(bot: Bot, chat_id: int, text: str):
    data = chat_db(chat_id)
    log_ch = data["settings"].get("log_channel")
    if log_ch:
        try:
            await bot.send_message(log_ch, text, parse_mode=ParseMode.HTML)
        except TelegramError:
            pass

# ══════════════════════════════════════════════════════════════
#  ДЕКОРАТОРЫ ПРАВ
# ══════════════════════════════════════════════════════════════
def group_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type == ChatType.PRIVATE:
            await update.effective_message.reply_text(
                tr(update.effective_chat.id, "only_groups")
            )
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper

def admin_only(func):
    @group_only
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid   = update.effective_user.id
        cid   = update.effective_chat.id
        if not await is_admin(ctx.bot, cid, uid):
            await update.effective_message.reply_text(tr(cid, "no_perm"))
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper

def mod_or_admin(func):
    @group_only
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cid = update.effective_chat.id
        if not await is_mod_or_admin(ctx.bot, cid, uid):
            await update.effective_message.reply_text(tr(cid, "no_perm"))
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper

# ══════════════════════════════════════════════════════════════
#  /START /HELP
# ══════════════════════════════════════════════════════════════
HELP_TEXT = """
🌸 <b>IRIS BOT — Менеджер чата</b>

<b>👑 Права и модераторы</b>
/addmod @user — назначить модератора
/removemod @user — снять модератора
/modlist — список модераторов
/promote @user — повысить до админа (нужны права)
/demote @user — понизить

<b>🔨 Модерация</b>
/ban @user [причина] — забанить
/unban @user — разбанить
/kick @user [причина] — кикнуть
/mute @user [время] [причина] — замьютить
/unmute @user — размьютить
/warn @user [причина] — варн
/unwarn @user — снять 1 варн
/warnlist @user — список варнов
/clearwarns @user — сбросить все варны
/ro @user [время] — только-чтение
/unro @user — снять только-чтение

<b>⚠️ Настройка варнов</b>
/setwarnlimit [N] — максимум варнов
/setwarnaction [kick|ban|mute] — действие по лимиту

<b>📌 Пины</b>
/pin [silent] — закрепить (ответом)
/unpin — открепить последнее
/unpinall — открепить все

<b>🗑 Удаление</b>
/del — удалить (ответом)
/purge [N] — удалить N сообщений
/purge — удалить до отмеченного

<b>📝 Заметки</b>
/note [имя] [текст] — сохранить заметку
/get [имя] или #имя — получить заметку
/delnote [имя] — удалить заметку
/notes — список заметок

<b>🎯 Фильтры</b>
/filter [слово] [ответ] — добавить фильтр
/stop [слово] — удалить фильтр
/filters — список фильтров

<b>⬛ Чёрный список</b>
/blacklist — список
/addblacklist [слово] — добавить
/rmblacklist [слово] — удалить
/setblacklistaction [delete|warn|kick|ban] — действие

<b>🔒 Локи (ограничения типов)</b>
/lock [тип] — заблокировать
/unlock [тип] — разблокировать
/locks — список
<i>Типы: text photo video audio doc sticker gif voice vnote contact location poll forward link invite game</i>

<b>🔗 Антилинк</b>
/antilink [on|off] — вкл/выкл
/setantilinkaction [delete|warn|mute|kick|ban]
/alwhitelist [домен] — в белый список
/alrmwhitelist [домен]

<b>⚡ Антифлуд</b>
/antiflood [on|off]
/setfloodlimit [N] — сообщений за окно
/setfloodaction [delete|mute|kick|ban]
/setfloodtime [секунды] — временное окно

<b>🎉 Приветствие</b>
/setwelcome [текст] — установить текст
/welcome [on|off]
/resetwelcome — сбросить
/setgoodbye [текст] — прощание
/goodbye [on|off]
<i>Переменные: {mention} {name} {username} {chat} {id} {count}</i>

<b>🤖 Капча</b>
/captcha [on|off]
/setcaptchatimeout [секунды]

<b>📋 Правила</b>
/rules — показать правила
/setrules [текст] — установить
/clearrules — очистить

<b>🐌 Медленный режим</b>
/slowmode [секунды|off]

<b>💤 AFK</b>
/afk [причина] — уйти в AFK
/back — вернуться

<b>📊 Статистика</b>
/stats — статистика чата
/info @user — информация о пользователе
/chatinfo — информация о чате
/id — узнать ID

<b>📣 Логирование</b>
/setlog [id канала] — канал для логов
/unsetlog — отключить логи

<b>🚨 Репорты</b>
/report — пожаловаться (ответом)
/reports [on|off]

<b>🌐 Язык</b>
/setlang [ru|en] — язык бота

<b>🔕 Прочее</b>
/disable [команда] — отключить команду
/enable [команда] — включить команду
/cleanservice [on|off] — удалять системные сообщения
/antispam [on|off]
"""

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "🌸 Привет! Я <b>Iris Bot</b> — менеджер групповых чатов.\n\n"
            "Добавь меня в группу и дай права администратора!\n\n"
            "Используй /help для списка команд.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text("🌸 Iris Bot активен! /help — список команд.")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📖 Полная справка", callback_data="help_full"),
    ]])
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            "🌸 <b>Iris Bot</b> — справка отправлена в ЛС!",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )

async def cb_help_full(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await ctx.bot.send_message(q.from_user.id, HELP_TEXT, parse_mode=ParseMode.HTML)
    except Forbidden:
        await q.answer("Сначала напиши мне в личку!", show_alert=True)

# ══════════════════════════════════════════════════════════════
#  МОДЕРАТОРЫ
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_addmod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    if await is_admin(ctx.bot, cid, target.id):
        return await update.message.reply_text("ℹ️ Пользователь уже является администратором.")
    data = chat_db(cid)
    if target.id not in data["moderators"]:
        data["moderators"].append(target.id)
        save_db(DB)
    await update.message.reply_text(
        tr(cid, "mod_added", name=target.full_name), parse_mode=ParseMode.HTML
    )
    await send_log(ctx.bot, cid,
        f"⭐ Модератор назначен: {mention(target)} | Кем: {mention(update.effective_user)}")

@admin_only
async def cmd_removemod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    data = chat_db(cid)
    if target.id in data["moderators"]:
        data["moderators"].remove(target.id)
        save_db(DB)
    await update.message.reply_text(
        tr(cid, "mod_removed", name=target.full_name), parse_mode=ParseMode.HTML
    )

@group_only
async def cmd_modlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    data = chat_db(cid)
    mods = data.get("moderators", [])
    if not mods:
        return await update.message.reply_text(tr(cid, "mod_empty"), parse_mode=ParseMode.HTML)
    lines = []
    for uid in mods:
        try:
            u = await ctx.bot.get_chat(uid)
            lines.append(f"• {mention(u)}")
        except TelegramError:
            lines.append(f"• ID: {uid}")
    await update.message.reply_text(
        tr(cid, "mod_list", list="\n".join(lines)), parse_mode=ParseMode.HTML
    )

# ══════════════════════════════════════════════════════════════
#  ПОВЫШЕНИЕ / ПОНИЖЕНИЕ (стандартные права TG)
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_promote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    try:
        await ctx.bot.promote_chat_member(
            cid, target.id,
            can_delete_messages=True, can_restrict_members=True,
            can_pin_messages=True, can_invite_users=True,
            can_manage_chat=True, can_manage_video_chats=True,
        )
        await update.message.reply_text(
            f"✅ {mention(target)} повышен до администратора!", parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

@admin_only
async def cmd_demote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    try:
        await ctx.bot.promote_chat_member(
            cid, target.id,
            can_delete_messages=False, can_restrict_members=False,
            can_pin_messages=False, can_invite_users=False,
            can_manage_chat=False, can_manage_video_chats=False,
        )
        await update.message.reply_text(
            f"✅ {mention(target)} понижен.", parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ══════════════════════════════════════════════════════════════
#  БАН
# ══════════════════════════════════════════════════════════════
@mod_or_admin
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    caller = update.effective_user
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    if target.id == caller.id:
        return await update.message.reply_text(tr(cid, "cant_action_self"))
    if await is_admin(ctx.bot, cid, target.id):
        return await update.message.reply_text(tr(cid, "cant_action_admin"))
    reason = " ".join(ctx.args[1:]) if ctx.args and len(ctx.args) > 1 else "—"
    if update.message.reply_to_message and not ctx.args:
        reason = " ".join(ctx.args) if ctx.args else "—"
    try:
        await ctx.bot.ban_chat_member(cid, target.id)
        chat_db(cid)["stats"]["bans"] += 1
        save_db(DB)
        await update.message.reply_text(
            tr(cid, "banned", name=mention(target), reason=reason),
            parse_mode=ParseMode.HTML,
        )
        await send_log(ctx.bot, cid,
            f"🔨 Бан: {mention(target)} | Кем: {mention(caller)} | Причина: {reason}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

@mod_or_admin
async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    try:
        await ctx.bot.unban_chat_member(cid, target.id, only_if_banned=True)
        await update.message.reply_text(
            tr(cid, "unbanned", name=mention(target)), parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ══════════════════════════════════════════════════════════════
#  КИК
# ══════════════════════════════════════════════════════════════
@mod_or_admin
async def cmd_kick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    caller = update.effective_user
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    if target.id == caller.id:
        return await update.message.reply_text(tr(cid, "cant_action_self"))
    if await is_admin(ctx.bot, cid, target.id):
        return await update.message.reply_text(tr(cid, "cant_action_admin"))
    reason = " ".join(ctx.args[1:]) if ctx.args and len(ctx.args) > 1 else "—"
    try:
        await ctx.bot.ban_chat_member(cid, target.id)
        await ctx.bot.unban_chat_member(cid, target.id)
        chat_db(cid)["stats"]["kicks"] += 1
        save_db(DB)
        await update.message.reply_text(
            tr(cid, "kicked", name=mention(target), reason=reason),
            parse_mode=ParseMode.HTML,
        )
        await send_log(ctx.bot, cid,
            f"👢 Кик: {mention(target)} | Кем: {mention(caller)} | Причина: {reason}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ══════════════════════════════════════════════════════════════
#  МЮТ
# ══════════════════════════════════════════════════════════════
async def _mute_user(bot: Bot, cid: int, uid: int, until: Optional[datetime] = None):
    await bot.restrict_chat_member(
        cid, uid,
        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        ),
        until_date=until,
    )

async def _unmute_user(bot: Bot, cid: int, uid: int):
    await bot.restrict_chat_member(
        cid, uid,
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_documents=True,
            can_send_audios=True,
            can_send_voice_notes=True,
            can_send_video_notes=True,
        ),
    )

@mod_or_admin
async def cmd_mute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    caller = update.effective_user
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    if target.id == caller.id:
        return await update.message.reply_text(tr(cid, "cant_action_self"))
    if await is_admin(ctx.bot, cid, target.id):
        return await update.message.reply_text(tr(cid, "cant_action_admin"))

    args = ctx.args or []
    if update.message.reply_to_message:
        args = list(args)  # аргументы без первого (target)
    else:
        args = args[1:]

    duration = None
    time_str  = ""
    reason    = "—"
    if args:
        secs = parse_time(args[0])
        if secs:
            duration = datetime.now(timezone.utc) + timedelta(seconds=secs)
            time_str = f" на {fmt_time(secs)}"
            reason = " ".join(args[1:]) or "—"
        else:
            reason = " ".join(args)

    try:
        await _mute_user(ctx.bot, cid, target.id, duration)
        chat_db(cid)["stats"]["mutes"] += 1
        save_db(DB)
        await update.message.reply_text(
            tr(cid, "muted", name=mention(target), time=time_str, reason=reason),
            parse_mode=ParseMode.HTML,
        )
        await send_log(ctx.bot, cid,
            f"🔇 Мут: {mention(target)}{time_str} | Кем: {mention(caller)} | Причина: {reason}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

@mod_or_admin
async def cmd_unmute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    try:
        await _unmute_user(ctx.bot, cid, target.id)
        await update.message.reply_text(
            tr(cid, "unmuted", name=mention(target)), parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

@mod_or_admin
async def cmd_ro(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только-чтение (полный мют, включая медиа)"""
    await cmd_mute(update, ctx)

@mod_or_admin
async def cmd_unro(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_unmute(update, ctx)

# ══════════════════════════════════════════════════════════════
#  СИСТЕМА ВАРНОВ
# ══════════════════════════════════════════════════════════════
async def _apply_warn_action(bot: Bot, cid: int, target: User, action: str, mute_time: int):
    if action == "ban":
        await bot.ban_chat_member(cid, target.id)
    elif action == "kick":
        await bot.ban_chat_member(cid, target.id)
        await bot.unban_chat_member(cid, target.id)
    elif action == "mute":
        until = datetime.now(timezone.utc) + timedelta(seconds=mute_time)
        await _mute_user(bot, cid, target.id, until)

@mod_or_admin
async def cmd_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    caller = update.effective_user
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    if target.id == caller.id:
        return await update.message.reply_text(tr(cid, "cant_action_self"))
    if await is_admin(ctx.bot, cid, target.id):
        return await update.message.reply_text(tr(cid, "cant_action_admin"))

    args = list(ctx.args or [])
    if not update.message.reply_to_message and args:
        args = args[1:]
    reason = " ".join(args) or "—"

    data     = chat_db(cid)
    uid      = str(target.id)
    warns    = data["warns"].setdefault(uid, [])
    warns.append({"reason": reason, "by": caller.id, "date": time.time()})
    max_w    = data["settings"]["max_warns"]
    cur_w    = len(warns)
    data["stats"]["warns_total"] += 1
    save_db(DB)

    text = tr(cid, "warn_added", name=mention(target), cur=cur_w, max=max_w, reason=reason)
    if cur_w >= max_w:
        action = data["settings"]["warn_action"]
        mtime  = data["settings"]["warn_mute_time"]
        try:
            await _apply_warn_action(ctx.bot, cid, target, action, mtime)
            text += "\n" + tr(cid, "warn_action", action=action)
            data["warns"][uid] = []  # сбрасываем после применения
            save_db(DB)
        except TelegramError:
            pass
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    await send_log(ctx.bot, cid,
        f"⚠️ Варн {cur_w}/{max_w}: {mention(target)} | Кем: {mention(caller)} | Причина: {reason}")

@mod_or_admin
async def cmd_unwarn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    data = chat_db(cid)
    uid  = str(target.id)
    if data["warns"].get(uid):
        data["warns"][uid].pop()
        save_db(DB)
    await update.message.reply_text(
        f"✅ Один варн снят у {mention(target)}.", parse_mode=ParseMode.HTML
    )

@mod_or_admin
async def cmd_clearwarns(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx)
    if not target:
        return await update.message.reply_text(tr(cid, "user_not_found"))
    data = chat_db(cid)
    data["warns"][str(target.id)] = []
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "warn_cleared", name=mention(target)), parse_mode=ParseMode.HTML
    )

@group_only
async def cmd_warnlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx) or update.effective_user
    data   = chat_db(cid)
    uid    = str(target.id)
    warns  = data["warns"].get(uid, [])
    max_w  = data["settings"]["max_warns"]
    if not warns:
        return await update.message.reply_text(
            tr(cid, "no_warns", name=mention(target)), parse_mode=ParseMode.HTML
        )
    lines = "\n".join(
        f"{i+1}. {w['reason']} ({datetime.fromtimestamp(w['date']).strftime('%d.%m.%Y')})"
        for i, w in enumerate(warns)
    )
    await update.message.reply_text(
        tr(cid, "warns_list", name=mention(target), cur=len(warns), max=max_w, list=lines),
        parse_mode=ParseMode.HTML,
    )

@admin_only
async def cmd_setwarnlimit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❌ Использование: /setwarnlimit [число]")
    chat_db(cid)["settings"]["max_warns"] = int(ctx.args[0])
    save_db(DB)
    await update.message.reply_text(f"✅ Лимит варнов: <b>{ctx.args[0]}</b>", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_setwarnaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    valid = ["kick", "ban", "mute"]
    if not ctx.args or ctx.args[0] not in valid:
        return await update.message.reply_text(f"❌ Использование: /setwarnaction [{' | '.join(valid)}]")
    chat_db(cid)["settings"]["warn_action"] = ctx.args[0]
    save_db(DB)
    await update.message.reply_text(f"✅ Действие по варнам: <b>{ctx.args[0]}</b>", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  ПИНЫ
# ══════════════════════════════════════════════════════════════
@mod_or_admin
async def cmd_pin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Ответь на сообщение, которое хочешь закрепить.")
    silent = ctx.args and ctx.args[0].lower() in ("silent", "тихо", "s")
    try:
        await ctx.bot.pin_chat_message(
            cid, update.message.reply_to_message.message_id,
            disable_notification=silent,
        )
        await update.message.reply_text(tr(cid, "pinned"))
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

@mod_or_admin
async def cmd_unpin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    try:
        if update.message.reply_to_message:
            await ctx.bot.unpin_chat_message(cid, update.message.reply_to_message.message_id)
        else:
            await ctx.bot.unpin_chat_message(cid)
        await update.message.reply_text(tr(cid, "unpinned"))
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

@admin_only
async def cmd_unpinall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    try:
        await ctx.bot.unpin_all_chat_messages(cid)
        await update.message.reply_text("📌 Все сообщения откреплены.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ══════════════════════════════════════════════════════════════
#  УДАЛЕНИЕ / PURGE
# ══════════════════════════════════════════════════════════════
@mod_or_admin
async def cmd_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await safe_delete(ctx.bot, update.effective_chat.id,
                          update.message.reply_to_message.message_id)
    await safe_delete(ctx.bot, update.effective_chat.id, update.message.message_id)

@mod_or_admin
async def cmd_purge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    msg = update.message

    if msg.reply_to_message:
        from_id = msg.reply_to_message.message_id
        to_id   = msg.message_id
        count   = 0
        ids     = list(range(from_id, to_id + 1))
        # Удаляем по 100 штук (лимит TG)
        for i in range(0, len(ids), 100):
            chunk = ids[i:i+100]
            try:
                await ctx.bot.delete_messages(cid, chunk)
                count += len(chunk)
            except TelegramError:
                for mid in chunk:
                    await safe_delete(ctx.bot, cid, mid)
                    count += 1
        await msg.reply_text(tr(cid, "purge_done", count=count))
    elif ctx.args and ctx.args[0].isdigit():
        n     = min(int(ctx.args[0]), 200)
        start = msg.message_id - n
        ids   = list(range(start, msg.message_id + 1))
        try:
            await ctx.bot.delete_messages(cid, ids)
        except TelegramError:
            for mid in ids:
                await safe_delete(ctx.bot, cid, mid)
        await msg.reply_text(tr(cid, "purge_done", count=n))
    else:
        await msg.reply_text("❌ Ответь на сообщение или укажи количество: /purge [N]")

# ══════════════════════════════════════════════════════════════
#  ЗАМЕТКИ
# ══════════════════════════════════════════════════════════════
@mod_or_admin
async def cmd_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    msg  = update.message
    if not ctx.args:
        return await msg.reply_text("❌ Использование: /note [имя] [текст] или ответом на медиа")
    name = ctx.args[0].lower()
    text = " ".join(ctx.args[1:])
    file_id, ftype = None, None

    if msg.reply_to_message:
        rep = msg.reply_to_message
        if rep.photo:     file_id, ftype = rep.photo[-1].file_id, "photo"
        elif rep.video:   file_id, ftype = rep.video.file_id,     "video"
        elif rep.document:file_id, ftype = rep.document.file_id,  "document"
        elif rep.audio:   file_id, ftype = rep.audio.file_id,     "audio"
        elif rep.sticker: file_id, ftype = rep.sticker.file_id,   "sticker"
        elif rep.voice:   file_id, ftype = rep.voice.file_id,     "voice"
        if not text:
            text = rep.caption or rep.text or ""

    data = chat_db(cid)
    data["notes"][name] = {"text": text, "file_id": file_id, "type": ftype}
    save_db(DB)
    await msg.reply_text(tr(cid, "note_saved", name=name), parse_mode=ParseMode.HTML)

@group_only
async def cmd_get(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /get [имя] или #имя")
    await _send_note(update, ctx, ctx.args[0].lower())

async def _send_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE, name: str):
    cid  = update.effective_chat.id
    data = chat_db(cid)
    note = data["notes"].get(name)
    if not note:
        return await update.message.reply_text(
            tr(cid, "note_notfound", name=name), parse_mode=ParseMode.HTML
        )
    text    = note.get("text", "")
    file_id = note.get("file_id")
    ftype   = note.get("type")
    try:
        if ftype == "photo":
            await update.message.reply_photo(file_id, caption=text or None, parse_mode=ParseMode.HTML)
        elif ftype == "video":
            await update.message.reply_video(file_id, caption=text or None, parse_mode=ParseMode.HTML)
        elif ftype == "document":
            await update.message.reply_document(file_id, caption=text or None, parse_mode=ParseMode.HTML)
        elif ftype == "sticker":
            await update.message.reply_sticker(file_id)
        elif ftype == "audio":
            await update.message.reply_audio(file_id, caption=text or None, parse_mode=ParseMode.HTML)
        elif ftype == "voice":
            await update.message.reply_voice(file_id, caption=text or None, parse_mode=ParseMode.HTML)
        else:
            if text:
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except TelegramError as e:
        await update.message.reply_text(f"❌ Ошибка при отправке заметки: {e}")

@mod_or_admin
async def cmd_delnote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /delnote [имя]")
    name = ctx.args[0].lower()
    data = chat_db(cid)
    if name not in data["notes"]:
        return await update.message.reply_text(
            tr(cid, "note_notfound", name=name), parse_mode=ParseMode.HTML
        )
    del data["notes"][name]
    save_db(DB)
    await update.message.reply_text(tr(cid, "note_deleted", name=name), parse_mode=ParseMode.HTML)

@group_only
async def cmd_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    data = chat_db(cid)
    notes = list(data["notes"].keys())
    if not notes:
        return await update.message.reply_text(tr(cid, "notes_empty"))
    lines = "\n".join(f"• <code>#{n}</code>" for n in sorted(notes))
    await update.message.reply_text(f"📝 <b>Заметки:</b>\n{lines}", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  ФИЛЬТРЫ
# ══════════════════════════════════════════════════════════════
@mod_or_admin
async def cmd_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /filter [слово] [ответ]")
    kw   = ctx.args[0].lower()
    text = " ".join(ctx.args[1:])
    if not text and update.message.reply_to_message:
        text = update.message.reply_to_message.text or ""
    data = chat_db(cid)
    data["filters"][kw] = {"text": text}
    save_db(DB)
    await update.message.reply_text(tr(cid, "filter_saved", kw=kw), parse_mode=ParseMode.HTML)

@mod_or_admin
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /stop [слово]")
    kw   = ctx.args[0].lower()
    data = chat_db(cid)
    if kw not in data["filters"]:
        return await update.message.reply_text(
            tr(cid, "filter_notfound", kw=kw), parse_mode=ParseMode.HTML
        )
    del data["filters"][kw]
    save_db(DB)
    await update.message.reply_text(tr(cid, "filter_deleted", kw=kw), parse_mode=ParseMode.HTML)

@group_only
async def cmd_filters(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    data = chat_db(cid)
    if not data["filters"]:
        return await update.message.reply_text(tr(cid, "filters_empty"))
    lines = "\n".join(f"• <code>{k}</code>" for k in sorted(data["filters"]))
    await update.message.reply_text(f"🎯 <b>Фильтры:</b>\n{lines}", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  ЧЁРНЫЙ СПИСОК
# ══════════════════════════════════════════════════════════════
@mod_or_admin
async def cmd_addblacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /addblacklist [слово]")
    word = " ".join(ctx.args).lower()
    data = chat_db(cid)
    if word not in data["blacklist"]:
        data["blacklist"].append(word)
        save_db(DB)
    await update.message.reply_text(tr(cid, "bl_added"))

@mod_or_admin
async def cmd_rmblacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /rmblacklist [слово]")
    word = " ".join(ctx.args).lower()
    data = chat_db(cid)
    if word in data["blacklist"]:
        data["blacklist"].remove(word)
        save_db(DB)
    await update.message.reply_text(tr(cid, "bl_removed"))

@group_only
async def cmd_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    data = chat_db(cid)
    bl   = data["blacklist"]
    if not bl:
        return await update.message.reply_text(tr(cid, "bl_empty"))
    lines = "\n".join(f"• <code>{w}</code>" for w in sorted(bl))
    await update.message.reply_text(f"⬛ <b>Чёрный список:</b>\n{lines}", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_setblacklistaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    valid = ["delete", "warn", "kick", "ban", "mute"]
    if not ctx.args or ctx.args[0] not in valid:
        return await update.message.reply_text(f"❌ Использование: /setblacklistaction [{' | '.join(valid)}]")
    chat_db(cid)["blacklist_action"] = ctx.args[0]
    save_db(DB)
    await update.message.reply_text(f"✅ Действие по ЧС: <b>{ctx.args[0]}</b>", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  ЛОКИ
# ══════════════════════════════════════════════════════════════
LOCK_NAMES = {
    "text": "Текст", "media": "Медиа (все)", "photo": "Фото",
    "video": "Видео", "audio": "Аудио", "document": "Документ",
    "sticker": "Стикер", "gif": "GIF", "voice": "Голос",
    "vnote": "Видео-кружок", "contact": "Контакт",
    "location": "Геолокация", "poll": "Опросы",
    "forward": "Пересылки", "link": "Ссылки",
    "invite": "Инвайты", "game": "Игры", "inline": "Inline-боты",
}

@admin_only
async def cmd_lock(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in chat_db(cid)["locks"]:
        keys = " | ".join(chat_db(cid)["locks"].keys())
        return await update.message.reply_text(f"❌ Использование: /lock [{keys}]")
    key = ctx.args[0]
    chat_db(cid)["locks"][key] = True
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "lock_on", lock=LOCK_NAMES.get(key, key)), parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_unlock(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in chat_db(cid)["locks"]:
        keys = " | ".join(chat_db(cid)["locks"].keys())
        return await update.message.reply_text(f"❌ Использование: /unlock [{keys}]")
    key = ctx.args[0]
    chat_db(cid)["locks"][key] = False
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "lock_off", lock=LOCK_NAMES.get(key, key)), parse_mode=ParseMode.HTML
    )

@group_only
async def cmd_locks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    locks = chat_db(cid)["locks"]
    lines = "\n".join(
        f"{'🔒' if v else '🔓'} <b>{LOCK_NAMES.get(k,k)}</b>"
        for k, v in locks.items()
    )
    await update.message.reply_text(f"📋 <b>Состояние локов:</b>\n{lines}", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  АНТИФЛУД
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_antiflood(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    data = chat_db(cid)
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        return await update.message.reply_text("❌ Использование: /antiflood [on|off]")
    val = ctx.args[0] in ("on","вкл")
    data["settings"]["antiflood"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Антифлуд"),
        parse_mode=ParseMode.HTML,
    )

@admin_only
async def cmd_setfloodlimit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❌ Использование: /setfloodlimit [число]")
    chat_db(cid)["settings"]["antiflood_limit"] = int(ctx.args[0])
    save_db(DB)
    await update.message.reply_text(f"✅ Лимит флуда: <b>{ctx.args[0]}</b> сообщений", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_setfloodaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    valid = ["delete","mute","kick","ban"]
    if not ctx.args or ctx.args[0] not in valid:
        return await update.message.reply_text(f"❌ Использование: /setfloodaction [{' | '.join(valid)}]")
    chat_db(cid)["settings"]["antiflood_action"] = ctx.args[0]
    save_db(DB)
    await update.message.reply_text(f"✅ Действие при флуде: <b>{ctx.args[0]}</b>", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_setfloodtime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❌ Использование: /setfloodtime [секунды]")
    chat_db(cid)["settings"]["antiflood_window"] = int(ctx.args[0])
    save_db(DB)
    await update.message.reply_text(f"✅ Окно флуда: <b>{ctx.args[0]}с</b>", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  АНТИЛИНК
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_antilink(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        return await update.message.reply_text("❌ Использование: /antilink [on|off]")
    val = ctx.args[0] in ("on","вкл")
    chat_db(cid)["settings"]["antilink"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Антилинк"),
        parse_mode=ParseMode.HTML,
    )

@admin_only
async def cmd_setantilinkaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    valid = ["delete","warn","mute","kick","ban"]
    if not ctx.args or ctx.args[0] not in valid:
        return await update.message.reply_text(f"❌ Использование: /setantilinkaction [{' | '.join(valid)}]")
    chat_db(cid)["settings"]["antilink_action"] = ctx.args[0]
    save_db(DB)
    await update.message.reply_text(f"✅ Действие при ссылке: <b>{ctx.args[0]}</b>", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_alwhitelist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /alwhitelist [домен]")
    domain = ctx.args[0].lower().strip("/").replace("https://","").replace("http://","")
    wl = chat_db(cid)["settings"]["antilink_whitelist"]
    if domain not in wl:
        wl.append(domain)
        save_db(DB)
    await update.message.reply_text(f"✅ Домен <code>{domain}</code> добавлен в белый список.", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_alrmwhitelist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /alrmwhitelist [домен]")
    domain = ctx.args[0].lower()
    wl = chat_db(cid)["settings"]["antilink_whitelist"]
    if domain in wl:
        wl.remove(domain)
        save_db(DB)
    await update.message.reply_text(f"✅ Домен <code>{domain}</code> удалён из белого списка.", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  АНТИСПАМ
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_antispam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        return await update.message.reply_text("❌ Использование: /antispam [on|off]")
    val = ctx.args[0] in ("on","вкл")
    chat_db(cid)["settings"]["antispam"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Антиспам"),
        parse_mode=ParseMode.HTML,
    )

# ══════════════════════════════════════════════════════════════
#  ПРИВЕТСТВИЕ
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_setwelcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    text = " ".join(ctx.args) if ctx.args else None
    if update.message.reply_to_message and not text:
        text = update.message.reply_to_message.text
    if not text:
        return await update.message.reply_text(
            "❌ Использование: /setwelcome [текст]\n"
            "Переменные: {mention} {name} {username} {chat} {id} {count}"
        )
    chat_db(cid)["settings"]["welcome_text"] = text
    save_db(DB)
    await update.message.reply_text("✅ Приветствие обновлено!")

@admin_only
async def cmd_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        data = chat_db(cid)["settings"]
        return await update.message.reply_text(
            f"📋 Текущее приветствие:\n{data['welcome_text']}\n\n"
            f"Статус: {'✅ включено' if data['welcome_enabled'] else '❌ выключено'}"
        )
    val = ctx.args[0] in ("on","вкл")
    chat_db(cid)["settings"]["welcome_enabled"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Приветствие"),
        parse_mode=ParseMode.HTML,
    )

@admin_only
async def cmd_resetwelcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    chat_db(cid)["settings"]["welcome_text"] = _default_chat()["settings"]["welcome_text"]
    save_db(DB)
    await update.message.reply_text("✅ Приветствие сброшено.")

@admin_only
async def cmd_setgoodbye(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    text = " ".join(ctx.args) if ctx.args else None
    if not text:
        return await update.message.reply_text("❌ Использование: /setgoodbye [текст]")
    chat_db(cid)["settings"]["goodbye_text"] = text
    save_db(DB)
    await update.message.reply_text("✅ Прощание обновлено!")

@admin_only
async def cmd_goodbye(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        return await update.message.reply_text("❌ Использование: /goodbye [on|off]")
    val = ctx.args[0] in ("on","вкл")
    chat_db(cid)["settings"]["goodbye_enabled"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Прощание"),
        parse_mode=ParseMode.HTML,
    )

async def _format_welcome(text: str, user: User, chat: Chat) -> str:
    try:
        count = await chat.get_member_count()
    except TelegramError:
        count = "?"
    return text.format(
        mention  = mention(user),
        name     = user.full_name,
        username = f"@{user.username}" if user.username else user.full_name,
        chat     = chat.title,
        id       = user.id,
        count    = count,
    )

# ══════════════════════════════════════════════════════════════
#  КАПЧА
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        return await update.message.reply_text("❌ Использование: /captcha [on|off]")
    val = ctx.args[0] in ("on","вкл")
    chat_db(cid)["settings"]["captcha"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Капча"),
        parse_mode=ParseMode.HTML,
    )

@admin_only
async def cmd_setcaptchatimeout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❌ Использование: /setcaptchatimeout [секунды]")
    chat_db(cid)["settings"]["captcha_timeout"] = int(ctx.args[0])
    save_db(DB)
    await update.message.reply_text(f"✅ Таймаут капчи: <b>{ctx.args[0]}с</b>", parse_mode=ParseMode.HTML)

async def cb_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    cid  = update.effective_chat.id
    uid  = q.from_user.id
    data = callback_parse(q.data)

    if data.get("action") != "captcha_pass":
        return await q.answer()

    target_id = int(data.get("uid", 0))
    if uid != target_id:
        return await q.answer("Это не для тебя!", show_alert=True)

    cdata = chat_db(cid)
    pending = cdata["captcha_pending"].pop(str(uid), None)
    if not pending:
        return await q.answer()

    # Снимаем ограничения
    try:
        await _unmute_user(ctx.bot, cid, uid)
    except TelegramError:
        pass

    await q.edit_message_text(tr(cid, "captcha_pass"))
    await asyncio.sleep(5)
    try:
        await ctx.bot.delete_message(cid, q.message.message_id)
    except TelegramError:
        pass
    save_db(DB)

def callback_parse(data: str) -> dict:
    result = {}
    for part in data.split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k] = v
    return result

# ══════════════════════════════════════════════════════════════
#  ПРАВИЛА
# ══════════════════════════════════════════════════════════════
@group_only
async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    rules = chat_db(cid)["settings"]["rules"]
    if not rules:
        return await update.message.reply_text(tr(cid, "rules_empty"))
    await update.message.reply_text(
        f"📋 <b>Правила чата:</b>\n\n{rules}", parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_setrules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    text = " ".join(ctx.args) if ctx.args else None
    if update.message.reply_to_message and not text:
        text = update.message.reply_to_message.text
    if not text:
        return await update.message.reply_text("❌ Использование: /setrules [текст]")
    chat_db(cid)["settings"]["rules"] = text
    save_db(DB)
    await update.message.reply_text(tr(cid, "rules_set"))

@admin_only
async def cmd_clearrules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    chat_db(cid)["settings"]["rules"] = ""
    save_db(DB)
    await update.message.reply_text("✅ Правила очищены.")

# ══════════════════════════════════════════════════════════════
#  МЕДЛЕННЫЙ РЕЖИМ
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_slowmode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /slowmode [секунды|off]")
    if ctx.args[0].lower() in ("off","выкл","0"):
        chat_db(cid)["settings"]["slowmode"] = 0
        save_db(DB)
        try:
            await ctx.bot.set_chat_slow_mode_delay(cid, 0)
        except TelegramError:
            pass
        return await update.message.reply_text("✅ Медленный режим отключён.")
    secs = parse_time(ctx.args[0])
    if not secs:
        return await update.message.reply_text("❌ Неверный формат времени. Пример: 30s, 5m, 1h")
    chat_db(cid)["settings"]["slowmode"] = secs
    save_db(DB)
    try:
        await ctx.bot.set_chat_slow_mode_delay(cid, min(secs, 21600))
    except TelegramError:
        pass
    await update.message.reply_text(
        f"🐌 Медленный режим: <b>{fmt_time(secs)}</b>", parse_mode=ParseMode.HTML
    )

# ══════════════════════════════════════════════════════════════
#  ЛОГИРОВАНИЕ
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_setlog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /setlog [ID канала]")
    try:
        log_id = int(ctx.args[0])
        test   = await ctx.bot.send_message(log_id, "✅ Канал логов подключён к чату!")
        chat_db(cid)["settings"]["log_channel"] = log_id
        save_db(DB)
        await update.message.reply_text(f"✅ Лог-канал установлен: <code>{log_id}</code>", parse_mode=ParseMode.HTML)
    except (ValueError, TelegramError) as e:
        await update.message.reply_text(f"❌ Ошибка: {e}\nУбедись, что бот является администратором канала.")

@admin_only
async def cmd_unsetlog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    chat_db(cid)["settings"]["log_channel"] = None
    save_db(DB)
    await update.message.reply_text("✅ Логирование отключено.")

# ══════════════════════════════════════════════════════════════
#  РЕПОРТЫ
# ══════════════════════════════════════════════════════════════
@group_only
async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid     = update.effective_chat.id
    caller  = update.effective_user
    data    = chat_db(cid)
    if not data["settings"].get("report_enabled", True):
        return await update.message.reply_text("❌ Репорты отключены в этом чате.")
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Ответь на сообщение для жалобы.")
    target = update.message.reply_to_message.from_user
    if not target:
        return await update.message.reply_text("❌ Нельзя пожаловаться на это сообщение.")
    if await is_admin(ctx.bot, cid, target.id):
        return await update.message.reply_text("❌ Нельзя пожаловаться на администратора.")

    msg_link = f"https://t.me/c/{str(cid).replace('-100','')}/{update.message.reply_to_message.message_id}"
    report_text = tr(cid, "report_msg",
        chat      = update.effective_chat.title,
        from_user = mention(caller),
        on_user   = mention(target),
        msg_link  = f'<a href="{msg_link}">ссылка</a>',
    )

    # Отправить всем администраторам
    try:
        admins = await ctx.bot.get_chat_administrators(cid)
        for admin in admins:
            if not admin.user.is_bot:
                try:
                    await ctx.bot.send_message(
                        admin.user.id, report_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                except TelegramError:
                    pass
    except TelegramError:
        pass

    if data["settings"].get("log_channel"):
        await send_log(ctx.bot, cid, report_text)

    await update.message.reply_text(tr(cid, "report_sent"))

@admin_only
async def cmd_reports(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        return await update.message.reply_text("❌ Использование: /reports [on|off]")
    val = ctx.args[0] in ("on","вкл")
    chat_db(cid)["settings"]["report_enabled"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Репорты"),
        parse_mode=ParseMode.HTML,
    )

# ══════════════════════════════════════════════════════════════
#  AFK
# ══════════════════════════════════════════════════════════════
@group_only
async def cmd_afk(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    uid    = update.effective_user.id
    reason = " ".join(ctx.args) if ctx.args else ""
    data   = chat_db(cid)
    data["afk"][str(uid)] = {"reason": reason, "since": time.time()}
    save_db(DB)
    rtext  = f": {reason}" if reason else ""
    await update.message.reply_text(
        tr(cid, "afk_set", name=mention(update.effective_user), reason=rtext),
        parse_mode=ParseMode.HTML,
    )

@group_only
async def cmd_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    uid = str(update.effective_user.id)
    data = chat_db(cid)
    if uid in data["afk"]:
        del data["afk"][uid]
        save_db(DB)
        await update.message.reply_text(
            tr(cid, "afk_back", name=mention(update.effective_user)),
            parse_mode=ParseMode.HTML,
        )

# ══════════════════════════════════════════════════════════════
#  СТАТИСТИКА / ИНФО
# ══════════════════════════════════════════════════════════════
@group_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    stats = chat_db(cid)["stats"]
    try:
        count = await ctx.bot.get_chat(cid).then(lambda c: c) if False else None
        count = (await ctx.bot.get_chat(cid)).get_member_count if False else "?"
        count = await (await ctx.bot.get_chat(cid)).get_member_count()
    except Exception:
        count = "?"
    await update.message.reply_text(
        f"📊 <b>Статистика чата</b>\n\n"
        f"👥 Участников: <b>{count}</b>\n"
        f"💬 Сообщений: <b>{stats['messages']}</b>\n"
        f"🚪 Вступлений: <b>{stats['joins']}</b>\n"
        f"🚶 Выходов: <b>{stats['leaves']}</b>\n"
        f"🔨 Банов: <b>{stats['bans']}</b>\n"
        f"👢 Киков: <b>{stats['kicks']}</b>\n"
        f"🔇 Мутов: <b>{stats['mutes']}</b>\n"
        f"⚠️ Варнов выдано: <b>{stats['warns_total']}</b>\n"
        f"🗑 Удалено сообщений: <b>{stats['deleted']}</b>",
        parse_mode=ParseMode.HTML,
    )

@group_only
async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid    = update.effective_chat.id
    target = await get_target(update, ctx) or update.effective_user
    try:
        member = await ctx.bot.get_chat_member(cid, target.id)
        status_map = {
            ChatMemberStatus.OWNER:         "👑 Владелец",
            ChatMemberStatus.ADMINISTRATOR: "⭐ Администратор",
            ChatMemberStatus.MEMBER:        "👤 Участник",
            ChatMemberStatus.RESTRICTED:    "🔇 Ограничен",
            ChatMemberStatus.LEFT:          "🚪 Покинул",
            ChatMemberStatus.BANNED:        "🔨 Забанен",
        }
        status = status_map.get(member.status, member.status)
    except TelegramError:
        status = "❓ Неизвестно"

    data   = chat_db(cid)
    warns  = len(data["warns"].get(str(target.id), []))
    is_mod = target.id in data["moderators"]

    text = (
        f"ℹ️ <b>Информация о пользователе</b>\n\n"
        f"👤 Имя: {mention(target)}\n"
        f"🆔 ID: <code>{target.id}</code>\n"
        f"📛 Username: @{target.username or '—'}\n"
        f"🤖 Бот: {'Да' if target.is_bot else 'Нет'}\n"
        f"📌 Статус: {status}\n"
        f"⭐ Модератор: {'Да' if is_mod else 'Нет'}\n"
        f"⚠️ Варны: {warns}/{data['settings']['max_warns']}\n"
    )
    if data["afk"].get(str(target.id)):
        afk = data["afk"][str(target.id)]
        since = datetime.fromtimestamp(afk["since"]).strftime("%d.%m %H:%M")
        text += f"💤 AFK с {since}: {afk.get('reason','')}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

@group_only
async def cmd_chatinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    chat = update.effective_chat
    try:
        count = await chat.get_member_count()
    except TelegramError:
        count = "?"
    data = chat_db(cid)
    s    = data["settings"]
    await update.message.reply_text(
        f"ℹ️ <b>Информация о чате</b>\n\n"
        f"📛 Название: {chat.title}\n"
        f"🆔 ID: <code>{chat.id}</code>\n"
        f"🔗 Username: @{chat.username or '—'}\n"
        f"👥 Участников: {count}\n"
        f"📋 Правила: {'✅' if s['rules'] else '❌'}\n"
        f"🎉 Приветствие: {'✅' if s['welcome_enabled'] else '❌'}\n"
        f"🤖 Капча: {'✅' if s['captcha'] else '❌'}\n"
        f"⚡ Антифлуд: {'✅' if s['antiflood'] else '❌'}\n"
        f"🔗 Антилинк: {'✅' if s['antilink'] else '❌'}\n"
        f"♻️ Антиспам: {'✅' if s['antispam'] else '❌'}\n"
        f"🌐 Язык: {s['language'].upper()}\n"
        f"⭐ Модераторов: {len(data['moderators'])}\n"
        f"📝 Заметок: {len(data['notes'])}\n"
        f"🎯 Фильтров: {len(data['filters'])}\n"
        f"⬛ Слов в ЧС: {len(data['blacklist'])}",
        parse_mode=ParseMode.HTML,
    )

async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        await msg.reply_text(
            f"👤 <b>{u.full_name}</b>\n🆔 ID: <code>{u.id}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        u   = update.effective_user
        cid = update.effective_chat.id
        await msg.reply_text(
            f"👤 Твой ID: <code>{u.id}</code>\n"
            f"💬 ID чата: <code>{cid}</code>",
            parse_mode=ParseMode.HTML,
        )

# ══════════════════════════════════════════════════════════════
#  ЯЗЫК
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_setlang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    valid = ["ru","en"]
    if not ctx.args or ctx.args[0].lower() not in valid:
        return await update.message.reply_text(f"❌ Использование: /setlang [{' | '.join(valid)}]")
    chat_db(cid)["settings"]["language"] = ctx.args[0].lower()
    save_db(DB)
    await update.message.reply_text(f"✅ Язык: <b>{ctx.args[0].upper()}</b>", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  CLEANSERVICE
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_cleanservice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args or ctx.args[0] not in ("on","off","вкл","выкл"):
        return await update.message.reply_text("❌ Использование: /cleanservice [on|off]")
    val = ctx.args[0] in ("on","вкл")
    chat_db(cid)["settings"]["clean_service"] = val
    save_db(DB)
    await update.message.reply_text(
        tr(cid, "setting_on" if val else "setting_off", setting="Автоудаление системных сообщений"),
        parse_mode=ParseMode.HTML,
    )

# ══════════════════════════════════════════════════════════════
#  ОТКЛЮЧЕНИЕ КОМАНД
# ══════════════════════════════════════════════════════════════
@admin_only
async def cmd_disable(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /disable [команда]")
    cmd  = ctx.args[0].lstrip("/").lower()
    data = chat_db(cid)
    if cmd not in data["disabled"]:
        data["disabled"].append(cmd)
        save_db(DB)
    await update.message.reply_text(f"🔕 Команда <code>/{cmd}</code> отключена.", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_enable(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not ctx.args:
        return await update.message.reply_text("❌ Использование: /enable [команда]")
    cmd  = ctx.args[0].lstrip("/").lower()
    data = chat_db(cid)
    if cmd in data["disabled"]:
        data["disabled"].remove(cmd)
        save_db(DB)
    await update.message.reply_text(f"✅ Команда <code>/{cmd}</code> включена.", parse_mode=ParseMode.HTML)

# ══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИК НОВЫХ УЧАСТНИКОВ (приветствие + капча)
# ══════════════════════════════════════════════════════════════
async def on_new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid     = update.effective_chat.id
    data    = chat_db(cid)
    settings= data["settings"]

    for user in update.message.new_chat_members:
        if user.is_bot:
            continue

        data["stats"]["joins"] += 1
        save_db(DB)

        # Чистка системных сообщений
        if settings.get("clean_service"):
            await safe_delete(ctx.bot, cid, update.message.message_id)

        # Капча — мютим и ждём нажатия кнопки
        if settings.get("captcha"):
            timeout = settings.get("captcha_timeout", 90)
            try:
                await _mute_user(ctx.bot, cid, user.id)
            except TelegramError:
                pass

            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "✅ Я не робот",
                    callback_data=f"action=captcha_pass|uid={user.id}",
                )
            ]])
            m = await ctx.bot.send_message(
                cid,
                tr(cid, "captcha_msg",
                   mention=mention(user), timeout=timeout),
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
            data["captcha_pending"][str(user.id)] = {
                "msg_id": m.message_id,
                "timeout_at": time.time() + timeout,
            }
            save_db(DB)
            ctx.application.job_queue.run_once(
                _captcha_timeout_job,
                timeout,
                data={"cid": cid, "uid": user.id, "msg_id": m.message_id},
            )
            continue  # Пропустить приветствие, пока не прошёл капчу

        # Приветствие
        if settings.get("welcome_enabled"):
            text = await _format_welcome(settings["welcome_text"], user, update.effective_chat)
            await ctx.bot.send_message(cid, text, parse_mode=ParseMode.HTML)

        await send_log(ctx.bot, cid, f"🚪 Вступил: {mention(user)}")

async def _captcha_timeout_job(ctx: ContextTypes.DEFAULT_TYPE):
    job = ctx.job
    cid, uid, msg_id = job.data["cid"], job.data["uid"], job.data["msg_id"]
    data  = chat_db(cid)
    pending = data["captcha_pending"].get(str(uid))
    if not pending:
        return  # Уже прошёл капчу
    del data["captcha_pending"][str(uid)]
    save_db(DB)

    settings = data["settings"]
    u_info   = None
    try:
        member = await ctx.bot.get_chat_member(cid, uid)
        u_info = member.user
    except TelegramError:
        pass

    try:
        await safe_delete(ctx.bot, cid, msg_id)
        if settings.get("captcha_kick", True):
            await ctx.bot.ban_chat_member(cid, uid)
            await ctx.bot.unban_chat_member(cid, uid)
            if u_info:
                await ctx.bot.send_message(
                    cid,
                    tr(cid, "captcha_fail", name=u_info.full_name),
                    parse_mode=ParseMode.HTML,
                )
    except TelegramError:
        pass

# ══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИК ПОКИНУВШИХ ЧАТ
# ══════════════════════════════════════════════════════════════
async def on_left_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    user = update.message.left_chat_member
    if not user or user.is_bot:
        return

    data     = chat_db(cid)
    settings = data["settings"]
    data["stats"]["leaves"] += 1
    save_db(DB)

    if settings.get("clean_service"):
        await safe_delete(ctx.bot, cid, update.message.message_id)
        return

    if settings.get("goodbye_enabled"):
        text = settings["goodbye_text"].format(
            name    = user.full_name,
            mention = mention(user),
            username= f"@{user.username}" if user.username else user.full_name,
        )
        await ctx.bot.send_message(cid, text, parse_mode=ParseMode.HTML)

    await send_log(ctx.bot, cid, f"🚪 Покинул: {mention(user)}")

# ══════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ
# ══════════════════════════════════════════════════════════════
# Кэш для анти-спама {cid: {uid: last_text}}
_spam_cache: dict = {}

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not user or not chat:
        return
    if chat.type == ChatType.PRIVATE:
        return  # В ЛС не обрабатываем
    if user.is_bot:
        return

    cid  = chat.id
    uid  = user.id
    data = chat_db(cid)
    settings = data["settings"]

    # Обновить счётчик сообщений
    data["stats"]["messages"] += 1

    # Проверить, что пользователь не в captcha_pending
    if str(uid) in data["captcha_pending"]:
        await safe_delete(ctx.bot, cid, msg.message_id)
        return

    # AFK — если кто-то вернулся
    if str(uid) in data["afk"]:
        del data["afk"][str(uid)]
        save_db(DB)
        await msg.reply_text(
            tr(cid, "afk_back", name=mention(user)), parse_mode=ParseMode.HTML
        )

    # AFK — упомянули кого-то в AFK
    if msg.entities or msg.text:
        for entity in (msg.entities or []):
            if entity.type == "mention":
                mentioned_username = msg.text[entity.offset+1:entity.offset+entity.length]
                for afk_uid, afk_data in list(data["afk"].items()):
                    try:
                        afk_user = await ctx.bot.get_chat(int(afk_uid))
                        if afk_user.username and afk_user.username.lower() == mentioned_username.lower():
                            since = datetime.fromtimestamp(afk_data["since"]).strftime("%H:%M")
                            reason = f" ({afk_data['reason']})" if afk_data.get("reason") else ""
                            await msg.reply_text(
                                tr(cid, "afk_mention", name=afk_user.full_name, reason=reason),
                                parse_mode=ParseMode.HTML,
                            )
                    except TelegramError:
                        pass

    # Модераторов / администраторов пропускаем остальные проверки
    is_privileged = await is_mod_or_admin(ctx.bot, cid, uid)

    if not is_privileged:
        text_lower = (msg.text or msg.caption or "").lower()

        # ── Чёрный список ──────────────────────────────────────
        for word in data["blacklist"]:
            if word in text_lower:
                action = data["blacklist_action"]
                await safe_delete(ctx.bot, cid, msg.message_id)
                data["stats"]["deleted"] += 1
                if action == "warn":
                    # Симулируем варн
                    warns = data["warns"].setdefault(str(uid), [])
                    warns.append({"reason": "Чёрный список", "by": 0, "date": time.time()})
                    max_w = settings["max_warns"]
                    if len(warns) >= max_w:
                        await _apply_warn_action(ctx.bot, cid, user, settings["warn_action"], settings["warn_mute_time"])
                        data["warns"][str(uid)] = []
                elif action == "kick":
                    await ctx.bot.ban_chat_member(cid, uid)
                    await ctx.bot.unban_chat_member(cid, uid)
                elif action == "ban":
                    await ctx.bot.ban_chat_member(cid, uid)
                elif action == "mute":
                    until = datetime.now(timezone.utc) + timedelta(seconds=3600)
                    await _mute_user(ctx.bot, cid, uid, until)
                save_db(DB)
                return

        # ── Анти-ссылки ────────────────────────────────────────
        if settings.get("antilink"):
            url_pattern = re.compile(
                r"(https?://|www\.|t\.me/|@\w+(?:\.|\s|$))[^\s]*",
                re.IGNORECASE,
            )
            has_link = bool(url_pattern.search(text_lower))
            if not has_link and msg.entities:
                for e in msg.entities:
                    if e.type in ("url", "text_link"):
                        has_link = True
                        break
            if has_link:
                whitelist = settings.get("antilink_whitelist", [])
                blocked = True
                if whitelist:
                    for domain in whitelist:
                        if domain in text_lower:
                            blocked = False
                            break
                if blocked:
                    action = settings["antilink_action"]
                    await safe_delete(ctx.bot, cid, msg.message_id)
                    data["stats"]["deleted"] += 1
                    notif = await ctx.bot.send_message(
                        cid, tr(cid, "antilink_msg"), parse_mode=ParseMode.HTML
                    )
                    if action == "warn":
                        warns = data["warns"].setdefault(str(uid), [])
                        warns.append({"reason": "Ссылка", "by": 0, "date": time.time()})
                    elif action == "mute":
                        until = datetime.now(timezone.utc) + timedelta(seconds=3600)
                        await _mute_user(ctx.bot, cid, uid, until)
                    elif action == "kick":
                        await ctx.bot.ban_chat_member(cid, uid)
                        await ctx.bot.unban_chat_member(cid, uid)
                    elif action == "ban":
                        await ctx.bot.ban_chat_member(cid, uid)
                    save_db(DB)
                    await asyncio.sleep(5)
                    await safe_delete(ctx.bot, cid, notif.message_id)
                    return

        # ── Антиспам (дублирующиеся сообщения) ────────────────
        if settings.get("antispam") and msg.text:
            cache = _spam_cache.setdefault(cid, {})
            if cache.get(uid) == msg.text:
                await safe_delete(ctx.bot, cid, msg.message_id)
                data["stats"]["deleted"] += 1
                notif = await ctx.bot.send_message(
                    cid, tr(cid, "antispam_msg"), parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(3)
                await safe_delete(ctx.bot, cid, notif.message_id)
                save_db(DB)
                return
            cache[uid] = msg.text

        # ── Антифлуд ───────────────────────────────────────────
        if settings.get("antiflood"):
            tracker = data["flood_tracker"].setdefault(str(uid), [])
            now     = time.time()
            window  = settings["antiflood_window"]
            tracker_clean = [t for t in tracker if now - t < window]
            tracker_clean.append(now)
            data["flood_tracker"][str(uid)] = tracker_clean

            if len(tracker_clean) > settings["antiflood_limit"]:
                data["flood_tracker"][str(uid)] = []
                action = settings["antiflood_action"]
                mtime  = settings.get("antiflood_mute_time", 300)
                await safe_delete(ctx.bot, cid, msg.message_id)
                data["stats"]["deleted"] += 1
                notif = await ctx.bot.send_message(
                    cid,
                    tr(cid, "antiflood_msg", name=mention(user), action=action),
                    parse_mode=ParseMode.HTML,
                )
                try:
                    if action == "mute":
                        until = datetime.now(timezone.utc) + timedelta(seconds=mtime)
                        await _mute_user(ctx.bot, cid, uid, until)
                        data["stats"]["mutes"] += 1
                    elif action == "kick":
                        await ctx.bot.ban_chat_member(cid, uid)
                        await ctx.bot.unban_chat_member(cid, uid)
                        data["stats"]["kicks"] += 1
                    elif action == "ban":
                        await ctx.bot.ban_chat_member(cid, uid)
                        data["stats"]["bans"] += 1
                    elif action == "delete":
                        pass
                except TelegramError:
                    pass
                save_db(DB)
                await asyncio.sleep(5)
                await safe_delete(ctx.bot, cid, notif.message_id)
                return

        # ── Медленный режим (бот-сторона) ──────────────────────
        slowmode_secs = settings.get("slowmode", 0)
        if slowmode_secs > 0:
            sm_tracker = data["slowmode_tracker"]
            last_msg   = sm_tracker.get(str(uid), 0)
            if time.time() - last_msg < slowmode_secs:
                await safe_delete(ctx.bot, cid, msg.message_id)
                data["stats"]["deleted"] += 1
                try:
                    notif = await ctx.bot.send_message(
                        uid,
                        tr(cid, "slowmode_msg", sec=slowmode_secs),
                        parse_mode=ParseMode.HTML,
                    )
                except TelegramError:
                    pass
                save_db(DB)
                return
            sm_tracker[str(uid)] = time.time()

        # ── Локи ───────────────────────────────────────────────
        locks = data["locks"]
        deleted_by_lock = False

        async def delete_locked():
            nonlocal deleted_by_lock
            if not deleted_by_lock:
                await safe_delete(ctx.bot, cid, msg.message_id)
                data["stats"]["deleted"] += 1
                deleted_by_lock = True
                notif = await ctx.bot.send_message(
                    cid, tr(cid, "locked_msg"), parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(3)
                await safe_delete(ctx.bot, cid, notif.message_id)

        if locks.get("text") and msg.text and not msg.entities:
            await delete_locked()
        if locks.get("photo") and msg.photo:
            await delete_locked()
        if locks.get("video") and msg.video:
            await delete_locked()
        if locks.get("audio") and msg.audio:
            await delete_locked()
        if locks.get("document") and msg.document:
            await delete_locked()
        if locks.get("sticker") and msg.sticker:
            await delete_locked()
        if locks.get("gif") and msg.animation:
            await delete_locked()
        if locks.get("voice") and msg.voice:
            await delete_locked()
        if locks.get("video_note") and msg.video_note:
            await delete_locked()
        if locks.get("contact") and msg.contact:
            await delete_locked()
        if locks.get("location") and msg.location:
            await delete_locked()
        if locks.get("poll") and msg.poll:
            await delete_locked()
        if locks.get("forward") and msg.forward_date:
            await delete_locked()
        if deleted_by_lock:
            save_db(DB)
            return

    # ── Заметки по #тегу ───────────────────────────────────────
    if msg.text:
        hash_match = re.findall(r"#(\w+)", msg.text)
        for tag in hash_match:
            if tag.lower() in data["notes"]:
                await _send_note(update, ctx, tag.lower())

    # ── Фильтры ────────────────────────────────────────────────
    if msg.text:
        text_lower = msg.text.lower()
        for kw, fdata in data["filters"].items():
            if kw in text_lower:
                ftxt = fdata.get("text", "")
                if ftxt:
                    await msg.reply_text(ftxt, parse_mode=ParseMode.HTML)
                break

    save_db(DB)

# ══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИК CALLBACK (кнопки)
# ══════════════════════════════════════════════════════════════
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = callback_parse(q.data)
    action = data.get("action","")

    if action == "captcha_pass":
        await cb_captcha(update, ctx)
    elif action == "help_full":
        await cb_help_full(update, ctx)
    else:
        await q.answer()

# ══════════════════════════════════════════════════════════════
#  ГЛАВНАЯ ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        log.error("Установи токен! BOT_TOKEN=xxx python iris_bot.py")
        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # ── Регистрация обработчиков ───────────────────────────────
    handlers = [
        # Общие
        CommandHandler("start",            cmd_start),
        CommandHandler("help",             cmd_help),
        CommandHandler("id",               cmd_id),

        # Модераторы
        CommandHandler("addmod",           cmd_addmod),
        CommandHandler("removemod",        cmd_removemod),
        CommandHandler("modlist",          cmd_modlist),
        CommandHandler("promote",          cmd_promote),
        CommandHandler("demote",           cmd_demote),

        # Модерация
        CommandHandler("ban",              cmd_ban),
        CommandHandler("unban",            cmd_unban),
        CommandHandler("kick",             cmd_kick),
        CommandHandler("mute",             cmd_mute),
        CommandHandler("unmute",           cmd_unmute),
        CommandHandler("ro",               cmd_ro),
        CommandHandler("unro",             cmd_unro),
        CommandHandler("warn",             cmd_warn),
        CommandHandler("unwarn",           cmd_unwarn),
        CommandHandler("clearwarns",       cmd_clearwarns),
        CommandHandler("warnlist",         cmd_warnlist),
        CommandHandler("setwarnlimit",     cmd_setwarnlimit),
        CommandHandler("setwarnaction",    cmd_setwarnaction),

        # Пины
        CommandHandler("pin",              cmd_pin),
        CommandHandler("unpin",            cmd_unpin),
        CommandHandler("unpinall",         cmd_unpinall),

        # Удаление
        CommandHandler("del",              cmd_del),
        CommandHandler("purge",            cmd_purge),

        # Заметки
        CommandHandler("note",             cmd_note),
        CommandHandler("get",              cmd_get),
        CommandHandler("delnote",          cmd_delnote),
        CommandHandler("notes",            cmd_notes),

        # Фильтры
        CommandHandler("filter",           cmd_filter),
        CommandHandler("stop",             cmd_stop),
        CommandHandler("filters",          cmd_filters),

        # Чёрный список
        CommandHandler("blacklist",        cmd_blacklist),
        CommandHandler("addblacklist",     cmd_addblacklist),
        CommandHandler("rmblacklist",      cmd_rmblacklist),
        CommandHandler("setblacklistaction", cmd_setblacklistaction),

        # Локи
        CommandHandler("lock",             cmd_lock),
        CommandHandler("unlock",           cmd_unlock),
        CommandHandler("locks",            cmd_locks),

        # Антифлуд
        CommandHandler("antiflood",        cmd_antiflood),
        CommandHandler("setfloodlimit",    cmd_setfloodlimit),
        CommandHandler("setfloodaction",   cmd_setfloodaction),
        CommandHandler("setfloodtime",     cmd_setfloodtime),

        # Антилинк
        CommandHandler("antilink",         cmd_antilink),
        CommandHandler("setantilinkaction",cmd_setantilinkaction),
        CommandHandler("alwhitelist",      cmd_alwhitelist),
        CommandHandler("alrmwhitelist",    cmd_alrmwhitelist),

        # Антиспам
        CommandHandler("antispam",         cmd_antispam),

        # Приветствие
        CommandHandler("setwelcome",       cmd_setwelcome),
        CommandHandler("welcome",          cmd_welcome),
        CommandHandler("resetwelcome",     cmd_resetwelcome),
        CommandHandler("setgoodbye",       cmd_setgoodbye),
        CommandHandler("goodbye",          cmd_goodbye),

        # Капча
        CommandHandler("captcha",          cmd_captcha),
        CommandHandler("setcaptchatimeout",cmd_setcaptchatimeout),

        # Правила
        CommandHandler("rules",            cmd_rules),
        CommandHandler("setrules",         cmd_setrules),
        CommandHandler("clearrules",       cmd_clearrules),

        # Slowmode
        CommandHandler("slowmode",         cmd_slowmode),

        # Логи
        CommandHandler("setlog",           cmd_setlog),
        CommandHandler("unsetlog",         cmd_unsetlog),

        # Репорты
        CommandHandler("report",           cmd_report),
        CommandHandler("reports",          cmd_reports),

        # AFK
        CommandHandler("afk",              cmd_afk),
        CommandHandler("back",             cmd_back),

        # Статистика
        CommandHandler("stats",            cmd_stats),
        CommandHandler("info",             cmd_info),
        CommandHandler("chatinfo",         cmd_chatinfo),

        # Язык
        CommandHandler("setlang",          cmd_setlang),

        # Прочее
        CommandHandler("cleanservice",     cmd_cleanservice),
        CommandHandler("disable",          cmd_disable),
        CommandHandler("enable",           cmd_enable),

        # Сообщения
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            on_new_member,
        ),
        MessageHandler(
            filters.StatusUpdate.LEFT_CHAT_MEMBER,
            on_left_member,
        ),
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            on_message,
        ),

        # Кнопки
        CallbackQueryHandler(on_callback),
    ]

    for h in handlers:
        app.add_handler(h)

    log.info("🌸 Iris Bot запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
