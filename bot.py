import asyncio
import random
import logging
import datetime
import os
import pytz
import aiohttp
from collections import Counter

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "ТВОЙ_GEMINI_КЛЮЧ")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
)

WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else None

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 10000))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

ai_enabled: dict[int, bool] = {}
ai_scope: dict[int, str] = {}

SCOPE_PROMPTS = {
    "countries": (
        "Ты — помощник в телеграм-боте про страны и столицы. "
        "Отвечай только на вопросы про страны, столицы, географию, культуру, флаги. "
        "Если вопрос не про это — вежливо скажи, что можешь помочь только с темой стран. "
        "Отвечай кратко, дружелюбно, можно с эмодзи."
    ),
    "anything": (
        "Ты — дружелюбный универсальный ИИ-помощник внутри телеграм-бота про столицы. "
        "Можешь отвечать на любые вопросы пользователя. "
        "Отвечай кратко и понятно, можно с эмодзи."
    ),
}

async def ask_gemini(user_id: int, question: str) -> str:
    scope = ai_scope.get(user_id, "countries")
    system_prompt = SCOPE_PROMPTS[scope]
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": question}]}],
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GEMINI_URL, json=payload, timeout=20) as resp:
                data = await resp.json()
                if resp.status != 200:
                    logging.error(f"Gemini error: {data}")
                    return "⚠️ ИИ сейчас недоступен, попробуй позже."
                return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logging.error(f"Gemini exception: {e}")
        return "⚠️ Не удалось получить ответ от ИИ. Попробуй позже."

COUNTRIES = {
    "узбекистан":     {"flag": "🇺🇿", "capital": "Ташкент",    "population": 36.0,  "continent": "Азия", "tz": "Asia/Tashkent"},
    "россия":         {"flag": "🇷🇺", "capital": "Москва",     "population": 146.0, "continent": "Европа", "tz": "Europe/Moscow"},
    "казахстан":      {"flag": "🇰🇿", "capital": "Астана",     "population": 19.6,  "continent": "Азия", "tz": "Asia/Almaty"},
    "кыргызстан":     {"flag": "🇰🇬", "capital": "Бишкек",     "population": 6.7,   "continent": "Азия", "tz": "Asia/Bishkek"},
    "таджикистан":    {"flag": "🇹🇯", "capital": "Душанбе",    "population": 10.1,  "continent": "Азия", "tz": "Asia/Dushanbe"},
    "туркменистан":   {"flag": "🇹🇲", "capital": "Ашхабад",    "population": 6.4,   "continent": "Азия", "tz": "Asia/Ashgabat"},
    "украина":        {"flag": "🇺🇦", "capital": "Киев",       "population": 36.7,  "continent": "Европа", "tz": "Europe/Kiev"},
    "беларусь":       {"flag": "🇧🇾", "capital": "Минск",      "population": 9.2,   "continent": "Европа", "tz": "Europe/Minsk"},
    "турция":         {"flag": "🇹🇷", "capital": "Анкара",     "population": 85.5,  "continent": "Азия", "tz": "Europe/Istanbul"},
    "китай":          {"flag": "🇨🇳", "capital": "Пекин",      "population": 1412.0,"continent": "Азия", "tz": "Asia/Shanghai"},
    "япония":         {"flag": "🇯🇵", "capital": "Токио",      "population": 123.0, "continent": "Азия", "tz": "Asia/Tokyo"},
    "германия":       {"flag": "🇩🇪", "capital": "Берлин",     "population": 84.5,  "continent": "Европа", "tz": "Europe/Berlin"},
    "франция":        {"flag": "🇫🇷", "capital": "Париж",      "population": 68.0,  "continent": "Европа", "tz": "Europe/Paris"},
    "сша":            {"flag": "🇺🇸", "capital": "Вашингтон",  "population": 335.0, "continent": "Северная Америка", "tz": "America/New_York"},
    "великобритания": {"flag": "🇬🇧", "capital": "Лондон",     "population": 68.0,  "continent": "Европа", "tz": "Europe/London"},
    "италия":         {"flag": "🇮🇹", "capital": "Рим",        "population": 58.9,  "continent": "Европа", "tz": "Europe/Rome"},
    "испания":        {"flag": "🇪🇸", "capital": "Мадрид",     "population": 47.4,  "continent": "Европа", "tz": "Europe/Madrid"},
    "индия":          {"flag": "🇮🇳", "capital": "Нью-Дели",   "population": 1428.0,"continent": "Азия", "tz": "Asia/Kolkata"},
    "бразилия":       {"flag": "🇧🇷", "capital": "Бразилиа",   "population": 216.0, "continent": "Южная Америка", "tz": "America/Sao_Paulo"},
    "египет":         {"flag": "🇪🇬", "capital": "Каир",       "population": 112.0, "continent": "Африка", "tz": "Africa/Cairo"},
    "канада":         {"flag": "🇨🇦", "capital": "Оттава",     "population": 39.0,  "continent": "Северная Америка", "tz": "America/Toronto"},
    "мексика":        {"flag": "🇲🇽", "capital": "Мехико",     "population": 128.0, "continent": "Северная Америка", "tz": "America/Mexico_City"},
    "аргентина":      {"flag": "🇦🇷", "capital": "Буэнос-Айрес","population": 46.0, "continent": "Южная Америка", "tz": "America/Argentina/Buenos_Aires"},
    "южная корея":    {"flag": "🇰🇷", "capital": "Сеул",       "population": 51.7,  "continent": "Азия", "tz": "Asia/Seoul"},
    "северная корея": {"flag": "🇰🇵", "capital": "Пхеньян",    "population": 26.0,  "continent": "Азия", "tz": "Asia/Pyongyang"},
    "австралия":      {"flag": "🇦🇺", "capital": "Канберра",   "population": 26.6,  "continent": "Австралия", "tz": "Australia/Sydney"},
    "польша":         {"flag": "🇵🇱", "capital": "Варшава",    "population": 37.7,  "continent": "Европа", "tz": "Europe/Warsaw"},
    "нидерланды":     {"flag": "🇳🇱", "capital": "Амстердам",  "population": 17.6,  "continent": "Европа", "tz": "Europe/Amsterdam"},
    "швеция":         {"flag": "🇸🇪", "capital": "Стокгольм",  "population": 10.5,  "continent": "Европа", "tz": "Europe/Stockholm"},
    "норвегия":       {"flag": "🇳🇴", "capital": "Осло",       "population": 5.5,   "continent": "Европа", "tz": "Europe/Oslo"},
    "финляндия":      {"flag": "🇫🇮", "capital": "Хельсинки",  "population": 5.6,   "continent": "Европа", "tz": "Europe/Helsinki"},
    "греция":         {"flag": "🇬🇷", "capital": "Афины",      "population": 10.4,  "continent": "Европа", "tz": "Europe/Athens"},
    "португалия":     {"flag": "🇵🇹", "capital": "Лиссабон",   "population": 10.3,  "continent": "Европа", "tz": "Europe/Lisbon"},
    "швейцария":      {"flag": "🇨🇭", "capital": "Берн",       "population": 8.7,   "continent": "Европа", "tz": "Europe/Zurich"},
    "австрия":        {"flag": "🇦🇹", "capital": "Вена",       "population": 9.1,   "continent": "Европа", "tz": "Europe/Vienna"},
    "чехия":          {"flag": "🇨🇿", "capital": "Прага",      "population": 10.5,  "continent": "Европа", "tz": "Europe/Prague"},
    "венгрия":        {"flag": "🇭🇺", "capital": "Будапешт",   "population": 9.6,   "continent": "Европа", "tz": "Europe/Budapest"},
    "румыния":        {"flag": "🇷🇴", "capital": "Бухарест",   "population": 19.0,  "continent": "Европа", "tz": "Europe/Bucharest"},
    "болгария":       {"flag": "🇧🇬", "capital": "София",      "population": 6.4,   "continent": "Европа", "tz": "Europe/Sofia"},
    "сербия":         {"flag": "🇷🇸", "capital": "Белград",    "population": 6.6,   "continent": "Европа", "tz": "Europe/Belgrade"},
    "хорватия":       {"flag": "🇭🇷", "capital": "Загреб",     "population": 3.8,   "continent": "Европа", "tz": "Europe/Zagreb"},
    "азербайджан":    {"flag": "🇦🇿", "capital": "Баку",       "population": 10.2,  "continent": "Азия", "tz": "Asia/Baku"},
    "армения":        {"flag": "🇦🇲", "capital": "Ереван",     "population": 3.0,   "continent": "Азия", "tz": "Asia/Yerevan"},
    "грузия":         {"flag": "🇬🇪", "capital": "Тбилиси",    "population": 3.7,   "continent": "Азия", "tz": "Asia/Tbilisi"},
    "иран":           {"flag": "🇮🇷", "capital": "Тегеран",    "population": 88.0,  "continent": "Азия", "tz": "Asia/Tehran"},
    "ирак":           {"flag": "🇮🇶", "capital": "Багдад",     "population": 43.0,  "continent": "Азия", "tz": "Asia/Baghdad"},
    "саудовская аравия": {"flag": "🇸🇦", "capital": "Эр-Рияд", "population": 36.0,  "continent": "Азия", "tz": "Asia/Riyadh"},
    "оаэ":            {"flag": "🇦🇪", "capital": "Абу-Даби",   "population": 10.0,  "continent": "Азия", "tz": "Asia/Dubai"},
    "израиль":        {"flag": "🇮🇱", "capital": "Иерусалим",  "population": 9.8,   "continent": "Азия", "tz": "Asia/Jerusalem"},
    "пакистан":       {"flag": "🇵🇰", "capital": "Исламабад",  "population": 240.0, "continent": "Азия", "tz": "Asia/Karachi"},
    "афганистан":     {"flag": "🇦🇫", "capital": "Кабул",      "population": 42.0,  "continent": "Азия", "tz": "Asia/Kabul"},
    "вьетнам":        {"flag": "🇻🇳", "capital": "Ханой",      "population": 99.0,  "continent": "Азия", "tz": "Asia/Ho_Chi_Minh"},
    "таиланд":        {"flag": "🇹🇭", "capital": "Бангкок",    "population": 71.0,  "continent": "Азия", "tz": "Asia/Bangkok"},
    "индонезия":      {"flag": "🇮🇩", "capital": "Джакарта",   "population": 279.0, "continent": "Азия", "tz": "Asia/Jakarta"},
    "малайзия":       {"flag": "🇲🇾", "capital": "Куала-Лумпур","population": 34.0, "continent": "Азия", "tz": "Asia/Kuala_Lumpur"},
    "филиппины":      {"flag": "🇵🇭", "capital": "Манила",     "population": 117.0, "continent": "Азия", "tz": "Asia/Manila"},
    "монголия":       {"flag": "🇲🇳", "capital": "Улан-Батор", "population": 3.4,   "continent": "Азия", "tz": "Asia/Ulaanbaatar"},
    "нигерия":        {"flag": "🇳🇬", "capital": "Абуджа",     "population": 223.0, "continent": "Африка", "tz": "Africa/Lagos"},
    "юар":            {"flag": "🇿🇦", "capital": "Претория",   "population": 60.0,  "continent": "Африка", "tz": "Africa/Johannesburg"},
    "кения":          {"flag": "🇰🇪", "capital": "Найроби",    "population": 55.0,  "continent": "Африка", "tz": "Africa/Nairobi"},
    "марокко":        {"flag": "🇲🇦", "capital": "Рабат",      "population": 37.0,  "continent": "Африка", "tz": "Africa/Casablanca"},
    "алжир":          {"flag": "🇩🇿", "capital": "Алжир",      "population": 45.0,  "continent": "Африка", "tz": "Africa/Algiers"},
    "эфиопия":        {"flag": "🇪🇹", "capital": "Аддис-Абеба","population": 126.0, "continent": "Африка", "tz": "Africa/Addis_Ababa"},
    "новая зеландия": {"flag": "🇳🇿", "capital": "Веллингтон", "population": 5.2,   "continent": "Австралия", "tz": "Pacific/Auckland"},
    "куба":           {"flag": "🇨🇺", "capital": "Гавана",     "population": 11.0,  "continent": "Северная Америка", "tz": "America/Havana"},
    "колумбия":       {"flag": "🇨🇴", "capital": "Богота",     "population": 52.0,  "continent": "Южная Америка", "tz": "America/Bogota"},
    "перу":           {"flag": "🇵🇪", "capital": "Лима",       "population": 34.0,  "continent": "Южная Америка", "tz": "America/Lima"},
    "чили":           {"flag": "🇨🇱", "capital": "Сантьяго",   "population": 19.5,  "continent": "Южная Америка", "tz": "America/Santiago"},
    "венесуэла":      {"flag": "🇻🇪", "capital": "Каракас",    "population": 28.0,  "continent": "Южная Америка", "tz": "America/Caracas"},
    "ирландия":       {"flag": "🇮🇪", "capital": "Дублин",     "population": 5.1,   "continent": "Европа", "tz": "Europe/Dublin"},
    "дания":          {"flag": "🇩🇰", "capital": "Копенгаген", "population": 5.9,   "continent": "Европа", "tz": "Europe/Copenhagen"},
    "литва":          {"flag": "🇱🇹", "capital": "Вильнюс",    "population": 2.9,   "continent": "Европа", "tz": "Europe/Vilnius"},
    "латвия":         {"flag": "🇱🇻", "capital": "Рига",       "population": 1.9,   "continent": "Европа", "tz": "Europe/Riga"},
    "эстония":        {"flag": "🇪🇪", "capital": "Таллин",     "population": 1.4,   "continent": "Европа", "tz": "Europe/Tallinn"},
    "молдова":        {"flag": "🇲🇩", "capital": "Кишинёв",    "population": 2.5,   "continent": "Европа", "tz": "Europe/Chisinau"},
}

CONTINENTS = sorted(set(d["continent"] for d in COUNTRIES.values()))

user_favorites = {}
user_search_count = {}
user_quiz_score = {}
global_search_counter = Counter()
quiz_answers = {}

class SearchState(StatesGroup):
    waiting_for_country = State()

def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔍 Найти столицу", callback_data="search")
    b.button(text="🎲 Случайная страна", callback_data="random")
    b.button(text="🧠 Квиз", callback_data="quiz")
    b.button(text="📋 Список стран", callback_data="list")
    b.button(text="🌐 По континенту", callback_data="continent")
    b.button(text="🌙 Страна дня", callback_data="daily")
    b.button(text="📈 Топ запросов", callback_data="top")
    b.button(text="🏆 Лидерборд квиза", callback_data="leaderboard")
    b.button(text="⭐ Избранное", callback_data="favorites")
    b.button(text="📊 Статистика", callback_data="stats")
    b.button(text="ℹ️ О боте", callback_data="about")
    b.adjust(2, 2, 2, 2, 2, 1)
    return b.as_markup()

def back_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад в меню", callback_data="menu")
    return b.as_markup()

def ai_scope_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌍 Только про страны/столицы", callback_data="ai_scope:countries")
    b.button(text="🧠 Обо всём на свете", callback_data="ai_scope:anything")
    b.adjust(1)
    return b.as_markup()

def country_card_kb(key: str, user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    is_fav = key in user_favorites.get(user_id, set())
    fav_text = "💔 Убрать из избранного" if is_fav else "⭐ Добавить в избранное"
    b.button(text=fav_text, callback_data=f"fav:{key}")
    b.button(text="⬅️ Назад в меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()

def country_list_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, data in COUNTRIES.items():
        b.button(text=f"{data['flag']} {key.capitalize()}", callback_data=f"country:{key}")
    b.button(text="⬅️ Назад в меню", callback_data="menu")
    b.adjust(2)
    return b.as_markup()

def continent_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in CONTINENTS:
        b.button(text=f"🌐 {c}", callback_data=f"cont:{c}")
    b.button(text="⬅️ Назад в меню", callback_data="menu")
    b.adjust(2)
    return b.as_markup()

def continent_countries_kb(continent: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, data in COUNTRIES.items():
        if data["continent"] == continent:
            b.button(text=f"{data['flag']} {key.capitalize()}", callback_data=f"country:{key}")
    b.button(text="⬅️ Назад в меню", callback_data="menu")
    b.adjust(2)
    return b.as_markup()

def format_country_card(key: str) -> str:
    d = COUNTRIES[key]
    pop_str = f"~{d['population']} млн чел." if d["population"] else "нет данных"
    return (
        f"{d['flag']} <b>{key.capitalize()}</b>\n"
        f"───────────────────\n"
        f"🏛 Столица: <b>{d['capital']}</b>\n"
        f"🌐 Континент: {d['continent']}\n"
        f"👥 Население: {pop_str}"
    )

def register_search(user_id: int, key: str):
    user_search_count[user_id] = user_search_count.get(user_id, 0) + 1
    global_search_counter[key] += 1

def get_daily_country() -> str:
    today = datetime.date.today().toordinal()
    keys = list(COUNTRIES.keys())
    return keys[today % len(keys)]

def get_local_time(key: str) -> str:
    tz_name = COUNTRIES[key].get("tz")
    if not tz_name:
        return "время неизвестно"
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.datetime.now(tz)
        return now.strftime("%H:%M (%Z)")
    except Exception:
        return "не удалось определить"

async def send_country_card(target, key: str, user_id: int):
    register_search(user_id, key)
    text = format_country_card(key)
    kb = country_card_kb(key, user_id)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")

def build_quiz(user_id: int):
    correct_key = random.choice(list(COUNTRIES.keys()))
    wrong_keys = random.sample([k for k in COUNTRIES if k != correct_key], min(3, len(COUNTRIES) - 1))
    options = wrong_keys + [correct_key]
    random.shuffle(options)
    quiz_answers[user_id] = correct_key
    b = InlineKeyboardBuilder()
    for opt in options:
        b.button(text=opt.capitalize(), callback_data=f"quizans:{opt}")
    b.adjust(2)
    flag = COUNTRIES[correct_key]["flag"]
    return f"🧠 <b>Квиз:</b> какой стране принадлежит этот флаг?\n\n{flag}", b.as_markup()

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text = (
        f"👋 Привет, <b>{message.from_user.full_name}</b>!\n\n"
        f"Я — <b>Capital Bot</b> 🌍, знаю столицы {len(COUNTRIES)} стран.\n"
        f"Выбери действие ниже 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")

@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📍 Главное меню:", reply_markup=main_menu_kb())

@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "❓ <b>Команды бота:</b>\n\n"
        "/search — найти столицу по стране\n"
        "/random — случайная страна\n"
        "/quiz — квиз (угадай по флагу)\n"
        "/list — список всех стран\n"
        "/continent — фильтр по континенту\n"
        "/daily — страна дня\n"
        "/top — топ популярных запросов\n"
        "/leaderboard — таблица лидеров квиза\n"
        "/favorites — моё избранное\n"
        "/stats — моя статистика\n"
        "/ai_on — включить ИИ-помощника\n"
        "/ai_off — выключить ИИ-помощника\n"
        "/about — о боте"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("about"))
async def cmd_about(message: Message):
    text = (
        "ℹ️ <b>О боте</b>\n\n"
        "Сделан на Python + <b>aiogram 3.x</b> в рамках учебного проекта.\n"
        f"📊 В базе: {len(COUNTRIES)} стран"
    )
    await message.answer(text, reply_markup=back_kb(), parse_mode="HTML")

@dp.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_country)
    await message.answer("✍️ Напиши название страны:", reply_markup=back_kb())

@dp.message(Command("random"))
async def cmd_random(message: Message):
    key = random.choice(list(COUNTRIES.keys()))
    await send_country_card(message, key, message.from_user.id)

@dp.message(Command("list"))
async def cmd_list(message: Message):
    await message.answer("📋 Выбери страну:", reply_markup=country_list_kb())

@dp.message(Command("continent"))
async def cmd_continent(message: Message):
    await message.answer("🌐 Выбери континент:", reply_markup=continent_kb())

@dp.message(Command("daily"))
async def cmd_daily(message: Message):
    key = get_daily_country()
    time_str = get_local_time(key)
    text = format_country_card(key) + f"\n🕒 Местное время: <b>{time_str}</b>"
    kb = country_card_kb(key, message.from_user.id)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(Command("top"))
async def cmd_top(message: Message):
    if not global_search_counter:
        await message.answer("📈 Пока никто ничего не искал.", reply_markup=back_kb())
        return
    lines = ["📈 <b>Топ-5 популярных запросов:</b>\n"]
    for i, (key, count) in enumerate(global_search_counter.most_common(5), 1):
        d = COUNTRIES[key]
        lines.append(f"{i}. {d['flag']} {key.capitalize()} — {count} запрос(ов)")
    await message.answer("\n".join(lines), reply_markup=back_kb(), parse_mode="HTML")

@dp.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    if not user_quiz_score:
        await message.answer("🏆 Пока никто не проходил квиз.", reply_markup=back_kb())
        return
    top5 = sorted(user_quiz_score.items(), key=lambda x: x[1], reverse=True)[:5]
    lines = ["🏆 <b>Лидерборд квиза:</b>\n"]
    for i, (uid, score) in enumerate(top5, 1):
        lines.append(f"{i}. Игрок {uid} — {score} очков")
    await message.answer("\n".join(lines), reply_markup=back_kb(), parse_mode="HTML")

@dp.message(Command("favorites"))
async def cmd_favorites(message: Message):
    favs = user_favorites.get(message.from_user.id, set())
    if not favs:
        await message.answer("⭐ У тебя пока нет избранных стран.", reply_markup=back_kb())
        return
    lines = ["⭐ <b>Твоё избранное:</b>\n"]
    for key in favs:
        d = COUNTRIES[key]
        lines.append(f"{d['flag']} {key.capitalize()} — {d['capital']}")
    await message.answer("\n".join(lines), reply_markup=back_kb(), parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    uid = message.from_user.id
    text = (
        f"📊 <b>Твоя статистика:</b>\n\n"
        f"🔍 Поисков сделано: {user_search_count.get(uid, 0)}\n"
        f"🧠 Очков в квизе: {user_quiz_score.get(uid, 0)}\n"
        f"⭐ В избранном: {len(user_favorites.get(uid, set()))} стран"
    )
    await message.answer(text, reply_markup=back_kb(), parse_mode="HTML")

@dp.message(Command("quiz"))
async def cmd_quiz(message: Message):
    text, kb = build_quiz(message.from_user.id)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(Command("ai_on"))
async def cmd_ai_on(message: Message):
    await message.answer(
        "🤖 Включаем ИИ-помощника!\n\nПро что он должен помогать?",
        reply_markup=ai_scope_kb(),
    )

@dp.message(Command("ai_off"))
async def cmd_ai_off(message: Message):
    ai_enabled[message.from_user.id] = False
    await message.answer("🔌 ИИ-помощник выключен. Бот снова работает в обычном режиме.")

@dp.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("📍 Главное меню:", reply_markup=main_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "search")
async def cb_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_country)
    await call.message.edit_text("✍️ Напиши название страны:", reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "random")
async def cb_random(call: CallbackQuery):
    key = random.choice(list(COUNTRIES.keys()))
    await send_country_card(call, key, call.from_user.id)
    await call.answer("🎲 Случайный выбор!")

@dp.callback_query(F.data == "list")
async def cb_list(call: CallbackQuery):
    await call.message.edit_text("📋 Выбери страну:", reply_markup=country_list_kb())
    await call.answer()

@dp.callback_query(F.data == "continent")
async def cb_continent(call: CallbackQuery):
    await call.message.edit_text("🌐 Выбери континент:", reply_markup=continent_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("cont:"))
async def cb_continent_countries(call: CallbackQuery):
    continent = call.data.split(":", 1)[1]
    await call.message.edit_text(
        f"🌐 Страны континента <b>{continent}</b>:",
        reply_markup=continent_countries_kb(continent),
        parse_mode="HTML",
    )
    await call.answer()

@dp.callback_query(F.data == "daily")
async def cb_daily(call: CallbackQuery):
    key = get_daily_country()
    time_str = get_local_time(key)
    text = format_country_card(key) + f"\n🕒 Местное время: <b>{time_str}</b>"
    kb = country_card_kb(key, call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("🌙 Страна дня!")

@dp.callback_query(F.data == "top")
async def cb_top(call: CallbackQuery):
    if not global_search_counter:
        await call.message.edit_text("📈 Пока никто ничего не искал.", reply_markup=back_kb())
        await call.answer()
        return
    lines = ["📈 <b>Топ-5 популярных запросов:</b>\n"]
    for i, (key, count) in enumerate(global_search_counter.most_common(5), 1):
        d = COUNTRIES[key]
        lines.append(f"{i}. {d['flag']} {key.capitalize()} — {count} запрос(ов)")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "leaderboard")
async def cb_leaderboard(call: CallbackQuery):
    if not user_quiz_score:
        await call.message.edit_text("🏆 Пока никто не проходил квиз.", reply_markup=back_kb())
        await call.answer()
        return
    top5 = sorted(user_quiz_score.items(), key=lambda x: x[1], reverse=True)[:5]
    lines = ["🏆 <b>Лидерборд квиза:</b>\n"]
    for i, (uid, score) in enumerate(top5, 1):
        lines.append(f"{i}. Игрок {uid} — {score} очков")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "favorites")
async def cb_favorites(call: CallbackQuery):
    favs = user_favorites.get(call.from_user.id, set())
    if not favs:
        await call.message.edit_text("⭐ У тебя пока нет избранных стран.", reply_markup=back_kb())
        await call.answer()
        return
    lines = ["⭐ <b>Твоё избранное:</b>\n"]
    for key in favs:
        d = COUNTRIES[key]
        lines.append(f"{d['flag']} {key.capitalize()} — {d['capital']}")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "stats")
async def cb_stats(call: CallbackQuery):
    uid = call.from_user.id
    text = (
        f"📊 <b>Твоя статистика:</b>\n\n"
        f"🔍 Поисков сделано: {user_search_count.get(uid, 0)}\n"
        f"🧠 Очков в квизе: {user_quiz_score.get(uid, 0)}\n"
        f"⭐ В избранном: {len(user_favorites.get(uid, set()))} стран"
    )
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "about")
async def cb_about(call: CallbackQuery):
    text = (
        "ℹ️ <b>О боте</b>\n\n"
        "Сделан на Python + <b>aiogram 3.x</b> в рамках учебного проекта.\n"
        f"📊 В базе: {len(COUNTRIES)} стран"
    )
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "quiz")
async def cb_quiz(call: CallbackQuery):
    text, kb = build_quiz(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("quizans:"))
async def cb_quiz_answer(call: CallbackQuery):
    uid = call.from_user.id
    chosen = call.data.split(":", 1)[1]
    correct = quiz_answers.get(uid)

    if chosen == correct:
        user_quiz_score[uid] = user_quiz_score.get(uid, 0) + 1
        result_text = f"✅ Правильно! Это была {correct.capitalize()} {COUNTRIES[correct]['flag']}"
    else:
        result_text = f"❌ Неверно. Правильный ответ: {correct.capitalize()} {COUNTRIES[correct]['flag']}"

    b = InlineKeyboardBuilder()
    b.button(text="➡️ Следующий вопрос", callback_data="quiz")
    b.button(text="⬅️ В меню", callback_data="menu")
    b.adjust(1)

    await call.message.edit_text(result_text, reply_markup=b.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("ai_scope:"))
async def cb_ai_scope(call: CallbackQuery):
    scope = call.data.split(":", 1)[1]
    uid = call.from_user.id
    ai_scope[uid] = scope
    ai_enabled[uid] = True
    scope_label = "странах и столицах" if scope == "countries" else "чём угодно"
    await call.message.edit_text(
        f"✅ ИИ-помощник включён! Теперь можешь спрашивать меня о {scope_label}.\n\n"
        f"Чтобы выключить — напиши /ai_off",
    )
    await call.answer("🤖 ИИ включён!")

@dp.callback_query(F.data.startswith("country:"))
async def cb_country_card(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    await send_country_card(call, key, call.from_user.id)
    await call.answer()

@dp.callback_query(F.data.startswith("fav:"))
async def cb_toggle_favorite(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    uid = call.from_user.id
    favs = user_favorites.setdefault(uid, set())
    if key in favs:
        favs.remove(key)
        note = "💔 Убрано из избранного"
    else:
        favs.add(key)
        note = "⭐ Добавлено в избранное"
    await call.message.edit_reply_markup(reply_markup=country_card_kb(key, uid))
    await call.answer(note)

@dp.message(SearchState.waiting_for_country)
async def process_search(message: Message, state: FSMContext):
    query = message.text.strip().lower()
    if query in COUNTRIES:
        await send_country_card(message, query, message.from_user.id)
    else:
        await message.answer(
            "🤷 Такой страны нет в базе. Попробуй ещё раз или вернись в меню.",
            reply_markup=back_kb(),
        )

@dp.message()
async def fallback(message: Message):
    query = message.text.strip().lower()

    if query in COUNTRIES:
        await send_country_card(message, query, message.from_user.id)
        return

    if ai_enabled.get(message.from_user.id):
        thinking = await message.answer("🤖 Думаю...")
        answer = await ask_gemini(message.from_user.id, message.text)
        await thinking.edit_text(answer)
        return

    await message.answer(
        "🤔 Не понял. Нажми /menu, чтобы открыть меню, или включи /ai_on для ИИ-помощника.",
    )

async def on_startup(bot: Bot):
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info(f"Webhook установлен: {WEBHOOK_URL}")
    else:
        logging.info("WEBHOOK_URL не задан, запуск в режиме polling")

def main():
    app = web.Application()
    
    async def handle_ping(request):
        return web.Response(text="Bot is running!")

    app.router.add_get("/", handle_ping)

    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    setup_application(app, dp, bot=bot)
    
    dp.startup.register(on_startup)
    
    logging.info(f"Запуск веб-сервера на порту {WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()