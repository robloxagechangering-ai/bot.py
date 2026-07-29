import asyncio
import logging
import sqlite3
import time
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================================================
# КОНФИГУРАЦИЯ
# ==================================================
BOT_TOKEN = "7946724552:AAGbTOLi_6E3cYHvvfH-PtK9Nk_7qZgSnYU"
ADMIN_ID = 8625870625
SELLER_USERNAME = "@goIanrexxx"
SUPPORT_USERNAME = "@NovasHelper"
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(level=logging.INFO)

# ==================================================
# БАЗА ДАННЫХ И КЕШ
# ==================================================
cart_cache = {}

def init_db():
    conn = sqlite3.connect("shop.db", timeout=10)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, cart TEXT)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            total INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_order_to_db(user_id: int, items_str: str, total: int) -> int:
    conn = sqlite3.connect("shop.db", timeout=10)
    cursor = conn.cursor()
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO orders (user_id, items, total, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (user_id, items_str, total, created_at)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_pending_orders():
    conn = sqlite3.connect("shop.db", timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT order_id, user_id, items, total, created_at FROM orders WHERE status = 'pending'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_order_done(order_id: int) -> bool:
    conn = sqlite3.connect("shop.db", timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT order_id FROM orders WHERE order_id = ? AND status = 'pending'", (order_id,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return False
    cursor.execute("UPDATE orders SET status = 'done' WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()
    return True

# ==================================================
# ТОВАРЫ
# ==================================================
PRODUCTS = {
    "sets": [
        ("Celestial Set", 1650), ("Alien set", 1450), ("Sakura set", 1250), ("Sun set", 1200),
        ("Snow set", 1100), ("Bauble set", 550), ("Bloom set", 750), ("Ocean set", 700),
        ("Xeno set", 650), ("FlowerWood set", 700), ("Corrupt set", 550), ("Pearl set", 200),
        ("Bat set", 150), ("Beach Set", 500), ("Borealis set", 150), ("Ice set", 350),
        ("Candy set", 400), ("Spectre set", 150), ("Blizzard set", 700), ("Full Elderwood set", 200)
    ],
    "ancients": [
        ("Celestial", 750), ("Vampire's Axe", 550), ("Harvester", 175),
        ("Icepiercer", 150), ("Icebreaker", 85), ("Icewing", 25)
    ],
    "chromas": [
        ("Chroma Heart Wand", 1450), ("Chroma Watergun", 1150), ("Chroma Sweet", 900),
        ("Chroma Treat", 900), ("Chroma Beachy", 950), ("Chroma Sands", 950),
        ("Chroma Ornament", 750), ("Chroma DarkBringer", 100),
        ("Chroma LightBringer", 100), ("Chroma Luger", 85),
        ("Chroma Laser", 80), ("Chroma Swirly Gun", 75)
    ],
    "godlies": [
        ("Constellation", 700), ("Turkey", 700), ("Alien Beam", 675), ("DarkShot", 630),
        ("DarkSword", 600), ("RayGun", 700), ("Blossom", 700), ("Sakura", 590),
        ("SnowCannon", 500), ("Sunrise", 575), ("Bauble", 400), ("Sunset", 500),
        ("Soul", 550), ("Spirit", 550), ("Rainbow Gun", 400),
        ("Rainbow", 400), ("Flora", 300), ("Bloom", 350), ("Heart Wand", 325),
        ("Ocean", 275), ("Waves", 270), ("IceCream", 400), ("XenoKnife", 300),
        ("Xenoshot", 270), ("FlowerWood Gun", 195), ("Flowerwood", 175),
        ("Snow Storm", 350), ("Beachy", 300), ("Sands", 300), ("Treat", 250),
        ("Sweet", 250), ("Borealis", 100), ("Australis", 100), ("Bat", 100),
        ("Pearl", 85), ("WaterGun", 250), ("PearlShine", 85), ("Candy", 85),
        ("HeartBlade", 80), ("Luger", 50), ("RedLuger", 50)
    ]
}

ALL_PRODUCTS = {}
for cat, items in PRODUCTS.items():
    for name, price in items:
        ALL_PRODUCTS[name] = price

# ==================================================
# КЛАВИАТУРЫ
# ==================================================
def get_main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Как оплатить", callback_data="how_to_pay")
    builder.button(text="💎 МАГАЗИН", callback_data="shop_menu")
    builder.button(text="💵 О магазине", callback_data="about_shop")
    builder.button(text="✍️ Поддержка", callback_data="support")
    builder.button(text="🛒 КОРЗИНА", callback_data="view_cart")
    builder.adjust(1, 1, 2, 1)
    return builder.as_markup()

def get_shop_categories_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏹 СЕТЫ", callback_data="cat_sets")
    builder.button(text="📜 Ancients", callback_data="cat_ancients")
    builder.button(text="🌈 Chromas", callback_data="cat_chromas")
    builder.button(text="🌸 Godlies", callback_data="cat_godlies_page_1")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_godlies_page_kb(page: int):
    builder = InlineKeyboardBuilder()
    godlies = PRODUCTS["godlies"]
    per_page = 15
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = godlies[start_idx:end_idx]

    for name, price in page_items:
        builder.button(text=f"{name} — {price}₽", callback_data=f"buy_{name}")
    
    builder.adjust(1)
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_godlies_page_{page-1}"))
    if end_idx < len(godlies):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"cat_godlies_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="🔙 К категориям", callback_data="shop_menu"))
    return builder.as_markup()

def get_category_items_kb(cat_key: str):
    builder = InlineKeyboardBuilder()
    items = PRODUCTS[cat_key]
    for name, price in items:
        builder.button(text=f"{name} — {price}₽", callback_data=f"buy_{name}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 К категориям", callback_data="shop_menu"))
    return builder.as_markup()

def get_item_confirm_kb(item_name: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Добавить в корзину", callback_data=f"addcart_{item_name}")
    builder.button(text="🔙 Назад", callback_data="shop_menu")
    builder.button(text="🏠 В главное", callback_data="main_menu")
    builder.adjust(1, 2)
    return builder.as_markup()

def get_cart_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    user_cart = cart_cache.get(user_id, [])
    
    if user_cart:
        for idx in range(len(user_cart)):
            builder.button(text=f"❌ Удалить [{idx + 1}]", callback_data=f"remove_item_{idx}")
        builder.adjust(2)
        builder.row(
            InlineKeyboardButton(text="✅ Оформить", callback_data="checkout"),
            InlineKeyboardButton(text="🔄 Очистить", callback_data="clear_cart")
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()

# ==================================================
# ТЕКСТЫ
# ==================================================
START_TEXT = (
    "👋 ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН 👋\n"
    "NOVASS SHOP 🛍️ ЗДЕСЬ МОЖНО КУПИТЬ КРУТЫЕ СКИНЫ 💎 ИЗ ИГРЫ 🩸 MURDER MYSTERY 2 😎"
)

HOW_TO_PAY_TEXT = (
    "💳 Как оплатить заказ?\n"
    "Мы работаем по всему миру — без привязки к странам, банкам и дурацким картам.\n"
    "Покупать карты для каждой страны — дорого, геморройно и невыгодно.\n"
    "Поэтому мы принимаем два надёжных способа оплаты:\n"
    "💸 USDT (криптовалюта)\n"
    "⭐ Telegram Stars\n\n"
    "Если у тебя пока нет ни крипты, ни звёзд — не переживай.\n"
    "Всё решается за 5–15 минут, даже если ты делаешь это впервые.\n\n"
    "1️⃣ СПОСОБ — КРИПТОВАЛЮТА (USDT)\n"
    "Самый быстрый и приватный способ.\n"
    "Покупай USDT через официальный бот Telegram — @send.\n"
    "Данные можно вводить любые, даже вымышленные — никто не проверяет.\n\n"
    "📱 Пошаговый туториал:\n"
    "1. Открой бота @send\n"
    "2. Нажми /start и пройди базовую настройку\n"
    "3. Снова нажми /start → появится кнопка P2P\n"
    "4. Нажми P2P → выбери «Оплата и валюта»\n"
    "5. Укажи валюту своей страны (например, 🇷🇺 Россия — Рубли)\n"
    "6. Нажми «Назад» — вернёшься в меню P2P\n"
    "7. Выбери «Купить» → укажи USDT (Tether)\n"
    "8. Выбери свой банк и подходящее предложение\n"
    "9. После покупки свяжись с продавцом — он объяснит детали обмена\n\n"
    "🧠 Альтернатива:\n"
    "Есть и другие магазины криптовалют — туториалы легко найти на YouTube.\n\n"
    "2️⃣ СПОСОБ — TELEGRAM STARS ⭐\n"
    "Если крипта — не твоё, используй Telegram Stars.\n"
    "Это встроенная валюта Telegram, которая работает в любой стране.\n\n"
    "📱 Пошаговый туториал:\n"
    "1. Открой бота @PremiumBot\n"
    "2. Нажми /start → увидишь синюю кнопку Menu\n"
    "3. Выбери Buy or Gift Telegram Stars → /stars\n"
    "4. Выбери нужную сумму (например, 100, 500, 1000 звёзд)\n"
    "5. Свяжись с владельцем сделки и сообщи, на какую сумму тебе нужны звёзды\n"
    "6. Дождись ответа (обычно от 5 до 30 минут)\n"
    "7. Когда продавец назовёт сумму — выбери «Подарить звёзды»\n"
    "8. Введи его юзернейм и отправь звёзды\n"
    "9. После этого начинается сделка ✅"
)

ABOUT_TEXT = (
    "👋 Добро пожаловать в NOVA SHOP MM2\n"
    "✅ 200-500 положительных отзывов\n"
    "⏱ Выдача 5-30 минут\n"
    "💰 Самые дешёвые цены"
)

SUPPORT_TEXT = f"✍️ Поддержка: {SUPPORT_USERNAME}\nБыстрый ответ на все вопросы."

# ==================================================
# ВЕБ-СЕРВЕР (ДЛЯ UPTIMEROBOT)
# ==================================================
async def handle_ping(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {PORT}")

# ==================================================
# ХЕНДЛЕРЫ
# ==================================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(START_TEXT, reply_markup=get_main_menu_kb())

@dp.message(Command("orders"))
async def cmd_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    orders = get_pending_orders()
    if not orders:
        await message.answer("📦 Активных заказов нет.")
        return
    
    text = "📋 **Активные заказы (pending):**\n\n"
    for o_id, u_id, items, total, created_at in orders:
        text += f"🆔 **Заказ #{o_id}**\n👤 User ID: `{u_id}`\n🛍️ Товары:\n{items}\n💰 Итого: {total} руб\n📅 {created_at}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("done"))
async def cmd_done(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Используйте: `/done <order_id>`", parse_mode="Markdown")
        return
    
    order_id = int(args[1])
    if mark_order_done(order_id):
        await message.answer(f"✅ Заказ #{order_id} отмечен как выполненный.")
    else:
        await message.answer(f"❌ Заказ #{order_id} не найден или уже выполнен.")

# ==================================================
# ЗАПУСК (ПОЛЛИНГ + ВЕБ-СЕРВЕР)
# ==================================================
async def main():
    init_db()
    
    # Запускаем веб-сервер в фоне
    asyncio.create_task(start_web_server())
    
    # Удаляем вебхук при старте
    await bot.delete_webhook(drop_pending_updates=True)
    
    logging.info("Запуск Telegram-бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
