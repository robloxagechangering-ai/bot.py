import os
import asyncio
import logging
import sqlite3
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================================================
# НАСТРОЙКИ
# ==================================================
BOT_TOKEN = "7946724552:AAHLQfvrJxw5QFjlEB3XFRPUoBD9_0gT2rw"
ADMIN_IDS = [8625870625]
PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.WARNING)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ==================================================
# БАЗА ДАННЫХ
# ==================================================
conn = sqlite3.connect("shop.db", check_same_thread=False, timeout=5)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    cart TEXT DEFAULT '[]'
)
""")

cur.execute("""
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

# ==================================================
# КЕШ КОРЗИН
# ==================================================
cart_cache = {}

def get_cart(user_id):
    if user_id in cart_cache:
        return cart_cache[user_id]
    cur.execute("SELECT cart FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    if result:
        cart = eval(result[0])
    else:
        cart = []
        cur.execute("INSERT INTO users (user_id, cart) VALUES (?, ?)", (user_id, "[]"))
        conn.commit()
    cart_cache[user_id] = cart
    return cart

def save_cart(user_id, cart):
    cart_cache[user_id] = cart
    cur.execute("UPDATE users SET cart = ? WHERE user_id = ?", (str(cart), user_id))
    conn.commit()

def add_to_cart(user_id, item):
    cart = get_cart(user_id)
    if len(cart) >= 25:
        return False, "Корзина заполнена (максимум 25 товаров)"
    if item in cart:
        return False, "Этот товар уже в корзине"
    cart.append(item)
    save_cart(user_id, cart)
    return True, f"{item} добавлен в корзину!"

def remove_from_cart(user_id, index):
    cart = get_cart(user_id)
    if 1 <= index <= len(cart):
        removed = cart.pop(index - 1)
        save_cart(user_id, cart)
        return True, f"{removed} удалён из корзины"
    return False, "Неверный номер товара"

def get_cart_total(cart):
    return sum(PRICES.get(item, 0) for item in cart)

# ==================================================
# ЦЕНЫ И КАТЕГОРИИ
# ==================================================
PRICES = {
    "Celestial Set": 1650, "Alien set": 1450, "Sakura set": 1250,
    "Sun set": 1200, "Snow set": 1100, "Bauble set": 550,
    "Bloom set": 750, "Ocean set": 700, "Xeno set": 650,
    "FlowerWood set": 700, "Corrupt set": 550, "Pearl set": 200,
    "Bat set": 150, "Beach Set": 500, "Borealis set": 150,
    "Ice set": 350, "Candy set": 400, "Spectre set": 150,
    "Blizzard set": 700, "Full Elderwood set": 200,
    "Celestial": 750, "Vampire's Axe": 550, "Harvester": 175,
    "Icepiercer": 150, "Icebreaker": 85, "Icewing": 25,
    "Chroma Heart Wand": 1450, "Chroma Watergun": 1150,
    "Chroma Sweet": 900, "Chroma Treat": 900, "Chroma Beachy": 950,
    "Chroma Sands": 950, "Chroma Ornament": 750,
    "Chroma DarkBringer": 100, "Chroma LightBringer": 100,
    "Chroma Luger": 85, "Chroma Laser": 80, "Chroma Swirly Gun": 75,
    "Constellation": 700, "Turkey": 700, "Alien Beam": 675,
    "DarkShot": 630, "DarkSword": 600, "RayGun": 700,
    "Blossom": 700, "Sakura": 590, "SnowCannon": 500,
    "Sunrise": 575, "Bauble": 400, "Sunset": 500,
    "Soul": 550, "Spirit": 550, "Rainbow Gun": 400,
    "Rainbow": 400, "Flora": 300, "Bloom": 350,
    "Heart Wand": 325, "Ocean": 275, "Waves": 270,
    "IceCream": 400, "XenoKnife": 300, "Xenoshot": 270,
    "FlowerWood Gun": 195, "Flowerwood": 175, "Snow Storm": 350,
    "Beachy": 300, "Sands": 300, "Treat": 250,
    "Sweet": 250, "Borealis": 100, "Australis": 100,
    "Bat": 100, "Pearl": 85, "WaterGun": 250,
    "PearlShine": 85, "Candy": 85, "HeartBlade": 80,
    "Luger": 50, "RedLuger": 50
}

CATEGORIES = {
    "sets": ["Celestial Set", "Alien set", "Sakura set", "Sun set", "Snow set",
             "Bauble set", "Bloom set", "Ocean set", "Xeno set", "FlowerWood set",
             "Corrupt set", "Pearl set", "Bat set", "Beach Set", "Borealis set",
             "Ice set", "Candy set", "Spectre set", "Blizzard set", "Full Elderwood set"],
    "ancients": ["Celestial", "Vampire's Axe", "Harvester", "Icepiercer", "Icebreaker", "Icewing"],
    "chromas": ["Chroma Heart Wand", "Chroma Watergun", "Chroma Sweet", "Chroma Treat",
                "Chroma Beachy", "Chroma Sands", "Chroma Ornament", "Chroma DarkBringer",
                "Chroma LightBringer", "Chroma Luger", "Chroma Laser", "Chroma Swirly Gun"],
    "godlies": ["Constellation", "Turkey", "Alien Beam", "DarkShot", "DarkSword",
                "RayGun", "Blossom", "Sakura", "SnowCannon", "Sunrise", "Bauble",
                "Sunset", "Soul", "Spirit", "Rainbow Gun", "Rainbow", "Flora",
                "Bloom", "Heart Wand", "Ocean", "Waves", "IceCream", "XenoKnife",
                "Xenoshot", "FlowerWood Gun", "Flowerwood", "Snow Storm", "Beachy",
                "Sands", "Treat", "Sweet", "Borealis", "Australis", "Bat", "Pearl",
                "WaterGun", "PearlShine", "Candy", "HeartBlade", "Luger", "RedLuger"]
}

# ==================================================
# КЛАВИАТУРЫ
# ==================================================
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Как оплатить", callback_data="how_to_pay"))
    builder.row(InlineKeyboardButton(text="💎 МАГАЗИН", callback_data="shop"))
    builder.row(InlineKeyboardButton(text="💵 О магазине", callback_data="about"))
    builder.row(InlineKeyboardButton(text="✍️ Поддержка", callback_data="support"))
    builder.row(InlineKeyboardButton(text="🛒 КОРЗИНА", callback_data="cart"))
    return builder.as_markup()

def shop_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏹 СЕТЫ", callback_data="category_sets"))
    builder.row(InlineKeyboardButton(text="📜 Ancients", callback_data="category_ancients"))
    builder.row(InlineKeyboardButton(text="🌈 Chromas", callback_data="category_chromas"))
    builder.row(InlineKeyboardButton(text="🌸 Godlies", callback_data="category_godlies"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()

# ==================================================
# ОБРАБОТЧИКИ
# ==================================================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    get_cart(message.from_user.id)
    text = """👋 ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН 👋

NOVASS SHOP 🛍️ ЗДЕСЬ МОЖНО
КУПИТЬ КРУТЫЕ СКИНЫ 💎 ИЗ ИГРЫ
🩸 MURDER MYSTERY 2 😎

Чтобы посмотреть цены и другие вещи в нашем магазине нажмите на кнопки 👇"""
    await message.answer(text, reply_markup=main_menu())

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(call: CallbackQuery):
    text = """👋 ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН 👋

NOVASS SHOP 🛍️ ЗДЕСЬ МОЖНО
КУПИТЬ КРУТЫЕ СКИНЫ 💎 ИЗ ИГРЫ
🩸 MURDER MYSTERY 2 😎

Чтобы посмотреть цены и другие вещи в нашем магазине нажмите на кнопки 👇"""
    await call.message.edit_text(text, reply_markup=main_menu())
    await call.answer()

# ==================================================
# 1. КАК ОПЛАТИТЬ
# ==================================================
@dp.callback_query(F.data == "how_to_pay")
async def how_to_pay(call: CallbackQuery):
    text = """💳 Как оплатить заказ?

Мы работаем по всему миру — без привязки к странам, банкам и дурацким картам.
Покупать карты для каждой страны — дорого, геморройно и невыгодно.

Поэтому мы принимаем два надёжных способа оплаты:

💸 USDT (криптовалюта)
⭐ Telegram Stars

Если у тебя пока нет ни крипты, ни звёзд — не переживай.
Всё решается за 5–15 минут, даже если ты делаешь это впервые.

1️⃣ СПОСОБ — КРИПТОВАЛЮТА (USDT)

Самый быстрый и приватный способ.
Покупай USDT через официальный бот Telegram — @send.
Данные можно вводить любые, даже вымышленные — никто не проверяет.

📱 Пошаговый туториал:

1. Открой бота @send
2. Нажми /start и пройди базовую настройку
3. Снова нажми /start → появится кнопка P2P
4. Нажми P2P → выбери «Оплата и валюта»
5. Укажи валюту своей страны (например, 🇷🇺 Россия — Рубли)
6. Нажми «Назад» — вернёшься в меню P2P
7. Выбери «Купить» → укажи USDT (Tether)
8. Выбери свой банк и подходящее предложение
9. После покупки свяжись с продавцом — он объяснит детали обмена

🧠 Альтернатива:
Есть и другие магазины криптовалют — туториалы легко найти на YouTube.

2️⃣ СПОСОБ — TELEGRAM STARS ⭐

Если крипта — не твоё, используй Telegram Stars.
Это встроенная валюта Telegram, которая работает в любой стране.

📱 Пошаговый туториал:

1. Открой бота @PremiumBot
2. Нажми /start → увидишь синюю кнопку Menu
3. Выбери Buy or Gift Telegram Stars → /stars
4. Выбери нужную сумму (например, 100, 500, 1000 звёзд)
5. Свяжись с владельцем сделки и сообщи, на какую сумму тебе нужны звёзды
6. Дождись ответа (обычно от 5 до 30 минут)
7. Когда продавец назовёт сумму — выбери «Подарить звёзды»
8. Введи его юзернейм и отправь звёзды
9. После этого начинается сделка ✅"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

# ==================================================
# 2. МАГАЗИН
# ==================================================
@dp.callback_query(F.data == "shop")
async def shop_callback(call: CallbackQuery):
    await call.message.edit_text("🛍️ Выберите тип оружия (Редкость):", reply_markup=shop_menu())
    await call.answer()

@dp.callback_query(F.data == "back_to_shop")
async def back_to_shop(call: CallbackQuery):
    await call.message.edit_text("🛍️ Выберите тип оружия (Редкость):", reply_markup=shop_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("category_"))
async def category_callback(call: CallbackQuery):
    category = call.data.split("_")[1]
    page = 1
    if "_page_" in call.data:
        category = call.data.split("_")[1]
        page = int(call.data.split("_")[3])

    items = CATEGORIES.get(category, [])
    items_per_page = 15
    total_pages = (len(items) + items_per_page - 1) // items_per_page
    start = (page - 1) * items_per_page
    end = start + items_per_page
    page_items = items[start:end]

    titles = {"sets": "🏹 Сеты:", "ancients": "📜 Ancients:", "chromas": "🌈 Chromas:", "godlies": "🌸 Godlies:"}
    title = titles.get(category, "Выберите:")

    builder = InlineKeyboardBuilder()
    for item in page_items:
        builder.row(InlineKeyboardButton(text=f"{item} - {PRICES.get(item, 0)} руб", callback_data=f"view_{item}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_shop"))
    builder.row(InlineKeyboardButton(text="🏠 В главное", callback_data="main_menu"))

    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"category_{category}_page_{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
        if page < total_pages:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"category_{category}_page_{page+1}"))
        builder.row(*nav)

    await call.message.edit_text(title, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("view_"))
async def view_item(call: CallbackQuery):
    item = call.data.replace("view_", "")
    price = PRICES.get(item, 0)
    text = f"""✅ Вы уверены, что хотите выбрать?

Название: {item}
Цена: {price} руб
В наличии: 1 шт

Выберите действие:"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"add_{item}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_category"))
    builder.row(InlineKeyboardButton(text="🏠 В главное", callback_data="main_menu"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data == "back_to_category")
async def back_to_category(call: CallbackQuery):
    await call.message.edit_text("🛍️ Выберите тип оружия (Редкость):", reply_markup=shop_menu())
    await call.answer()

# ==================================================
# 3. О МАГАЗИНЕ
# ==================================================
@dp.callback_query(F.data == "about")
async def about_callback(call: CallbackQuery):
    text = """👋 Добро пожаловать в NOVA SHOP MM2

✅ 200-500 положительных отзывов
⏱ Выдача 5-30 минут
💰 Самые дешёвые цены"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

# ==================================================
# 4. ПОДДЕРЖКА
# ==================================================
@dp.callback_query(F.data == "support")
async def support_callback(call: CallbackQuery):
    text = """✍️ Поддержка: @NovasHelper

Быстрый ответ на все вопросы."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

# ==================================================
# 5. КОРЗИНА
# ==================================================
@dp.callback_query(F.data == "cart")
async def cart_callback(call: CallbackQuery):
    user_id = call.from_user.id
    cart = get_cart(user_id)
    if not cart:
        text = "🛒 Ваша корзина пуста"
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
        await call.message.edit_text(text, reply_markup=builder.as_markup())
        await call.answer()
        return

    text = "🛒 КОРЗИНА (лимит 25)\n\n"
    total = 0
    for i, item in enumerate(cart, 1):
        price = PRICES.get(item, 0)
        total += price
        text += f"{i}. {item} - {price} руб\n"
    text += f"\n💰 ИТОГО: {total} руб"

    builder = InlineKeyboardBuilder()
    for i in range(1, min(len(cart) + 1, 26)):
        builder.row(InlineKeyboardButton(text=f"❌ Удалить {i}", callback_data=f"del_{i}"))
    builder.row(InlineKeyboardButton(text="✅ Оформить", callback_data="checkout"))
    builder.row(InlineKeyboardButton(text="🔄 Очистить", callback_data="clear_cart"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart_callback(call: CallbackQuery):
    user_id = call.from_user.id
    item = call.data.replace("add_", "")
    success, msg = add_to_cart(user_id, item)
    await call.answer(msg, show_alert=True)
    if success:
        await back_to_shop(call)

@dp.callback_query(F.data.startswith("del_"))
async def remove_from_cart_callback(call: CallbackQuery):
    user_id = call.from_user.id
    index = int(call.data.replace("del_", ""))
    success, msg = remove_from_cart(user_id, index)
    await call.answer(msg, show_alert=True)
    await cart_callback(call)

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_callback(call: CallbackQuery):
    user_id = call.from_user.id
    save_cart(user_id, [])
    await call.answer("Корзина очищена", show_alert=True)
    await cart_callback(call)

@dp.callback_query(F.data == "checkout")
async def checkout_callback(call: CallbackQuery):
    user_id = call.from_user.id
    cart = get_cart(user_id)
    if not cart:
        await call.answer("Корзина пуста", show_alert=True)
        return

    total = get_cart_total(cart)
    items_text = "\n".join([f"{i+1}. {item} - {PRICES.get(item, 0)} руб" for i, item in enumerate(cart)])

    cur.execute("""
        INSERT INTO orders (user_id, items, total, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, str(cart), total, datetime.now().isoformat()))
    conn.commit()
    order_id = cur.lastrowid

    text = f"""✅ ЗАКАЗ #{order_id} ОФОРМЛЕН!

Ваши товары:
{items_text}

💰 ИТОГО: {total} руб

💳 Для оплаты используйте способы из раздела «Как оплатить заказ»

⏱ Ожидайте выдачи (5-30 минут)

📩 Свяжитесь с продавцом: @goIanrexxx"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\nПользователь: {call.from_user.id}\nТовары: {items_text}\nИтого: {total} руб")

    save_cart(user_id, [])

# ==================================================
# АДМИН-КОМАНДЫ
# ==================================================
@dp.message(Command("orders"))
async def cmd_orders(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    cur.execute("SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC")
    orders = cur.fetchall()
    if not orders:
        await message.answer("Нет активных заказов")
        return
    text = "📋 АКТИВНЫЕ ЗАКАЗЫ:\n\n"
    for order in orders:
        order_id, user_id, items, total, status, created = order
        text += f"#{order_id} | {user_id} | {total} руб | {created[:16]}\n"
    await message.answer(text)

@dp.message(Command("done"))
async def cmd_done(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Используйте: /done <order_id>")
        return
    order_id = args[1]
    cur.execute("UPDATE orders SET status = 'completed' WHERE order_id = ?", (order_id,))
    conn.commit()
    await message.answer(f"✅ Заказ #{order_id} выполнен")

# ==================================================
# ВЕБ-СЕРВЕР (UptimeRobot)
# ==================================================
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text="OK"))
    app.router.add_get('/ping', lambda request: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=PORT)
    await site.start()
    await asyncio.Event().wait()

# ==================================================
# ЗАПУСК (с авто-перезапуском)
# ==================================================
async def main():
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await asyncio.gather(
                dp.start_polling(bot),
                start_web_server()
            )
        except Exception as e:
            logging.error(f"Бот упал: {e}. Перезапуск через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
