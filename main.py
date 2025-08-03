import os
import random
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db

# Firebase инициализация
try:
    cr = credentials.Certificate("creds/katanawtfbot-firebase-adminsdk-fbsvc-ec711b11db.json")
    firebase_admin.initialize_app(cr, {
        "databaseURL": "https://katanawtfbot-default-rtdb.firebaseio.com/"
    })

    firebase_enabled = True
    print("✅ Firebase Realtime Database подключен успешно!")

    # Запись тестовых данных
    ref = db.reference("/katana")
    ref.set({"status": "online"})

    # Получение данных
    data = ref.get()
    print("📦 Данные из Firebase:", data)

except Exception as e:
    firebase_enabled = False
    print(f"❌ Ошибка подключения Firebase: {e}")

# Store user data in memory
user_balances = {}
active_games = {}
free_cooldowns = {}  # Track when users last used /free command
farm_values = {}  # Track farm values for users
max_farm_values = {}  # Track maximum farm values
farm_cooldowns = {}  # Track farm cooldowns
case_cooldowns = {}  # Track case opening cooldowns
user_inventories = {}  # Track user inventories
item_experience = {}  # Track item experience
item_levels = {}  # Track item levels
farm_fail_chances = {}  # Track farm fail chances for users
blackjack_games = {}  # Track active blackjack games
crash_games = {}  # Track active crash games
game_locks = {}  # Для предотвращения дублирования сообщений

# Game configuration
MIN_BET = 5
TOTAL_TILES = 25  # Changed to 25 tiles
ROWS = 5  # Changed to 5 rows
COLS = 5  # Changed to 5 columns
FREE_COINS = 10
FREE_COOLDOWN_MINUTES = 25
FARM_COOLDOWN_MINUTES = 5  # Changed from 30 to 5 minutes
FARM_STARTING_VALUE = 5
MAX_FARM_VALUE = 500  # Maximum value farm can produce
FARM_FAIL_CHANCE = 10  # Percentage chance of failing
CASE_COOLDOWN_SECONDS = 5  # Anti-spam cooldown for case opening
POISONOUS_MINE_CHANCE = 40  # Percentage chance of mine being poisonous
ADMIN_ID = 1820934194  # ID администратора

# Experience configuration
EXP_PER_WIN = {
    "mines": 10,
    "coinflip": 5,
    "blackjack": 8,
    "crash": 12
}
MAX_EXP_BY_LEVEL = {
    1: 100,
    2: 250,
    3: 500,
    4: 1000,
    5: 2000
}
MAX_ITEM_LEVEL = 5  # Maximum level for items

# Case configuration
CASE_COSTS = {
    "1": 35  # Bronze case cost
}

CASE_PRIZES = {
    "1": [
        {"emoji": "💎", "value": 45, "chance": 30},
        {"emoji": "💵", "value": 20, "chance": 60},
        {"emoji": "💰", "value": 85, "chance": 10}
    ]
}

# Shop items
SHOP_ITEMS = {
    "1": {
        "id": "1",
        "name": "Защитная аура",
        "emoji": "🛡️",
        "description": "10% шанс спастись от мины в игре Mines (одноразовое использование)",
        "price": 150,
        "upgrades": {
            1: "Базовая защитная аура (10% шанс защиты)",
            2: "Улучшенная защитная аура (15% шанс защиты)",
            3: "Продвинутая защитная аура (20% шанс защиты)",
            4: "Элитная защитная аура (25% шанс защиты)",
            5: "Легендарная защитная аура (30% шанс защиты)"
        }
    },
    "2": {
        "id": "2",
        "name": "Счастливая монета",
        "emoji": "🪙",
        "description": "Увеличивает шанс выигрыша в игре Coinflip на 5%",
        "price": 200,
        "upgrades": {
            1: "Базовая счастливая монета (5% к шансу выигрыша)",
            2: "Улучшенная счастливая монета (8% к шансу выигрыша)",
            3: "Продвинутая счастливая монета (12% к шансу выигрыша)",
            4: "Элитная счастливая монета (15% к шансу выигрыша)",
            5: "Легендарная счастливая монета (20% к шансу выигрыша)"
        }
    },
    "3": {
        "id": "3",
        "name": "Радар опасности",
        "emoji": "📡",
        "description": "20% шанс обнаружить область 2x2 с миной, 1% шанс самоуничтожения при нажатии на мину",
        "price": 350,
        "upgrades": {
            1: "Базовый радар (20% шанс обнаружения, 1% шанс самоуничтожения)",
            2: "Улучшенный радар (25% шанс обнаружения, 0.8% шанс самоуничтожения)",
            3: "Продвинутый радар (30% шанс обнаружения, 0.6% шанс самоуничтожения)",
            4: "Элитный радар (35% шанс обнаружения, 0.4% шанс самоуничтожения)",
            5: "Легендарный радар (40% шанс обнаружения, 0.2% шанс самоуничтожения)"
        }
    },
    "4": {
        "id": "4",
        "name": "Анти-краш щит",
        "emoji": "🔰",
        "description": "10% шанс спастись от взрыва в игре Crash (одноразовое использование)",
        "price": 400,
        "upgrades": {
            1: "Базовый щит (10% шанс спасения от взрыва)",
            2: "Улучшенный щит (15% шанс спасения от взрыва)",
            3: "Продвинутый щит (20% шанс спасения от взрыва)",
            4: "Элитный щит (25% шанс спасения от взрыва)",
            5: "Легендарный щит (30% шанс спасения от взрыва)"
        }
    }
}

# Mapping from item ID to internal key
ITEM_ID_MAP = {
    "1": "defending_aura",
    "2": "lucky_coin",
    "3": "danger_radar",
    "4": "anti_crash_shield"
}

# Reverse mapping
ITEM_KEY_TO_ID = {v: k for k, v in ITEM_ID_MAP.items()}

# Item effects by level
ITEM_EFFECTS = {
    "defending_aura": {  # Chance to save from mine
        1: 0.10,
        2: 0.15,
        3: 0.20,
        4: 0.25,
        5: 0.30
    },
    "lucky_coin": {  # Additional chance to win coinflip
        1: 5,
        2: 8,
        3: 12,
        4: 15,
        5: 20
    },
    "danger_radar": {  # Chance to detect mines, chance to self-destruct
        1: {"detect": 0.20, "explode": 0.01},
        2: {"detect": 0.25, "explode": 0.008},
        3: {"detect": 0.30, "explode": 0.006},
        4: {"detect": 0.35, "explode": 0.004},
        5: {"detect": 0.40, "explode": 0.002}
    },
    "anti_crash_shield": {  # Chance to save from crash
        1: 0.10,
        2: 0.15,
        3: 0.20,
        4: 0.25,
        5: 0.30
    }
}

# Card suits and values for Blackjack
SUITS = ["♠️", "♥️", "♦️", "♣️"]
CARD_VALUES = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 10, "Q": 10, "K": 10, "A": 11
}

# Функции работы с Firebase
async def save_user_data():
    if not firebase_enabled:
        return
        
    try:
        # Сохраняем все данные пользователей
        data_to_save = {
            "user_balances": user_balances,
            "farm_values": farm_values,
            "max_farm_values": max_farm_values,
            "farm_fail_chances": farm_fail_chances,
            "user_inventories": user_inventories,
            "item_experience": item_experience,
            "item_levels": item_levels
        }
        
        # Сохраняем в Firebase
        db.collection("bot_data").document("user_data").set(data_to_save)
        print("Данные пользователей успешно сохранены в Firebase")
    except Exception as e:
        print(f"Ошибка при сохранении данных в Firebase: {e}")

async def load_user_data():
    if not firebase_enabled:
        return
        
    try:
        # Загружаем данные из Firebase
        doc_ref = db.collection("bot_data").document("user_data")
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            
            # Обновляем глобальные переменные
            global user_balances, farm_values, max_farm_values
            global farm_fail_chances, user_inventories, item_experience, item_levels
            
            user_balances = data.get("user_balances", {})
            farm_values = data.get("farm_values", {})
            max_farm_values = data.get("max_farm_values", {})
            farm_fail_chances = data.get("farm_fail_chances", {})
            user_inventories = data.get("user_inventories", {})
            item_experience = data.get("item_experience", {})
            item_levels = data.get("item_levels", {})
            
            # Конвертируем строковые ключи в числовые для user_id
            user_balances = {int(k): v for k, v in user_balances.items()}
            farm_values = {int(k): v for k, v in farm_values.items()}
            max_farm_values = {int(k): v for k, v in max_farm_values.items()}
            farm_fail_chances = {int(k): v for k, v in farm_fail_chances.items()}
            user_inventories = {int(k): v for k, v in user_inventories.items()}
            item_experience = {int(k): v for k, v in item_experience.items()}
            item_levels = {int(k): v for k, v in item_levels.items()}
            
            print("Данные пользователей успешно загружены из Firebase")
        else:
            print("Данные пользователей не найдены в Firebase")
    except Exception as e:
        print(f"Ошибка при загрузке данных из Firebase: {e}")

# Новая команда для администратора - установка баланса
async def set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверка, является ли пользователь администратором
    if user_id != ADMIN_ID:
        return  # Тихо игнорируем, если не админ
    
    # Проверка аргументов
    if len(context.args) != 2:
        await update.message.reply_text(
            "Использование: /set_bal [юзернейм] [сумма]"
        )
        return
    
    target_username = context.args[0]
    
    try:
        new_balance = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "Ошибка! Сумма должна быть числом."
        )
        return
    
    # Ищем пользователя по юзернейму
    target_user_id = None
    for uid, balance in user_balances.items():
        # Здесь мы должны были бы проверить юзернейм, но у нас нет его в данных
        # Поэтому просто присваиваем баланс напрямую если находим ID
        try:
            chat_member = await context.bot.get_chat_member(update.effective_chat.id, uid)
            if chat_member.user.username == target_username:
                target_user_id = uid
                break
        except Exception:
            continue
    
    if target_user_id is None:
        await update.message.reply_text(
            f"Пользователь с юзернеймом @{target_username} не найден."
        )
        return
    
    # Устанавливаем новый баланс
    user_balances[target_user_id] = new_balance
    
    # Сохраняем в Firebase
    await save_user_data()
    
    await update.message.reply_text(
        f"Баланс пользователя @{target_username} установлен на {new_balance} ktn$"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
    
    try:
        text = f"🎮 Добро пожаловать в игровой бот Mines, {user_name}! 🎮\n\n"
        text += f"💰 Ваш баланс: {user_balances[user_id]} ktn$\n\n"
        text += "📋 Доступные команды:\n"
        text += "▫️ /free - Получить 10 ktn$ бесплатно (раз в 25 минут)\n"
        text += "▫️ /mines [кол-во_мин] [ставка] - Играть в Mines\n"
        text += "▫️ /crash [ставка] - Игра в Crash\n"
        text += "▫️ /coinflip [ставка] [сторона] - Игра в монетку (орел/решка)\n"
        text += "▫️ /blackjack [ставка] - Игра в Блэкджек\n"
        text += "▫️ /farm - Фармить ktn$ (с растущей наградой)\n"
        text += "▫️ /upgrade_farm [режим] - Улучшить ферму\n"
        text += "▫️ /upgrade_inv [ID] - Улучшить предмет в инвентаре\n"
        text += "▫️ /opencase [1-3] - Открыть кейс с призами\n"
        text += "▫️ /shop [buy/stock] [ID] - Магазин предметов\n"
        text += "▫️ /inventory - Посмотреть свой инвентарь\n"
        text += "▫️ /balance - Проверить баланс\n"
        text += "▫️ /reset - Сбросить игру, если возникли проблемы\n\n"
        text += "🎯 Удачной игры!"
        
        await update.message.reply_text(text)
    except Exception as e:
        print(f"Error in start command: {e}")

async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_time = datetime.now()
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    # Check cooldown
    if user_id in free_cooldowns:
        last_free_time = free_cooldowns[user_id]
        time_since_last = current_time - last_free_time
        cooldown_time = timedelta(minutes=FREE_COOLDOWN_MINUTES)
        
        if time_since_last < cooldown_time:
            remaining = cooldown_time - time_since_last
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            
            await update.message.reply_text(
                f"⏳ Подождите! Вы сможете получить бесплатные монеты через {minutes} мин. {seconds} сек.\n\n"
                f"Текущий баланс: {user_balances[user_id]} ktn$"
            )
            return
    
    # Give free coins
    user_balances[user_id] += FREE_COINS
    free_cooldowns[user_id] = current_time
    
    # Сохраняем в Firebase
    await save_user_data()
    
    await update.message.reply_text(
        f"💸 Поздравляем! Вы получили {FREE_COINS} ktn$!\n\n"
        f"💰 Ваш баланс: {user_balances[user_id]} ktn$\n\n"
        f"⏰ Следующие бесплатные монеты будут доступны через {FREE_COOLDOWN_MINUTES} минут."
    )

async def farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_time = datetime.now()
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
        
    if user_id not in farm_values:
        farm_values[user_id] = FARM_STARTING_VALUE
        
    if user_id not in max_farm_values:
        max_farm_values[user_id] = MAX_FARM_VALUE
        
    if user_id not in farm_fail_chances:
        farm_fail_chances[user_id] = FARM_FAIL_CHANCE
    
    # Check cooldown
    if user_id in farm_cooldowns:
        last_farm_time = farm_cooldowns[user_id]
        time_since_last = current_time - last_farm_time
        
        # Check for temporary cooldown reduction
        cooldown_minutes = FARM_COOLDOWN_MINUTES
        if "temp_cooldown" in farm_cooldowns and user_id in farm_cooldowns["temp_cooldown"]:
            cooldown_minutes -= farm_cooldowns["temp_cooldown"][user_id]
            # Use this reduction once
            del farm_cooldowns["temp_cooldown"][user_id]
        
        cooldown_time = timedelta(minutes=cooldown_minutes)
        
        if time_since_last < cooldown_time:
            remaining = cooldown_time - time_since_last
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            
            await update.message.reply_text(
                f"🌱 Ваша ферма ещё растёт!\n\n"
                f"⏳ Следующий сбор урожая через {minutes} мин. {seconds} сек.\n"
                f"🌾 Ожидаемый урожай: {farm_values[user_id]} ktn$\n\n"
                f"💰 Текущий баланс: {user_balances[user_id]} ktn$"
            )
            return
    
    # Check for failure
    fail = random.randint(1, 100) <= farm_fail_chances[user_id]
    
    if fail:
        # Farming failed
        farm_cooldowns[user_id] = current_time
        
        # Calculate next value with cap
        next_value = round(farm_values[user_id] * 1.5)
        next_value = min(next_value, max_farm_values[user_id])
        
        await update.message.reply_text(
            f"❌ Неудача! Ваш урожай погиб!\n\n"
            f"🌱 Но не расстраивайтесь, следующий урожай будет ещё больше!\n"
            f"🌾 Следующий ожидаемый урожай: {next_value} ktn$\n\n"
            f"⏰ Приходите через {FARM_COOLDOWN_MINUTES} минут\n"
            f"💰 Ваш баланс: {user_balances[user_id]} ktn$"
        )
        
        # Update farm value
        farm_values[user_id] = next_value
    else:
        # Farming succeeded
        current_value = farm_values[user_id]
        user_balances[user_id] += current_value
        farm_cooldowns[user_id] = current_time
        
        # Calculate next value with cap
        next_value = round(current_value * 1.5)
        next_value = min(next_value, max_farm_values[user_id])
        
        await update.message.reply_text(
            f"✅ Успех! Вы собрали {current_value} ktn$ с вашей фермы!\n\n"
            f"🌱 Ваша ферма растёт!\n"
            f"🌾 Следующий ожидаемый урожай: {next_value} ktn$\n\n"
            f"⏰ Приходите через {FARM_COOLDOWN_MINUTES} минут\n"
            f"💰 Ваш баланс: {user_balances[user_id]} ktn$"
        )
        
        # Update farm value
        farm_values[user_id] = next_value
    
    # Сохраняем в Firebase
    await save_user_data()

async def upgrade_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
        
    if user_id not in farm_values:
        farm_values[user_id] = FARM_STARTING_VALUE
        
    if user_id not in max_farm_values:
        max_farm_values[user_id] = MAX_FARM_VALUE
        
    if user_id not in farm_fail_chances:
        farm_fail_chances[user_id] = FARM_FAIL_CHANCE
    
    # Check arguments
    if not context.args:
        try:
            text = "ℹ️ Улучшение фермы\n\n"
            text += "Использование: /upgrade_farm [режим] [сумма]\n\n"
            text += "Доступные режимы:\n"
            text += "1 - Инвестировать в увеличение прибыли\n"
            text += "2 - Инвестировать в защиту от неудач\n"
            text += "3 - Инвестировать в снижение времени отката\n"
            text += "4 - Увеличить максимальный объем урожая\n\n"
            text += "Текущие параметры фермы:\n"
            text += f"🌾 Доходность: {farm_values[user_id]} ktn$\n"
            text += f"🌾 Максимальный объем: {max_farm_values[user_id]} ktn$\n"
            text += f"🛡️ Шанс неудачи: {farm_fail_chances[user_id]}%\n"
            text += f"⏱️ Время отката: {FARM_COOLDOWN_MINUTES} мин.\n\n"
            text += "Примеры:\n"
            text += "/upgrade_farm 1 100 - Вложить 100 ktn$ в увеличение прибыли\n"
            text += "/upgrade_farm 4 - Увеличить максимальный объем (стоимость будет рассчитана автоматически)"
            
            await update.message.reply_text(text)
        except Exception as e:
            print(f"Error in upgrade_farm info: {e}")
        return
        
    # Режим 4 - увеличение максимального объема фермы
    if len(context.args) == 1 and context.args[0] == "4":
        # Рассчитываем стоимость и новый объем
        new_max_value = round(max_farm_values[user_id] * 1.5)
        cost = max_farm_values[user_id] * 2
        
        # Проверяем, хватает ли денег
        if user_balances[user_id] < cost:
            await update.message.reply_text(
                f"❌ Недостаточно средств для улучшения объема фермы!\n\n"
                f"Чтобы улучшить объем фермы до {new_max_value} ktn$, вам надо {cost} ktn$\n\n"
                f"Ваш баланс: {user_balances[user_id]} ktn$"
            )
            return
            
        # Обновляем максимальный объем
        user_balances[user_id] -= cost
        max_farm_values[user_id] = new_max_value
        
        # Сохраняем в Firebase
        await save_user_data()
        
        await update.message.reply_text(
            f"🌱 Максимальный объем фермы увеличен!\n\n"
            f"💰 Инвестировано: {cost} ktn$\n"
            f"📈 Новый максимальный объем: {new_max_value} ktn$\n\n"
            f"💹 Ваш баланс: {user_balances[user_id]} ktn$"
        )
        return
    
    # Стандартные режимы улучшения
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Ошибка! Неверное количество аргументов.\n\n"
            "Используйте: /upgrade_farm [режим] [сумма]\n"
            "Пример: /upgrade_farm 1 100\n\n"
            "Или для улучшения объема: /upgrade_farm 4"
        )
        return
    
    try:
        mode = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Режим и сумма должны быть числами.\n\n"
            "Используйте: /upgrade_farm [режим] [сумма]\n"
            "Пример: /upgrade_farm 1 100"
        )
        return
    
    # Validate input
    if amount <= 0:
        await update.message.reply_text(
            "❌ Ошибка! Сумма должна быть положительным числом."
        )
        return
    
    if mode not in [1, 2, 3]:
        await update.message.reply_text(
            "❌ Ошибка! Режим должен быть 1, 2 или 3.\n\n"
            "Доступные режимы:\n"
            "1 - Инвестировать в увеличение прибыли\n"
            "2 - Инвестировать в защиту от неудач\n"
            "3 - Инвестировать в снижение времени отката"
        )
        return
    
    if amount > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ Недостаточно средств!\n\n"
            f"Ваш баланс: {user_balances[user_id]} ktn$\n"
            f"Требуется: {amount} ktn$"
        )
        return
    
    # Deduct the investment
    user_balances[user_id] -= amount
    
    # Apply upgrade based on mode with balanced formulas
    if mode == 1:
        # Upgrade farm productivity - with diminishing returns
        # Logarithmic scaling to prevent overpowered farms
        percentage_increase = min(50, 5 * (1 + 0.2 * (amount / 100)))
        
        old_value = farm_values[user_id]
        new_value = round(old_value * (1 + percentage_increase / 100), 1)
        
        # Ensure new value doesn't exceed max
        new_value = min(new_value, max_farm_values[user_id])
        farm_values[user_id] = new_value
        
        await update.message.reply_text(
            f"🌱 Ферма улучшена!\n\n"
            f"💰 Инвестировано: {amount} ktn$\n"
            f"📈 Доходность увеличена: {old_value} ktn$ → {new_value} ktn$\n"
            f"📊 Процент увеличения: +{percentage_increase}%\n\n"
            f"💹 Ваш баланс: {user_balances[user_id]} ktn$"
        )
    elif mode == 2:
        # Upgrade farm immunity - with diminishing returns
        percentage_decrease = min(1, 0.1 * (1 + 0.05 * (amount / 100)))
        
        old_chance = farm_fail_chances[user_id]
        farm_fail_chances[user_id] = max(1, round(old_chance - percentage_decrease, 1))  # Minimum 1%
        
        await update.message.reply_text(
            f"🛡️ Защита фермы улучшена!\n\n"
            f"💰 Инвестировано: {amount} ktn$\n"
            f"📉 Шанс неудачи снижен: {old_chance}% → {farm_fail_chances[user_id]}%\n"
            f"📊 Процент снижения: -{percentage_decrease}%\n\n"
            f"💹 Ваш баланс: {user_balances[user_id]} ktn$"
        )
    else:  # mode == 3
        # New mode: reduce cooldown time (min 1 minute)
        # This effect is temporary for the next harvest only
        
        # Store temporary cooldown reduction for next farm
        if "temp_cooldown" not in farm_cooldowns:
            farm_cooldowns["temp_cooldown"] = {}
        
        reduction_minutes = min(3, 0.2 * (1 + 0.1 * (amount / 100)))
        farm_cooldowns["temp_cooldown"][user_id] = reduction_minutes
        
        await update.message.reply_text(
            f"⏱️ Время отката фермы уменьшено!\n\n"
            f"💰 Инвестировано: {amount} ktn$\n"
            f"⏳ Время отката для следующего сбора: {FARM_COOLDOWN_MINUTES - reduction_minutes} мин.\n"
            f"📊 Уменьшение времени: -{reduction_minutes} мин.\n\n"
            f"💹 Ваш баланс: {user_balances[user_id]} ktn$"
        )
    
    # Сохраняем в Firebase
    await save_user_data()

async def upgrade_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Initialize user data if not exists
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
    
    if user_id not in item_experience:
        item_experience[user_id] = {}
        
    if user_id not in item_levels:
        item_levels[user_id] = {}
    
    # Check arguments
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "ℹ️ Использование: /upgrade_inv [ID предмета]\n\n"
            "Пример: /upgrade_inv 1\n\n"
            "Проверьте свой инвентарь с помощью команды /inventory, чтобы узнать ID предметов и их опыт."
        )
        return
    
    item_id = context.args[0]
    
    # Check if item ID is valid
    if item_id not in SHOP_ITEMS:
        await update.message.reply_text(
            "❌ Ошибка! Указан неверный ID предмета.\n\n"
            "Проверьте свой инвентарь с помощью команды /inventory, чтобы узнать правильные ID."
        )
        return
    
    # Convert item ID to internal key
    item_key = ITEM_ID_MAP[item_id]
    
    # Check if user has this item
    if item_key not in user_inventories[user_id] or user_inventories[user_id][item_key] <= 0:
        await update.message.reply_text(
            f"❌ Ошибка! У вас нет предмета с ID {item_id} в инвентаре.\n\n"
            f"Вы можете приобрести его в магазине: /shop buy {item_id}"
        )
        return
    
    # Initialize item experience and level if not exists
    if item_key not in item_experience[user_id]:
        item_experience[user_id][item_key] = 0
        
    if item_key not in item_levels[user_id]:
        item_levels[user_id][item_key] = 1
    
    current_level = item_levels[user_id][item_key]
    current_exp = item_experience[user_id][item_key]
    
    # Check if item is already at max level
    if current_level >= MAX_ITEM_LEVEL:
        await update.message.reply_text(
            f"⭐ Предмет {SHOP_ITEMS[item_id]['name']} уже достиг максимального уровня ({MAX_ITEM_LEVEL})!\n\n"
            f"Этот предмет нельзя улучшить дальше."
        )
        return
    
    # Check if enough experience
    max_exp_needed = MAX_EXP_BY_LEVEL[current_level]
    
    if current_exp < max_exp_needed:
        await update.message.reply_text(
            f"❌ Недостаточно опыта для улучшения предмета!\n\n"
            f"Предмет: {SHOP_ITEMS[item_id]['emoji']} {SHOP_ITEMS[item_id]['name']} (Уровень {current_level})\n"
            f"Текущий опыт: {current_exp}/{max_exp_needed}\n"
            f"Необходимо ещё: {max_exp_needed - current_exp} опыта\n\n"
            f"Опыт накапливается за победы в играх."
        )
        return
    
    # Upgrade item
    item_levels[user_id][item_key] += 1
    item_experience[user_id][item_key] = 0  # Reset experience
    
    new_level = item_levels[user_id][item_key]
    
    # Get upgrade description
    upgrade_description = SHOP_ITEMS[item_id]['upgrades'][new_level]
    
    # Сохраняем в Firebase
    await save_user_data()
    
    await update.message.reply_text(
        f"🌟 Предмет успешно улучшен!\n\n"
        f"{SHOP_ITEMS[item_id]['emoji']} {SHOP_ITEMS[item_id]['name']}\n"
        f"Уровень: {current_level} → {new_level}\n\n"
        f"Новые характеристики:\n"
        f"{upgrade_description}\n\n"
        f"Опыт сброшен до 0/{MAX_EXP_BY_LEVEL[new_level]}"
    )

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
        
    if user_id not in item_experience:
        item_experience[user_id] = {}
        
    if user_id not in item_levels:
        item_levels[user_id] = {}
    
    # Check if inventory is empty
    if not user_inventories[user_id]:
        await update.message.reply_text(
            f"📦 Инвентарь пользователя {user_name}\n\n"
            f"Ваш инвентарь пуст.\n\n"
            f"Предметы можно приобрести в магазине: /shop stock"
        )
        return
    
    # Create inventory display
    inventory_text = f"📦 Инвентарь пользователя {user_name}\n\n"
    
    # Convert internal item keys to their display names
    for item_key, count in user_inventories[user_id].items():
        if count > 0:
            # Find the item ID from the reverse map
            item_id = ITEM_KEY_TO_ID.get(item_key)
            if item_id and item_id in SHOP_ITEMS:
                item = SHOP_ITEMS[item_id]
                
                # Get item level and experience
                level = item_levels[user_id].get(item_key, 1)
                exp = item_experience[user_id].get(item_key, 0)
                max_exp = MAX_EXP_BY_LEVEL.get(level, 100)
                
                # Get upgrade description
                upgrade_desc = item['upgrades'][level]
                
                inventory_text += f"{item['emoji']} {item['name']} - {count} шт. | Уровень {level}\n"
                inventory_text += f"└ {upgrade_desc}\n"
                inventory_text += f"└ Опыт: {exp}/{max_exp}\n"
                inventory_text += f"└ ID: {item['id']}\n\n"
    
    inventory_text += f"💰 Ваш баланс: {user_balances[user_id]} ktn$\n\n"
    inventory_text += "Предметы можно приобрести в магазине: /shop stock\n"
    inventory_text += "Для улучшения предмета используйте: /upgrade_inv [ID]"
    
    await update.message.reply_text(inventory_text)

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
    
    # Check arguments
    if len(context.args) < 1:
        await update.message.reply_text(
            "ℹ️ Использование: /shop [buy/stock] [ID предмета]\n\n"
            "Пример: /shop buy 1 или /shop stock"
        )
        return
    
    action = context.args[0].lower()
    
    if action == "stock":
        # Show available items
        stock_text = "🛒 Доступные предметы в магазине:\n\n"
        
        for item_id, item in SHOP_ITEMS.items():
            stock_text += f"{item['emoji']} {item['name']} - {item['price']} ktn$\n"
            stock_text += f"└ {item['description']}\n"
            stock_text += f"└ ID: {item['id']}\n\n"
        
        stock_text += f"💰 Ваш баланс: {user_balances[user_id]} ktn$\n\n"
        stock_text += "Для покупки используйте: /shop buy [ID предмета]"
        
        await update.message.reply_text(stock_text)
        return
    
    elif action == "buy":
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Ошибка! Укажите ID предмета для покупки.\n"
                "Пример: /shop buy 1\n\n"
                "Для просмотра доступных предметов используйте: /shop stock"
            )
            return
        
        item_id = context.args[1]
        
        if item_id not in SHOP_ITEMS:
            await update.message.reply_text(
                "❌ Ошибка! Указанный ID предмета не найден.\n\n"
                "Для просмотра доступных предметов используйте: /shop stock"
            )
            return
        
        item = SHOP_ITEMS[item_id]
        
        # Check if user has enough money
        if user_balances[user_id] < item["price"]:
            await update.message.reply_text(
                f"❌ Недостаточно средств!\n\n"
                f"Ваш баланс: {user_balances[user_id]} ktn$\n"
                f"Стоимость предмета: {item['price']} ktn$"
            )
            return
        
        # Process purchase
        user_balances[user_id] -= item["price"]
        
        # Convert item ID to internal key
        internal_key = ITEM_ID_MAP[item_id]
        
        if internal_key not in user_inventories[user_id]:
            user_inventories[user_id][internal_key] = 0
            
        # Initialize experience and level if first purchase
        if internal_key not in item_experience.get(user_id, {}):
            if user_id not in item_experience:
                item_experience[user_id] = {}
            item_experience[user_id][internal_key] = 0
            
        if internal_key not in item_levels.get(user_id, {}):
            if user_id not in item_levels:
                item_levels[user_id] = {}
            item_levels[user_id][internal_key] = 1
        
        user_inventories[user_id][internal_key] += 1
        
        # Сохраняем в Firebase
        await save_user_data()
        
        await update.message.reply_text(
            f"✅ Покупка успешна!\n\n"
            f"{item['emoji']} Вы приобрели: {item['name']}\n"
            f"💰 Стоимость: {item['price']} ktn$\n"
            f"📦 У вас в инвентаре: {user_inventories[user_id][internal_key]} шт.\n\n"
            f"💹 Ваш баланс: {user_balances[user_id]} ktn$"
        )
        return
    
    else:
        await update.message.reply_text(
            "❌ Ошибка! Неверное действие.\n\n"
            "Доступные действия: buy, stock"
        )

# Function to add experience to items after winning games
def add_experience(user_id, game_type):
    if user_id not in item_experience:
        item_experience[user_id] = {}
        
    if user_id not in item_levels:
        item_levels[user_id] = {}
        
    if user_id not in user_inventories:
        return
    
    # Get experience amount based on game type
    exp_amount = EXP_PER_WIN.get(game_type, 5)
    
    # Add experience to all items in inventory
    for item_key in user_inventories[user_id]:
        if user_inventories[user_id][item_key] > 0:
            # Initialize if not exists
            if item_key not in item_experience[user_id]:
                item_experience[user_id][item_key] = 0
                
            if item_key not in item_levels[user_id]:
                item_levels[user_id][item_key] = 1
            
            # Add experience
            item_experience[user_id][item_key] += exp_amount

async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
        
    if user_id not in item_levels:
        item_levels[user_id] = {}
    
    # Check arguments
    if len(context.args) != 2:
        await update.message.reply_text(
            "ℹ️ Использование: /coinflip [ставка] [сторона]\n\n"
            "Доступные стороны:\n"
            "▫️ heads/h/орел/о - Орёл\n"
            "▫️ tails/t/решка/р - Решка\n\n"
            "Пример: /coinflip 50 орел"
        )
        return
    
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Ставка должна быть числом."
        )
        return
    
    side = context.args[1].lower()
    
    # Map different inputs to heads/tails
    heads_options = ["heads", "h", "орел", "орёл", "о"]
    tails_options = ["tails", "t", "решка", "р"]
    
    if side in heads_options:
        player_choice = "heads"
        player_choice_ru = "Орёл"
    elif side in tails_options:
        player_choice = "tails"
        player_choice_ru = "Решка"
    else:
        await update.message.reply_text(
            "❌ Ошибка! Неверная сторона монеты.\n\n"
            "Доступные стороны:\n"
            "▫️ heads/h/орел/о - Орёл\n"
            "▫️ tails/t/решка/р - Решка"
        )
        return
    
    # Validate bet
    if bet < MIN_BET:
        await update.message.reply_text(
            f"❌ Ошибка! Минимальная ставка: {MIN_BET} ktn$."
        )
        return
    
    if bet > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ Недостаточно средств!\n\n"
            f"Ваш баланс: {user_balances[user_id]} ktn$\n"
            f"Требуется: {bet} ktn$"
        )
        return
    
    # Deduct bet from balance
    user_balances[user_id] -= bet
    
    # Send initial message
    initial_message = await update.message.reply_text(
        f"🪙 Бросаем монетку...\n\n"
        f"👤 Игрок: {user_name}\n"
        f"💰 Ставка: {bet} ktn$\n"
        f"🎯 Выбор: {player_choice_ru}\n\n"
        f"⏳ Подбрасываем монету..."
    )
    
    # Animation
    for i in range(3):
        await asyncio.sleep(0.5)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=initial_message.message_id,
            text=f"🪙 Бросаем монетку...\n\n"
                 f"👤 Игрок: {user_name}\n"
                 f"💰 Ставка: {bet} ktn$\n"
                 f"🎯 Выбор: {player_choice_ru}\n\n"
                 f"⏳ {'Орёл' if i % 2 == 0 else 'Решка'}..."
        )
    
    # Check if user has lucky coin and apply bonus
    has_lucky_coin = user_inventories.get(user_id, {}).get("lucky_coin", 0) > 0
    
    # Get level of lucky coin if user has it
    lucky_coin_level = 1
    if has_lucky_coin and "lucky_coin" in item_levels.get(user_id, {}):
        lucky_coin_level = item_levels[user_id]["lucky_coin"]
    
    # Get bonus based on level
    bonus_chance = 0
    if has_lucky_coin:
        bonus_chance = ITEM_EFFECTS["lucky_coin"][lucky_coin_level]
    
    # Determine result (slightly biased if user has lucky coin)
    if has_lucky_coin and player_choice == "heads":
        win_chance = 50 + bonus_chance
    elif has_lucky_coin and player_choice == "tails":
        win_chance = 50 + bonus_chance
    else:
        win_chance = 50
    
    user_won = random.randint(1, 100) <= win_chance
    
    # Determine coin result based on if user won
    if user_won:
        coin_result = player_choice
        coin_result_ru = player_choice_ru
    else:
        coin_result = "tails" if player_choice == "heads" else "heads"
        coin_result_ru = "Решка" if player_choice == "heads" else "Орёл"
    
    # Calculate winnings
    if user_won:
        winnings = bet * 2
        user_balances[user_id] += winnings
        result_text = f"🎉 Вы выиграли!\n💰 Выигрыш: {winnings} ktn$"
        
        # Add experience to items
        add_experience(user_id, "coinflip")
    else:
        winnings = 0
        result_text = "❌ Вы проиграли!\n💰 Ставка потеряна."
    
    # Bonus info if lucky coin was used
    bonus_text = ""
    if has_lucky_coin:
        bonus_text = f"\n🪙 Счастливая монета (Уровень {lucky_coin_level}) дала вам +{bonus_chance}% к шансу выигрыша!"
    
    # Сохраняем в Firebase
    await save_user_data()
    
    # Final message
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=initial_message.message_id,
        text=f"🪙 Результат броска монеты:\n\n"
             f"👤 Игрок: {user_name}\n"
             f"💰 Ставка: {bet} ktn$\n"
             f"🎯 Ваш выбор: {player_choice_ru}\n"
             f"🎲 Выпало: {coin_result_ru}\n\n"
             f"{result_text}{bonus_text}\n\n"
             f"💹 Ваш баланс: {user_balances[user_id]} ktn$"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    await update.message.reply_text(
        f"💰 Баланс пользователя {user_name}\n\n"
        f"{user_balances[user_id]} ktn$"
    )

async def opencase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    current_time = datetime.now()
    
    # Check for anti-spam cooldown
    if user_id in case_cooldowns:
        last_case_time = case_cooldowns[user_id]
        time_since_last = current_time - last_case_time
        cooldown_time = timedelta(seconds=CASE_COOLDOWN_SECONDS)
        
        if time_since_last < cooldown_time:
            remaining_seconds = round((cooldown_time - time_since_last).total_seconds())
            await update.message.reply_text(
                f"⏳ Подождите {remaining_seconds} сек. перед открытием следующего кейса!"
            )
            return
    
    # Make sure user has balance
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    # Check arguments
    if len(context.args) != 1:
        await update.message.reply_text(
            "ℹ️ Использование: /opencase [номер_кейса]\n\n"
            "Доступные кейсы:\n"
            "1 - Бронзовый кейс (35 ktn$)"
        )
        return
    
    case_type = context.args[0]
    
    # Validate case type
    if case_type not in CASE_COSTS:
        await update.message.reply_text(
            "❌ Ошибка! Указан неверный тип кейса.\n\n"
            "Доступные кейсы:\n"
            "1 - Бронзовый кейс (35 ktn$)"
        )
        return
    
    case_cost = CASE_COSTS[case_type]
    
    # Check if user has enough balance
    if user_balances[user_id] < case_cost:
        await update.message.reply_text(
            f"❌ Недостаточно средств!\n\n"
            f"Ваш баланс: {user_balances[user_id]} ktn$\n"
            f"Стоимость кейса: {case_cost} ktn$"
        )
        return
    
    # Deduct the case cost
    user_balances[user_id] -= case_cost
    
    # Update cooldown
    case_cooldowns[user_id] = current_time
    
    # Send initial message
    case_names = {
        "1": "Бронзовый"
    }
    
    initial_message = await update.message.reply_text(
        f"🎁 Открываем {case_names[case_type]} кейс...\n\n"
        f"💰 Стоимость: {case_cost} ktn$\n"
        f"👤 Игрок: {user_name}\n\n"
        f"⏳ Выбираем приз..."
    )
    
    # Animation sequence
    prizes = CASE_PRIZES[case_type]
    animation_steps = 8  # Number of animation steps
    
    for i in range(animation_steps):
        # Make animation slower towards the end
        delay = 0.1 + (i / (animation_steps * 3))
        
        # Random item for animation
        random_prize = random.choice(prizes)
        
        await asyncio.sleep(delay)
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=initial_message.message_id,
                text=f"🎁 Открываем {case_names[case_type]} кейс...\n\n"
                     f"💰 Стоимость: {case_cost} ktn$\n"
                     f"👤 Игрок: {user_name}\n\n"
                     f"⏳ Выпадает: {random_prize['emoji']} ({random_prize['value']} ktn$)"
            )
        except Exception:
            pass
    
    # Determine the final prize based on chances
    rand = random.randint(1, 100)
    cumulative_chance = 0
    final_prize = None
    
    for prize in prizes:
        cumulative_chance += prize["chance"]
        if rand <= cumulative_chance:
            final_prize = prize
            break
    
    # Add the prize to user's balance
    user_balances[user_id] += final_prize["value"]
    
    # Сохраняем в Firebase
    await save_user_data()
    
    # Final message
    profit = final_prize["value"] - case_cost
    profit_str = f"+{profit}" if profit >= 0 else f"{profit}"
    
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=initial_message.message_id,
        text=f"🎁 {case_names[case_type]} кейс открыт!\n\n"
             f"🏆 Вы выиграли: {final_prize['emoji']} {final_prize['value']} ktn$\n"
             f"📊 Профит: {profit_str} ktn$\n\n"
             f"💰 Ваш баланс: {user_balances[user_id]} ktn$"
    )

async def reset_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in active_games:
        # Unpin message if pinned
        game = active_games[user_id]
        if "message_id" in game and "chat_id" in game and game.get("pinned", False):
            try:
                await context.bot.unpin_chat_message(
                    chat_id=game["chat_id"],
                    message_id=game["message_id"]
                )
            except Exception:
                pass
        
        del active_games[user_id]
        await update.message.reply_text(
            "🔄 Ваша игра успешно сброшена!\n"
            "Теперь вы можете начать новую игру."
        )
        return
    
    if user_id in blackjack_games:
        del blackjack_games[user_id]
        await update.message.reply_text(
            "🔄 Ваша игра в Блэкджек успешно сброшена!\n"
            "Теперь вы можете начать новую игру."
        )
        return
        
    if user_id in crash_games:
        del crash_games[user_id]
        await update.message.reply_text(
            "🔄 Ваша игра в Crash успешно сброшена!\n"
            "Теперь вы можете начать новую игру."
        )
        return
    
    await update.message.reply_text(
        "ℹ️ У вас нет активных игр, которые нужно сбросить."
    )

async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if user is admin
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    # Count before cleanup
    count_before = len(active_games)
    count_blackjack_before = len(blackjack_games)
    count_crash_before = len(crash_games)
    
    # Find stale games (older than 1 hour)
    current_time = datetime.now()
    stale_game_users = []
    stale_blackjack_users = []
    stale_crash_users = []
    
    for user_id, game in active_games.items():
        if 'start_time' not in game:
            game['start_time'] = current_time
            continue
            
        time_diff = current_time - game['start_time']
        if time_diff > timedelta(hours=1):
            stale_game_users.append(user_id)
    
    for user_id, game in blackjack_games.items():
        if 'start_time' not in game:
            game['start_time'] = current_time
            continue
            
        time_diff = current_time - game['start_time']
        if time_diff > timedelta(hours=1):
            stale_blackjack_users.append(user_id)
            
    for user_id, game in crash_games.items():
        if 'start_time' not in game:
            game['start_time'] = current_time
            continue
            
        time_diff = current_time - game['start_time']
        if time_diff > timedelta(hours=1):
            stale_crash_users.append(user_id)
    
    # Remove stale games
    for user_id in stale_game_users:
        if user_id in active_games:
            # Try to unpin if pinned
            game = active_games[user_id]
            if "message_id" in game and "chat_id" in game and game.get("pinned", False):
                try:
                    await context.bot.unpin_chat_message(
                        chat_id=game["chat_id"],
                        message_id=game["message_id"]
                    )
                except Exception:
                    pass
            
            del active_games[user_id]
    
    for user_id in stale_blackjack_users:
        if user_id in blackjack_games:
            del blackjack_games[user_id]
            
    for user_id in stale_crash_users:
        if user_id in crash_games:
            del crash_games[user_id]
    
    # Report results
    count_after = len(active_games)
    count_blackjack_after = len(blackjack_games)
    count_crash_after = len(crash_games)
    
    await update.message.reply_text(
        f"🧹 Очистка завершена\n\n"
        f"Игры Mines:\n"
        f"- Было: {count_before}\n"
        f"- Удалено: {count_before - count_after}\n"
        f"- Осталось: {count_after}\n\n"
        f"Игры Blackjack:\n"
        f"- Было: {count_blackjack_before}\n"
        f"- Удалено: {count_blackjack_before - count_blackjack_after}\n"
        f"- Осталось: {count_blackjack_after}\n\n"
        f"Игры Crash:\n"
        f"- Было: {count_crash_before}\n"
        f"- Удалено: {count_crash_before - count_crash_after}\n"
        f"- Осталось: {count_crash_after}"
    )

async def mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
        
    if user_id not in item_levels:
        item_levels[user_id] = {}
    
    # Check if user already has an active game
    if user_id in active_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
    
    if user_id in blackjack_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Блэкджек!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
        
    if user_id in crash_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Crash!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
    
    # Parse arguments
    if len(context.args) != 2:
        await update.message.reply_text(
            "ℹ️ Использование: /mines [количество_мин] [ставка]\n\n"
            "Пример: /mines 5 10"
        )
        return
    
    try:
        num_mines = int(context.args[0])
        bet = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Оба аргумента должны быть числами."
        )
        return
    
    # Validate input
    if num_mines <= 0 or num_mines >= TOTAL_TILES:
        await update.message.reply_text(
            f"❌ Ошибка! Количество мин должно быть от 1 до {TOTAL_TILES-1}."
        )
        return
    
    if bet < MIN_BET:
        await update.message.reply_text(
            f"❌ Ошибка! Минимальная ставка: {MIN_BET} ktn$."
        )
        return
    
    if bet > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ Недостаточно средств!\n\n"
            f"Ваш баланс: {user_balances[user_id]} ktn$\n"
            f"Требуется: {bet} ktn$"
        )
        return
    
    # Deduct bet from balance
    user_balances[user_id] -= bet
    
    # Generate mine positions
    all_positions = list(range(TOTAL_TILES))
    mine_positions = random.sample(all_positions, num_mines)
    
    # Check if user has items
    has_aura = user_inventories.get(user_id, {}).get("defending_aura", 0) > 0
    has_radar = user_inventories.get(user_id, {}).get("danger_radar", 0) > 0
    
    # Get item levels
    aura_level = 1
    radar_level = 1
    
    if has_aura and "defending_aura" in item_levels.get(user_id, {}):
        aura_level = item_levels[user_id]["defending_aura"]
        
    if has_radar and "danger_radar" in item_levels.get(user_id, {}):
        radar_level = item_levels[user_id]["danger_radar"]
    
    # Decide if radar activates
    radar_activated = False
    radar_area = []
    
    if has_radar:
        # Get radar detection chance based on level
        radar_chance = ITEM_EFFECTS["danger_radar"][radar_level]["detect"]
        radar_activated = random.random() < radar_chance
        
        if radar_activated:
            # Choose one random mine
            mine_position = random.choice(mine_positions)
            row = mine_position // COLS
            col = mine_position % COLS
            
            # Create a 2x2 area around the mine
            for r in range(max(0, row-1), min(ROWS, row+2)):
                for c in range(max(0, col-1), min(COLS, col+2)):
                    pos = r * COLS + c
                    if 0 <= pos < TOTAL_TILES:
                        radar_area.append(pos)
    
    # Create game state
    game_state = {
        "bet": bet,
        "num_mines": num_mines,
        "mine_positions": mine_positions,
        "revealed_positions": [],
        "protected_positions": [],  # For defending aura
        "radar_area": radar_area,  # For danger radar
        "game_over": False,
        "win": False,
        "user_id": user_id,
        "user_name": user_name,
        "chat_id": update.effective_chat.id,
        "start_time": datetime.now(),  # Track when the game started
        "has_aura": has_aura,
        "has_radar": has_radar,
        "aura_level": aura_level,
        "radar_level": radar_level,
        "aura_used": False,
        "radar_used": radar_activated,
        "poisonous_mines": []  # Для ядовитых мин
    }
    
    active_games[user_id] = game_state
    
    # Create and send the game board
    await send_game_board(update, context, user_id)

async def send_game_board(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    try:
        if user_id not in active_games:
            return
            
        game = active_games[user_id]
        
        # Проверяем блокировку для предотвращения дублирования
        if user_id in game_locks and game_locks[user_id]:
            return
            
        # Устанавливаем блокировку
        game_locks[user_id] = True
        
        try:
            # Calculate multiplier based on revealed safe tiles
            revealed_count = len(game["revealed_positions"])
            
            # Calculate current multiplier with enhanced formula
            mines_left = game["num_mines"]
            tiles_left = TOTAL_TILES - revealed_count
            
            # Improved multiplier formula that scales better with mines and revealed tiles
            if tiles_left > mines_left:
                # Base multiplier calculation
                base_multiplier = tiles_left / (tiles_left - mines_left)
                
                # Apply bonus for more revealed tiles
                bonus = revealed_count * 0.15
                
                # Apply bonus for more mines (higher risk)
                mines_bonus = (mines_left / TOTAL_TILES) * 2.0
                
                # Special case for almost all tiles revealed
                if revealed_count >= TOTAL_TILES - mines_left - 1:
                    bonus *= 2  # Double bonus for high risk plays
                
                multiplier = round(base_multiplier * (1 + bonus + mines_bonus), 2)
            else:
                multiplier = 1.0
            
            # Create keyboard with tile buttons
            keyboard = []
            for row in range(ROWS):
                keyboard_row = []
                for col in range(COLS):
                    position = row * COLS + col
                    
                    if position in game["protected_positions"]:
                        # This is a position protected by aura
                        button_text = "🛡️"
                    elif position in game["revealed_positions"]:
                        # This is a revealed safe tile
                        button_text = "✅"
                    elif position in game["radar_area"]:
                        # This is a radar detected area
                        button_text = "❓"
                    else:
                        # This is an unrevealed tile
                        button_text = "🔲"
                        
                    callback_data = f"tile_{position}_{user_id}"  # Add user_id to callback data for security
                    keyboard_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
                
                keyboard.append(keyboard_row)
            
            # Add cashout button if at least 3 safe tiles revealed
            if revealed_count >= 3 and not game["game_over"]:
                keyboard.append([
                    InlineKeyboardButton(f"💰 ЗАБРАТЬ ВЫИГРЫШ ({multiplier}x) 💰", callback_data=f"cashout_{user_id}")
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Calculate potential win
            potential_win = round(game["bet"] * multiplier)
            
            # Create status message
            if game["game_over"]:
                if game["win"]:
                    status = (
                        f"🎉 {game['user_name']} выиграл {game['win_amount']} ktn$! 🎉\n\n"
                        f"💰 Множитель: {multiplier}x\n"
                        f"💵 Ставка: {game['bet']} ktn$\n"
                        f"💎 Выигрыш: {game['win_amount']} ktn$"
                    )
                else:
                    status = (
                        f"💥 БУМ! {game['user_name']} подорвался на мине! 💥\n\n"
                        f"❌ Ставка {game['bet']} ktn$ потеряна.\n"
                        f"🎮 Удачи в следующий раз!"
                    )
            else:
                status = (
                    f"🎮 MINES | Игрок: {game['user_name']}\n\n"
                    f"💣 Мин на поле: {game['num_mines']}\n"
                    f"💰 Ставка: {game['bet']} ktn$\n"
                    f"✅ Открыто безопасных клеток: {revealed_count}\n"
                    f"📈 Текущий множитель: {multiplier}x\n"
                    f"💎 Потенциальный выигрыш: {potential_win} ktn$"
                )
                
                # Add aura info if available
                if game["has_aura"] and not game["aura_used"]:
                    aura_chance = ITEM_EFFECTS["defending_aura"][game["aura_level"]] * 100
                    status += f"\n🛡️ Защитная аура (Уровень {game['aura_level']}) активна ({aura_chance}% шанс защиты от мины)"
                elif game["aura_used"]:
                    status += "\n🛡️ Защитная аура использована!"
                    
                # Add radar info if available
                if game["has_radar"]:
                    if game["radar_used"]:
                        status += "\n📡 Радар опасности обнаружил подозрительную область (❓)"
                    else:
                        radar_chance = ITEM_EFFECTS["danger_radar"][game["radar_level"]]["detect"] * 100
                        status += f"\n📡 Радар опасности (Уровень {game['radar_level']}) активен ({radar_chance}% шанс обнаружения мин)"
                    
                status += "\n\nНажимайте на клетки, чтобы открыть их!"
            
            # Update or send new message
            if "message_id" in game and "chat_id" in game:
                try:
                    await context.bot.edit_message_text(
                        chat_id=game["chat_id"],
                        message_id=game["message_id"],
                        text=status,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    # If there's an error updating, send a new message
                    message = await context.bot.send_message(
                        chat_id=game["chat_id"],
                        text=status,
                        reply_markup=reply_markup
                    )
                    game["message_id"] = message.message_id
                    
                    # Try to pin the message
                    try:
                        # Unpin old messages first if any
                        if game.get("pinned", False):
                            try:
                                await context.bot.unpin_chat_message(
                                    chat_id=game["chat_id"],
                                    message_id=game["message_id"]
                                )
                            except Exception:
                                pass
                        
                        await context.bot.pin_chat_message(
                            chat_id=game["chat_id"],
                            message_id=message.message_id,
                            disable_notification=True
                        )
                        game["pinned"] = True
                    except Exception:
                        # If pinning fails, continue anyway
                        game["pinned"] = False
            else:
                # First time sending the board
                message = await update.message.reply_text(
                    text=status,
                    reply_markup=reply_markup
                )
                game["message_id"] = message.message_id
                game["chat_id"] = update.effective_chat.id
                
                # Try to pin the message
                try:
                    await context.bot.pin_chat_message(
                        chat_id=game["chat_id"],
                        message_id=message.message_id,
                        disable_notification=True
                    )
                    game["pinned"] = True
                except Exception:
                    # If pinning fails, continue anyway
                    game["pinned"] = False
        finally:
            # Снимаем блокировку
            game_locks[user_id] = False
    except Exception as e:
        print(f"Error in send_game_board: {e}")
        # Снимаем блокировку в случае ошибки
        if user_id in game_locks:
            game_locks[user_id] = False

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        
        # Extract data from callback
        callback_parts = query.data.split('_')
        caller_id = update.effective_user.id
        
        # Handle blackjack callbacks
        if callback_parts[0] == "bj":
            await handle_blackjack_button(update, context, query, callback_parts)
            return
            
        # Handle crash callbacks
        if callback_parts[0] == "crash":
            await handle_crash_button(update, context, query, callback_parts)
            return
        
        # Extract user_id from callback data for mines game
        game_owner_id = int(callback_parts[-1])
        
        # Security check: Only game owner can press buttons
        if caller_id != game_owner_id:
            await query.answer("Это не ваша игра! Вы не можете нажимать на кнопки в чужой игре.", show_alert=False)
            return
        
        # Check if game exists
        if game_owner_id not in active_games:
            await query.answer("Игра не найдена! Возможно, она была сброшена.", show_alert=True)
            return
        
        game = active_games[game_owner_id]
        
        # Проверяем блокировку
        if game_owner_id in game_locks and game_locks[game_owner_id]:
            await query.answer("Подождите, предыдущее действие ещё обрабатывается...", show_alert=False)
            return
        
        # Устанавливаем блокировку
        game_locks[game_owner_id] = True
        
        try:
            # Check if game is over
            if game["game_over"]:
                await query.answer("Эта игра уже завершена!", show_alert=True)
                return
            
            # Answer the callback query to stop loading indicator
            await query.answer()
            
            # Handle cashout
            if callback_parts[0] == "cashout":
                # Calculate win amount with improved multiplier
                revealed_count = len(game["revealed_positions"])
                mines_left = game["num_mines"]
                tiles_left = TOTAL_TILES - revealed_count
                
                # Improved multiplier formula
                if tiles_left > mines_left:
                    # Base multiplier calculation
                    base_multiplier = tiles_left / (tiles_left - mines_left)
                    
                    # Apply bonus for more revealed tiles
                    bonus = revealed_count * 0.15
                    
                    # Apply bonus for more mines (higher risk)
                    mines_bonus = (mines_left / TOTAL_TILES) * 2.0
                    
                    # Special case for almost all tiles revealed
                    if revealed_count >= TOTAL_TILES - mines_left - 1:
                        bonus *= 2  # Double bonus for high risk plays
                    
                    multiplier = round(base_multiplier * (1 + bonus + mines_bonus), 2)
                else:
                    multiplier = 1.0
                
                win_amount = round(game["bet"] * multiplier)
                
                # Update game state
                game["game_over"] = True
                game["win"] = True
                game["win_amount"] = win_amount
                
                # Update user balance
                user_balances[game_owner_id] += win_amount
                
                # Add experience to items
                add_experience(game_owner_id, "mines")
                
                # Сохраняем в Firebase
                await save_user_data()
                
                # Reveal all mines
                await show_all_mines(update, context, game_owner_id)
                
                # Schedule message deletion after 5 seconds
                asyncio.create_task(delete_game_message_after_delay(context, game, 5))
                
                # Unpin if pinned
                if game.get("pinned", False):
                    try:
                        await context.bot.unpin_chat_message(
                            chat_id=game["chat_id"],
                            message_id=game["message_id"]
                        )
                    except Exception:
                        pass
                
                # Clean up
                del active_games[game_owner_id]
                return
            
            # Handle tile click
            if callback_parts[0] == "tile":
                position = int(callback_parts[1])
                
                # Check if tile already revealed
                if position in game["revealed_positions"] or position in game["protected_positions"]:
                    await query.answer("Эта клетка уже открыта!")
                    return
                
                # Check if tile is a mine
                if position in game["mine_positions"]:
                    # Проверяем, будет ли мина ядовитой (40% шанс)
                    is_poisonous = random.randint(1, 100) <= POISONOUS_MINE_CHANCE
                    
                    # Check if danger radar might explode
                    if game["has_radar"]:
                        # Get explode chance based on level
                        explode_chance = ITEM_EFFECTS["danger_radar"][game["radar_level"]]["explode"]
                        
                        if random.random() < explode_chance:
                            # Radar explodes
                            if "danger_radar" in user_inventories[game_owner_id]:
                                user_inventories[game_owner_id]["danger_radar"] -= 1
                            
                            await query.answer("📡 Ваш радар опасности самоуничтожился!", show_alert=True)
                            game["has_radar"] = False
                    
                    # Check if user has active aura
                    if game["has_aura"] and not game["aura_used"]:
                        # Get aura protection chance based on level
                        aura_chance = ITEM_EFFECTS["defending_aura"][game["aura_level"]]
                        
                        if random.random() < aura_chance:  # Chance to activate
                            # Aura activation - save the player
                            game["aura_used"] = True
                            game["protected_positions"].append(position)
                            
                            # Use up the aura
                            if "defending_aura" in user_inventories[game_owner_id]:
                                user_inventories[game_owner_id]["defending_aura"] -= 1
                            
                            # Reshuffle the mines
                            remaining_positions = [p for p in range(TOTAL_TILES) if p not in game["revealed_positions"] and p not in game["protected_positions"]]
                            game["mine_positions"] = random.sample(remaining_positions, min(game["num_mines"], len(remaining_positions)))
                            
                            # Update the game board
                            await query.answer("🛡️ Защитная аура сработала! Вы спаслись от мины!", show_alert=True)
                            await send_game_board(update, context, game_owner_id)
                            return
                    
                    # Если мина ядовитая, снимаем с баланса
                    if is_poisonous:
                        # Добавляем в список ядовитых мин
                        game["poisonous_mines"].append(position)
                        
                        # Снимаем с баланса пользователя (баланс / 1.5)
                        if user_balances[game_owner_id] > 0:
                            penalty = int(user_balances[game_owner_id] / 1.5)
                            # Убеждаемся, что баланс не станет отрицательным
                            if penalty > user_balances[game_owner_id]:
                                penalty = user_balances[game_owner_id]
                            user_balances[game_owner_id] -= penalty
                            
                            # Сохраняем в Firebase
                            await save_user_data()
                            
                            # Сообщаем пользователю о потере средств
                            await query.answer(f"☠️ Вы попали на ЯДОВИТУЮ мину! Потеряно {penalty} ktn$", show_alert=True)
                    
                    # Game over - user hit a mine
                    game["game_over"] = True
                    
                    # Show all mines
                    await show_all_mines(update, context, game_owner_id)
                    
                    # Schedule message deletion after 5 seconds
                    asyncio.create_task(delete_game_message_after_delay(context, game, 5))
                    
                    # Unpin if pinned
                    if game.get("pinned", False):
                        try:
                            await context.bot.unpin_chat_message(
                                chat_id=game["chat_id"],
                                message_id=game["message_id"]
                            )
                        except Exception:
                            pass
                    
                    # Clean up
                    del active_games[game_owner_id]
                else:
                    # Safe tile - reveal it
                    game["revealed_positions"].append(position)
                    
                    # Update game board
                    await send_game_board(update, context, game_owner_id)
        finally:
            # Снимаем блокировку
            game_locks[game_owner_id] = False
    except Exception as e:
        print(f"Error in handle_button: {e}")
        # Снимаем блокировку в случае ошибки
        if 'game_owner_id' in locals() and game_owner_id in game_locks:
            game_locks[game_owner_id] = False

async def delete_game_message_after_delay(context, game, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        await context.bot.delete_message(
            chat_id=game["chat_id"],
            message_id=game["message_id"]
        )
    except Exception:
        # If deletion fails, it's not critical
        pass

async def show_all_mines(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    game = active_games[user_id]
    
    # Create keyboard with all mines revealed
    keyboard = []
    for row in range(ROWS):
        keyboard_row = []
        for col in range(COLS):
            position = row * COLS + col
            
            if position in game["protected_positions"]:
                # This is a position protected by aura
                button_text = "🛡️"
            elif position in game["poisonous_mines"]:
                # Это ядовитая мина
                button_text = "☠️"
            elif position in game["mine_positions"]:
                # This is a mine
                button_text = "❌"
            elif position in game["revealed_positions"]:
                # This is a revealed safe tile
                button_text = "✅"
            else:
                # This is an unrevealed safe tile
                button_text = "🔲"
                
            callback_data = f"tile_{position}_{user_id}"
            keyboard_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        keyboard.append(keyboard_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create status message
    if game["win"]:
        revealed_count = len(game["revealed_positions"])
        mines_left = game["num_mines"]
        tiles_left = TOTAL_TILES - revealed_count
        
        # Calculate final multiplier with same formula as in send_game_board
        if tiles_left > mines_left:
            # Base multiplier calculation
            base_multiplier = tiles_left / (tiles_left - mines_left)
            
            # Apply bonus for more revealed tiles
            bonus = revealed_count * 0.15
            
            # Apply bonus for more mines (higher risk)
            mines_bonus = (mines_left / TOTAL_TILES) * 2.0
            
            # Special case for almost all tiles revealed
            if revealed_count >= TOTAL_TILES - mines_left - 1:
                bonus *= 2  # Double bonus for high risk plays
            
            multiplier = round(base_multiplier * (1 + bonus + mines_bonus), 2)
        else:
            multiplier = 1.0
            
        status = (
            f"🎉 {game['user_name']} выиграл {game['win_amount']} ktn$! 🎉\n\n"
            f"💰 Множитель: {multiplier}x\n"
            f"💵 Ставка: {game['bet']} ktn$\n"
            f"💎 Выигрыш: {game['win_amount']} ktn$\n\n"
            f"⏱️ Сообщение будет удалено через 5 секунд"
        )
    else:
        # Добавляем информацию о ядовитых минах
        poisonous_info = ""
        if game["poisonous_mines"]:
            poisonous_info = f"\n☠️ Вы попали на ядовитую мину! Потеряно часть баланса."
            
        status = (
            f"💥 БУМ! {game['user_name']} подорвался на мине! 💥\n\n"
            f"❌ Ставка {game['bet']} ktn$ потеряна.{poisonous_info}\n"
            f"🎮 Удачи в следующий раз!\n\n"
            f"⏱️ Сообщение будет удалено через 5 секунд"
        )
    
    # Update message
    try:
        await context.bot.edit_message_text(
            chat_id=game["chat_id"],
            message_id=game["message_id"],
            text=status,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error in show_all_mines: {e}")

# Crash game functions
async def crash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
        
    if user_id not in item_levels:
        item_levels[user_id] = {}
    
    # Check if user already has an active game
    if user_id in active_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Mines!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
    
    if user_id in blackjack_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Блэкджек!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
        
    if user_id in crash_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Crash!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
    
    # Parse arguments
    if len(context.args) != 1:
        await update.message.reply_text(
            "ℹ️ Использование: /crash [ставка]\n\n"
            "Пример: /crash 50\n\n"
            "Правила игры:\n"
            "• Ракета взлетает и множитель постоянно растет\n"
            "• Чем дольше ждете, тем выше множитель\n"
            "• Но в любой момент ракета может взорваться и вы потеряете ставку\n"
            "• Нажмите кнопку 'Забрать выигрыш', чтобы получить текущий множитель"
        )
        return
    
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Ставка должна быть числом."
        )
        return
    
    # Validate bet
    if bet < MIN_BET:
        await update.message.reply_text(
            f"❌ Ошибка! Минимальная ставка: {MIN_BET} ktn$."
        )
        return
    
    if bet > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ Недостаточно средств!\n\n"
            f"Ваш баланс: {user_balances[user_id]} ktn$\n"
            f"Требуется: {bet} ktn$"
        )
        return
    
    # Deduct bet from balance
    user_balances[user_id] -= bet
    
    # Сохраняем в Firebase
    await save_user_data()
    
    # Check if user has anti-crash shield
    has_shield = user_inventories.get(user_id, {}).get("anti_crash_shield", 0) > 0
    
    # Get shield level if user has it
    shield_level = 1
    if has_shield and "anti_crash_shield" in item_levels.get(user_id, {}):
        shield_level = item_levels[user_id]["anti_crash_shield"]
    
    # Determine crash point (where the rocket will explode)
    # Higher values are less likely
    crash_point = 1.0
    r = random.random()
    
    # This formula creates an exponential distribution
    # Most crashes happen at low multipliers, some at high
    if r < 0.4:  # 40% chance to crash below 2x
        crash_point = 1.0 + r
    elif r < 0.8:  # 40% chance to crash between 2x and 5x
        crash_point = 2.0 + (r - 0.4) * 7.5
    else:  # 20% chance to crash above 5x
        crash_point = 5.0 + (r - 0.8) * 25
    
    crash_point = round(crash_point, 2)
    
    # Create game state
    game_state = {
        "bet": bet,
        "current_multiplier": 1.0,
        "crash_point": crash_point,
        "game_over": False,
        "win": False,
        "user_id": user_id,
        "user_name": user_name,
        "chat_id": update.effective_chat.id,
        "start_time": datetime.now(),
        "has_shield": has_shield,
        "shield_level": shield_level,
        "shield_used": False
    }
    
    crash_games[user_id] = game_state
    
    # Create and send initial game board
    initial_message = await update.message.reply_text(
        f"🚀 *CRASH* | Игрок: {user_name}\n\n"
        f"💰 Ставка: {bet} ktn$\n"
        f"📈 Текущий множитель: 1.00x\n"
        f"💎 Потенциальный выигрыш: {bet} ktn$\n\n"
        f"⏳ Ракета взлетает...\n"
        f"🔥 Нажмите кнопку, чтобы забрать выигрыш до взрыва!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💰 ЗАБРАТЬ ВЫИГРЫШ (1.00x) 💰", callback_data=f"crash_cashout_{user_id}")
        ]]),
        parse_mode="Markdown"
    )
    
    # Store message info
    game_state["message_id"] = initial_message.message_id
    
    # Start the game loop in background
    asyncio.create_task(crash_game_loop(context, user_id))

async def crash_game_loop(context, user_id):
    try:
        # Safety check
        if user_id not in crash_games:
            return
            
        game = crash_games[user_id]
        
        # Loop until game is over
        while not game["game_over"] and user_id in crash_games:
            # Increase multiplier
            game["current_multiplier"] += 0.05
            game["current_multiplier"] = round(game["current_multiplier"], 2)
            
            # Calculate potential win
            potential_win = round(game["bet"] * game["current_multiplier"])
            
            # Update message with new multiplier
            status = (
                f"🚀 *CRASH* | Игрок: {game['user_name']}\n\n"
                f"💰 Ставка: {game['bet']} ktn$\n"
                f"📈 Текущий множитель: {game['current_multiplier']}x\n"
                f"💎 Потенциальный выигрыш: {potential_win} ktn$\n\n"
            )
            
            # Add shield info if available
            if game["has_shield"] and not game["shield_used"]:
                shield_chance = ITEM_EFFECTS["anti_crash_shield"][game["shield_level"]] * 100
                status += f"🔰 Анти-краш щит (Уровень {game['shield_level']}) активен ({shield_chance}% шанс спасения)\n"
            elif game["shield_used"]:
                status += f"🔰 Анти-краш щит уже использован!\n"
            
            # Rocket animation based on multiplier
            rocket_stages = [
                "🔥 Ракета взлетает...",
                "🔥🔥 Ракета набирает высоту!",
                "🔥🔥🔥 Ракета летит всё выше!",
                "🔥🔥🔥🔥 Ракета на опасной высоте!",
                "🔥🔥🔥🔥🔥 Ракета вот-вот взорвется!!!"
            ]
            
            if game["current_multiplier"] < 2:
                status += f"{rocket_stages[0]}\n"
            elif game["current_multiplier"] < 3:
                status += f"{rocket_stages[1]}\n"
            elif game["current_multiplier"] < 5:
                status += f"{rocket_stages[2]}\n"
            elif game["current_multiplier"] < 10:
                status += f"{rocket_stages[3]}\n"
            else:
                status += f"{rocket_stages[4]}\n"
                
            status += f"🔥 Нажмите кнопку, чтобы забрать выигрыш до взрыва!"
            
            # Update message
            try:
                await context.bot.edit_message_text(
                    chat_id=game["chat_id"],
                    message_id=game["message_id"],
                    text=status,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(f"💰 ЗАБРАТЬ ВЫИГРЫШ ({game['current_multiplier']}x) 💰", 
                                           callback_data=f"crash_cashout_{user_id}")
                    ]]),
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Error updating crash message: {e}")
            
            # Check if crash point reached
            if game["current_multiplier"] >= game["crash_point"]:
                # Check if shield can save
                shield_activated = False
                if game["has_shield"] and not game["shield_used"]:
                    # Get shield save chance based on level
                    shield_chance = ITEM_EFFECTS["anti_crash_shield"][game["shield_level"]]
                    
                    if random.random() < shield_chance:
                        # Shield saves from crash
                        shield_activated = True
                        game["shield_used"] = True
                        
                        # Use up the shield
                        if "anti_crash_shield" in user_inventories[user_id]:
                            user_inventories[user_id]["anti_crash_shield"] -= 1
                        
                        # Show shield activation message
                        shield_message = (
                            f"🚀 *CRASH* | Игрок: {game['user_name']}\n\n"
                            f"🔰 *Анти-краш щит активировался!* Вы спаслись от взрыва!\n\n"
                            f"💰 Ставка: {game['bet']} ktn$\n"
                            f"📈 Текущий множитель: {game['current_multiplier']}x\n"
                            f"💎 Потенциальный выигрыш: {potential_win} ktn$\n\n"
                            f"⚠️ Щит можно использовать только один раз за игру!\n"
                            f"🔥 Нажмите кнопку, чтобы забрать выигрыш до взрыва!"
                        )
                        
                        try:
                            await context.bot.edit_message_text(
                                chat_id=game["chat_id"],
                                message_id=game["message_id"],
                                text=shield_message,
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton(f"💰 ЗАБРАТЬ ВЫИГРЫШ ({game['current_multiplier']}x) 💰", 
                                                       callback_data=f"crash_cashout_{user_id}")
                                ]]),
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                        
                        # Generate new crash point for continuation
                        r = random.random()
                        new_crash_point = game["current_multiplier"]
                        
                        if r < 0.5:  # 50% chance to crash soon after shield activation
                            new_crash_point += 0.5 + r
                        else:  # 50% chance to go much higher
                            new_crash_point += 1.0 + r * 5
                            
                        game["crash_point"] = round(new_crash_point, 2)
                        
                        # Wait a moment to show shield activation
                        await asyncio.sleep(1.5)
                        continue
                
                if not shield_activated:
                    # Game over - crash
                    game["game_over"] = True
                    
                    # Show crash message
                    crash_message = (
                        f"🚀 *CRASH* | Игрок: {game['user_name']}\n\n"
                        f"💥 *БУМ! Ракета взорвалась при {game['current_multiplier']}x!*\n\n"
                        f"❌ Ставка {game['bet']} ktn$ потеряна.\n"
                        f"🎮 Удачи в следующий раз!\n\n"
                        f"⏱️ Сообщение будет удалено через 5 секунд"
                    )
                    
                    try:
                        await context.bot.edit_message_text(
                            chat_id=game["chat_id"],
                            message_id=game["message_id"],
                            text=crash_message,
                            reply_markup=None,
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
                    
                    # Schedule message deletion
                    asyncio.create_task(delete_crash_message(context, game, 5))
                    
                    # Clean up
                    if user_id in crash_games:
                        del crash_games[user_id]
                    
                    break
            
            # Wait a bit before next update
            # Higher multipliers update faster for more excitement
            if game["current_multiplier"] < 2:
                await asyncio.sleep(0.8)
            elif game["current_multiplier"] < 5:
                await asyncio.sleep(0.5)
            elif game["current_multiplier"] < 10:
                await asyncio.sleep(0.3)
            else:
                await asyncio.sleep(0.2)
    
    except Exception as e:
        print(f"Error in crash game loop: {e}")
        # Clean up on error
        if user_id in crash_games:
            del crash_games[user_id]

async def delete_crash_message(context, game, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        await context.bot.delete_message(
            chat_id=game["chat_id"],
            message_id=game["message_id"]
        )
    except Exception:
        # If deletion fails, it's not critical
        pass

async def handle_crash_button(update: Update, context, query, callback_parts):
    try:
        action = callback_parts[1]
        user_id = int(callback_parts[2])
        caller_id = update.effective_user.id
        
        # Security check: Only game owner can press buttons
        if caller_id != user_id:
            await query.answer("Это не ваша игра! Вы не можете нажимать на кнопки в чужой игре.", show_alert=False)
            return
        
        # Check if game exists
        if user_id not in crash_games:
            await query.answer("Игра не найдена! Возможно, она была сброшена.", show_alert=True)
            return
        
        game = crash_games[user_id]
        
        # Check if game is over
        if game["game_over"]:
            await query.answer("Эта игра уже завершена!", show_alert=True)
            return
        
        # Answer the callback query to stop loading indicator
        await query.answer()
        
        # Handle cashout
        if action == "cashout":
            # Calculate win amount
            win_amount = round(game["bet"] * game["current_multiplier"])
            
            # Update game state
            game["game_over"] = True
            game["win"] = True
            game["win_amount"] = win_amount
            
            # Update user balance
            user_balances[user_id] += win_amount
            
            # Add experience to items
            add_experience(user_id, "crash")
            
            # Сохраняем в Firebase
            await save_user_data()
            
            # Show win message
            win_message = (
                f"🚀 *CRASH* | Игрок: {game['user_name']}\n\n"
                f"✅ *Вы успешно забрали выигрыш при {game['current_multiplier']}x!*\n\n"
                f"💰 Ставка: {game['bet']} ktn$\n"
                f"💎 Выигрыш: {win_amount} ktn$\n\n"
                f"⏱️ Сообщение будет удалено через 5 секунд"
            )
            
            try:
                await context.bot.edit_message_text(
                    chat_id=game["chat_id"],
                    message_id=game["message_id"],
                    text=win_message,
                    reply_markup=None,
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            
            # Schedule message deletion
            asyncio.create_task(delete_crash_message(context, game, 5))
            
            # Clean up
            del crash_games[user_id]
    
    except Exception as e:
        print(f"Error in handle_crash_button: {e}")

# Blackjack game functions
def create_deck():
    """Create and shuffle a new deck of cards"""
    deck = []
    for suit in SUITS:
        for value in CARD_VALUES:
            deck.append({"value": value, "suit": suit})
    random.shuffle(deck)
    return deck

def deal_card(deck):
    """Deal a card from the deck"""
    return deck.pop()

def calculate_hand_value(hand):
    """Calculate the value of a hand, accounting for aces"""
    value = 0
    aces = 0
    
    for card in hand:
        card_value = card["value"]
        if card_value == "A":
            aces += 1
            value += 11
        else:
            value += CARD_VALUES[card_value]
    
    # Adjust for aces if needed
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    
    return value

def format_card(card):
    """Format a card for display"""
    return f"{card['value']}{card['suit']}"

def format_hand(hand):
    """Format a hand for display"""
    return " ".join([format_card(card) for card in hand])

def is_blackjack(hand):
    """Check if hand is a natural blackjack (21 with 2 cards)"""
    return len(hand) == 2 and calculate_hand_value(hand) == 21

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    # Check if user already has an active game
    if user_id in active_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Mines!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
    
    if user_id in blackjack_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Блэкджек!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
        
    if user_id in crash_games:
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра в Crash!\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить."
        )
        return
    
    # Check arguments
    if len(context.args) != 1:
        await update.message.reply_text(
            "ℹ️ Использование: /blackjack [ставка]\n\n"
            "Пример: /blackjack 50\n\n"
            "Правила игры:\n"
            "• Цель: набрать 21 очко или приблизиться к этому числу, не превысив его\n"
            "• Карты от 2 до 10 имеют номинальную ценность\n"
            "• Валеты, Дамы и Короли стоят по 10 очков\n"
            "• Тузы могут стоить 1 или 11 очков\n"
            "• Если у вас сразу 21 (Туз + 10/картинка) - у вас Блэкджек, вы выигрываете с коэффициентом 2.5\n"
            "• Дилер должен брать карты, пока не наберёт 17 или больше"
        )
        return
    
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Ставка должна быть числом."
        )
        return
    
    # Validate bet
    if bet < MIN_BET:
        await update.message.reply_text(
            f"❌ Ошибка! Минимальная ставка: {MIN_BET} ktn$."
        )
        return
    
    if bet > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ Недостаточно средств!\n\n"
            f"Ваш баланс: {user_balances[user_id]} ktn$\n"
            f"Требуется: {bet} ktn$"
        )
        return
    
    # Deduct bet from balance
    user_balances[user_id] -= bet
    
    # Сохраняем в Firebase
    await save_user_data()
    
    # Create new deck and deal initial cards
    deck = create_deck()
    player_hand = [deal_card(deck), deal_card(deck)]
    dealer_hand = [deal_card(deck), deal_card(deck)]
    
    # Create game state
    game_state = {
        "bet": bet,
        "deck": deck,
        "player_hand": player_hand,
        "dealer_hand": dealer_hand,
        "player_value": calculate_hand_value(player_hand),
        "dealer_value": calculate_hand_value(dealer_hand),
        "game_over": False,
        "result": None,
        "user_id": user_id,
        "user_name": user_name,
        "chat_id": update.effective_chat.id,
        "start_time": datetime.now()
    }
    
    blackjack_games[user_id] = game_state
    
    # Check for immediate blackjack
    player_blackjack = is_blackjack(player_hand)
    dealer_blackjack = is_blackjack(dealer_hand)
    
    if player_blackjack or dealer_blackjack:
        game_state["game_over"] = True
        
        if player_blackjack and dealer_blackjack:
            # Both have blackjack - push
            game_state["result"] = "push"
            user_balances[user_id] += bet  # Return bet
        elif player_blackjack:
            # Player has blackjack - win 3:2
            game_state["result"] = "blackjack"
            winnings = int(bet * 2.5)
            user_balances[user_id] += winnings
            # Add experience to items
            add_experience(user_id, "blackjack")
        else:  # dealer_blackjack
            # Dealer has blackjack - player loses
            game_state["result"] = "dealer_blackjack"
            
        # Сохраняем в Firebase
        await save_user_data()
    
    # Create and send the game board
    await send_blackjack_board(update, context, user_id)

async def send_blackjack_board(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    try:
        if user_id not in blackjack_games:
            return
            
        game = blackjack_games[user_id]
        
        # Determine what to show for dealer's hand
        if game["game_over"]:
            # Show all cards if game is over
            dealer_hand_display = format_hand(game["dealer_hand"])
            dealer_value_display = game["dealer_value"]
        else:
            # Show only first card if game is still in progress
            dealer_hand_display = f"{format_card(game['dealer_hand'][0])} 🂠"
            dealer_value_display = "?"
        
        # Create keyboard with game buttons
        keyboard = []
        
        if not game["game_over"]:
            # Add hit and stand buttons if game is still in progress
            keyboard.append([
                InlineKeyboardButton("🎯 Взять карту", callback_data=f"bj_hit_{user_id}"),
                InlineKeyboardButton("✋ Остановиться", callback_data=f"bj_stand_{user_id}")
            ])
        else:
            # Add play again button if game is over
            keyboard.append([
                InlineKeyboardButton("🔄 Играть снова", callback_data=f"bj_again_{user_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Create status message
        status = f"🎮 BLACKJACK | Игрок: {game['user_name']}\n\n"
        
        # Player's hand
        status += f"👤 Ваши карты: {format_hand(game['player_hand'])}\n"
        status += f"📊 Сумма: {game['player_value']}\n\n"
        
        # Dealer's hand
        status += f"🎰 Карты дилера: {dealer_hand_display}\n"
        status += f"📊 Сумма: {dealer_value_display}\n\n"
        
        # Bet information
        status += f"💰 Ставка: {game['bet']} ktn$\n"
        
        # Result information if game is over
        if game["game_over"]:
            if game["result"] == "blackjack":
                winnings = int(game["bet"] * 2.5)
                status += f"🎉 БЛЭКДЖЕК! Вы выиграли {winnings} ktn$\n"
            elif game["result"] == "win":
                winnings = game["bet"] * 2
                status += f"🎉 Вы выиграли! Получено {winnings} ktn$\n"
            elif game["result"] == "push":
                status += f"🤝 Ничья! Ставка возвращена.\n"
            elif game["result"] == "bust":
                status += f"💥 Перебор! Вы проиграли {game['bet']} ktn$\n"
            elif game["result"] == "dealer_blackjack":
                status += f"💀 У дилера блэкджек! Вы проиграли {game['bet']} ktn$\n"
            elif game["result"] == "dealer_bust":
                winnings = game["bet"] * 2
                status += f"🎉 У дилера перебор! Вы выиграли {winnings} ktn$\n"
            elif game["result"] == "dealer_win":
                status += f"💀 Дилер выиграл! Вы проиграли {game['bet']} ktn$\n"
            
            status += f"\n💰 Ваш баланс: {user_balances[user_id]} ktn$"
        
        # Update or send new message
        if "message_id" in game and "chat_id" in game:
            try:
                await context.bot.edit_message_text(
                    chat_id=game["chat_id"],
                    message_id=game["message_id"],
                    text=status,
                    reply_markup=reply_markup
                )
            except Exception as e:
                # If there's an error updating, send a new message
                message = await context.bot.send_message(
                    chat_id=game["chat_id"],
                    text=status,
                    reply_markup=reply_markup
                )
                game["message_id"] = message.message_id
        else:
            # First time sending the board
            message = await update.message.reply_text(
                text=status,
                reply_markup=reply_markup
            )
            game["message_id"] = message.message_id
            game["chat_id"] = update.effective_chat.id
    
    except Exception as e:
        print(f"Error in send_blackjack_board: {e}")

async def handle_blackjack_button(update: Update, context, query, callback_parts):
    try:
        action = callback_parts[1]
        user_id = int(callback_parts[2])
        caller_id = update.effective_user.id
        
        # Security check: Only game owner can press buttons
        if caller_id != user_id:
            await query.answer("Это не ваша игра! Вы не можете нажимать на кнопки в чужой игре.", show_alert=False)
            return
        
        # Check if game exists
        if user_id not in blackjack_games:
            await query.answer("Игра не найдена! Возможно, она была сброшена.", show_alert=True)
            return
        
        game = blackjack_games[user_id]
        
        # Check if game is over (except for "again" action)
        if game["game_over"] and action != "again":
            await query.answer("Эта игра уже завершена!", show_alert=True)
            return
        
        # Answer the callback query to stop loading indicator
        await query.answer()
        
        # Handle hit action
        if action == "hit":
            # Deal a new card to player
            new_card = deal_card(game["deck"])
            game["player_hand"].append(new_card)
            game["player_value"] = calculate_hand_value(game["player_hand"])
            
            # Check if player busts
            if game["player_value"] > 21:
                game["game_over"] = True
                game["result"] = "bust"
                
                # Сохраняем в Firebase
                await save_user_data()
            
            # Update game board
            await send_blackjack_board(update, context, user_id)
        
        # Handle stand action
        elif action == "stand":
            # Dealer plays
            while game["dealer_value"] < 17:
                new_card = deal_card(game["deck"])
                game["dealer_hand"].append(new_card)
                game["dealer_value"] = calculate_hand_value(game["dealer_hand"])
            
            # Determine result
            game["game_over"] = True
            
            if game["dealer_value"] > 21:
                game["result"] = "dealer_bust"
                winnings = game["bet"] * 2
                user_balances[user_id] += winnings
                # Add experience to items
                add_experience(user_id, "blackjack")
            elif game["dealer_value"] > game["player_value"]:
                game["result"] = "dealer_win"
            elif game["dealer_value"] < game["player_value"]:
                game["result"] = "win"
                winnings = game["bet"] * 2
                user_balances[user_id] += winnings
                # Add experience to items
                add_experience(user_id, "blackjack")
            else:
                game["result"] = "push"
                user_balances[user_id] += game["bet"]  # Return bet
                
            # Сохраняем в Firebase
            await save_user_data()
            
            # Update game board
            await send_blackjack_board(update, context, user_id)
        
        # Handle play again action
        elif action == "again":
            # Start a new game with the same bet
            bet = game["bet"]
            
            # Check if user has enough balance
            if bet > user_balances[user_id]:
                await query.answer(f"Недостаточно средств! Нужно {bet} ktn$", show_alert=True)
                return
            
            # Deduct bet from balance
            user_balances[user_id] -= bet
            
            # Сохраняем в Firebase
            await save_user_data()
            
            # Create new deck and deal initial cards
            deck = create_deck()
            player_hand = [deal_card(deck), deal_card(deck)]
            dealer_hand = [deal_card(deck), deal_card(deck)]
            
            # Create new game state
            new_game = {
                "bet": bet,
                "deck": deck,
                "player_hand": player_hand,
                "dealer_hand": dealer_hand,
                "player_value": calculate_hand_value(player_hand),
                "dealer_value": calculate_hand_value(dealer_hand),
                "game_over": False,
                "result": None,
                "user_id": user_id,
                "user_name": game["user_name"],
                "chat_id": game["chat_id"],
                "message_id": game["message_id"],
                "start_time": datetime.now()
            }
            
            blackjack_games[user_id] = new_game
            
            # Check for immediate blackjack
            player_blackjack = is_blackjack(player_hand)
            dealer_blackjack = is_blackjack(dealer_hand)
            
            if player_blackjack or dealer_blackjack:
                new_game["game_over"] = True
                
                if player_blackjack and dealer_blackjack:
                    # Both have blackjack - push
                    new_game["result"] = "push"
                    user_balances[user_id] += bet  # Return bet
                elif player_blackjack:
                    # Player has blackjack - win 3:2
                    new_game["result"] = "blackjack"
                    winnings = int(bet * 2.5)
                    user_balances[user_id] += winnings
                    # Add experience to items
                    add_experience(user_id, "blackjack")
                else:  # dealer_blackjack
                    # Dealer has blackjack - player loses
                    new_game["result"] = "dealer_blackjack"
                    
                # Сохраняем в Firebase
                await save_user_data()
            
            # Update game board
            await send_blackjack_board(update, context, user_id)
    
    except Exception as e:
        print(f"Error in handle_blackjack_button: {e}")

async def initialize_bot():
    if firebase_enabled:
        print("Загрузка данных из Firebase...")
        await load_user_data()

def main():
    try:
        # Create the Application
        app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("free", free))
        app.add_handler(CommandHandler("farm", farm))
        app.add_handler(CommandHandler("upgrade_farm", upgrade_farm))
        app.add_handler(CommandHandler("upgrade_inv", upgrade_inventory))
        app.add_handler(CommandHandler("balance", balance))
        app.add_handler(CommandHandler("opencase", opencase))
        app.add_handler(CommandHandler("shop", shop))
        app.add_handler(CommandHandler("inventory", inventory))
        app.add_handler(CommandHandler("coinflip", coinflip))
        app.add_handler(CommandHandler("blackjack", blackjack))
        app.add_handler(CommandHandler("crash", crash))
        app.add_handler(CommandHandler("mines", mines))
        app.add_handler(CommandHandler("reset", reset_game))
        app.add_handler(CommandHandler("cleanup", manual_cleanup))  # Admin command for manual cleanup
        app.add_handler(CommandHandler("set_bal", set_balance))     # Admin command for setting balance
        app.add_handler(CallbackQueryHandler(handle_button))
        
        # Initialize bot (load data from Firebase)
        asyncio.run(initialize_bot())
        
        # Start the Bot
        print("Бот запущен!")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()
