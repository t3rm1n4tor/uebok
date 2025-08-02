import os
import random
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    CallbackQueryHandler
)
from datetime import datetime, timedelta

# Store user data in memory
user_balances = {}
active_games = {}
free_cooldowns = {}  # Track when users last used /free command
farm_values = {}  # Track farm values for users
farm_cooldowns = {}  # Track farm cooldowns
case_cooldowns = {}  # Track case opening cooldowns
user_inventories = {}  # Track user inventories
farm_fail_chances = {}  # Track farm fail chances for users

# Game configuration
MIN_BET = 5
TOTAL_TILES = 25  # Changed to 25 tiles
ROWS = 5  # Changed to 5 rows
COLS = 5  # Changed to 5 columns
FREE_COINS = 10
FREE_COOLDOWN_MINUTES = 25
FARM_COOLDOWN_MINUTES = 5  # Changed from 30 to 5 minutes
FARM_STARTING_VALUE = 5
FARM_FAIL_CHANCE = 10  # Percentage chance of failing
CASE_COOLDOWN_SECONDS = 5  # Anti-spam cooldown for case opening

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
    "defending_aura": {
        "name": "Защитная аура",
        "emoji": "🛡️",
        "description": "10% шанс спастись от мины в игре минки (одноразовое использование)",
        "price": 150
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
    
    await update.message.reply_text(
        f"🎮 *Добро пожаловать в игровой бот минки, {user_name}!* 🎮\n\n"
        f"💰 Ваш баланс: *{user_balances[user_id]} ktn$*\n\n"
        "📋 *Доступные команды:*\n"
        "▫️ /free - Получить 10 ktn$ бесплатно (раз в 25 минут)\n"
        "▫️ /mines [кол-во_мин] [ставка] - Играть в минки\n"
        "▫️ /farm - Фармить ktn$ (с растущей наградой)\n"
        "▫️ /upgrade farm [сумма] [режим] - Улучшить ферму\n"
        "▫️ /opencase [1-3] - Открыть кейс с призами\n"
        "▫️ /shop [buy/stock] [предмет] - Магазин предметов\n"
        "▫️ /balance - Проверить баланс\n"
        "▫️ /reset - Сбросить игру, если возникли проблемы\n\n"
        "🎯 *Удачной игры!*",
        parse_mode="Markdown"
    )

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
                f"⏳ *Подождите!* Вы сможете получить бесплатные монеты через *{minutes} мин. {seconds} сек.*\n\n"
                f"Текущий баланс: *{user_balances[user_id]} ktn$*",
                parse_mode="Markdown"
            )
            return
    
    # Give free coins
    user_balances[user_id] += FREE_COINS
    free_cooldowns[user_id] = current_time
    
    await update.message.reply_text(
        f"💸 *Поздравляем!* Вы получили *{FREE_COINS} ktn$*!\n\n"
        f"💰 Ваш баланс: *{user_balances[user_id]} ktn$*\n\n"
        f"⏰ Следующие бесплатные монеты будут доступны через *{FREE_COOLDOWN_MINUTES} минут*.",
        parse_mode="Markdown"
    )

async def farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_time = datetime.now()
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
        
    if user_id not in farm_values:
        farm_values[user_id] = FARM_STARTING_VALUE
        
    if user_id not in farm_fail_chances:
        farm_fail_chances[user_id] = FARM_FAIL_CHANCE
    
    # Check cooldown
    if user_id in farm_cooldowns:
        last_farm_time = farm_cooldowns[user_id]
        time_since_last = current_time - last_farm_time
        cooldown_time = timedelta(minutes=FARM_COOLDOWN_MINUTES)
        
        if time_since_last < cooldown_time:
            remaining = cooldown_time - time_since_last
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            
            await update.message.reply_text(
                f"🌱 *Ваша ферма ещё растёт!*\n\n"
                f"⏳ Следующий сбор урожая через *{minutes} мин. {seconds} сек.*\n"
                f"🌾 Ожидаемый урожай: *{farm_values[user_id]} ktn$*\n\n"
                f"💰 Текущий баланс: *{user_balances[user_id]} ktn$*",
                parse_mode="Markdown"
            )
            return
    
    # Check for failure
    fail = random.randint(1, 100) <= farm_fail_chances[user_id]
    
    if fail:
        # Farming failed
        farm_cooldowns[user_id] = current_time
        next_value = round(farm_values[user_id] * 1.5)
        
        await update.message.reply_text(
            f"❌ *Неудача!* Ваш урожай погиб!\n\n"
            f"🌱 Но не расстраивайтесь, следующий урожай будет ещё больше!\n"
            f"🌾 Следующий ожидаемый урожай: *{next_value} ktn$*\n\n"
            f"⏰ Приходите через *{FARM_COOLDOWN_MINUTES} минут*\n"
            f"💰 Текущий баланс: *{user_balances[user_id]} ktn$*",
            parse_mode="Markdown"
        )
        
        # Update farm value
        farm_values[user_id] = next_value
    else:
        # Farming succeeded
        current_value = farm_values[user_id]
        user_balances[user_id] += current_value
        farm_cooldowns[user_id] = current_time
        next_value = round(current_value * 1.5)
        
        await update.message.reply_text(
            f"✅ *Успех!* Вы собрали *{current_value} ktn$* с вашей фермы!\n\n"
            f"🌱 Ваша ферма растёт!\n"
            f"🌾 Следующий ожидаемый урожай: *{next_value} ktn$*\n\n"
            f"⏰ Приходите через *{FARM_COOLDOWN_MINUTES} минут*\n"
            f"💰 Текущий баланс: *{user_balances[user_id]} ktn$*",
            parse_mode="Markdown"
        )
        
        # Update farm value
        farm_values[user_id] = next_value

async def upgrade_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
        
    if user_id not in farm_values:
        farm_values[user_id] = FARM_STARTING_VALUE
        
    if user_id not in farm_fail_chances:
        farm_fail_chances[user_id] = FARM_FAIL_CHANCE
    
    # Check arguments
    if len(context.args) != 2:
        await update.message.reply_text(
            "ℹ️ *Использование:* /upgrade farm [сумма] [режим]\n\n"
            "*Доступные режимы:*\n"
            "1 - Инвестировать в увеличение прибыли\n"
            "2 - Инвестировать в защиту от неудач\n\n"
            "Пример: `/upgrade farm 100 1`",
            parse_mode="Markdown"
        )
        return
    
    try:
        amount = int(context.args[0])
        mode = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ *Ошибка!* Сумма и режим должны быть числами.",
            parse_mode="Markdown"
        )
        return
    
    # Validate input
    if amount <= 0:
        await update.message.reply_text(
            "❌ *Ошибка!* Сумма должна быть положительным числом.",
            parse_mode="Markdown"
        )
        return
    
    if mode not in [1, 2]:
        await update.message.reply_text(
            "❌ *Ошибка!* Режим должен быть 1 или 2.\n\n"
            "*Доступные режимы:*\n"
            "1 - Инвестировать в увеличение прибыли\n"
            "2 - Инвестировать в защиту от неудач",
            parse_mode="Markdown"
        )
        return
    
    if amount > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ *Недостаточно средств!*\n\n"
            f"Ваш баланс: *{user_balances[user_id]} ktn$*\n"
            f"Требуется: *{amount} ktn$*",
            parse_mode="Markdown"
        )
        return
    
    # Deduct the investment
    user_balances[user_id] -= amount
    
    # Apply upgrade based on mode
    if mode == 1:
        # Upgrade farm productivity
        percentage_increase = amount / 100
        increase_factor = 0.5 + percentage_increase
        
        old_value = farm_values[user_id]
        farm_values[user_id] = round(old_value * (1 + increase_factor / 10), 1)
        
        await update.message.reply_text(
            f"🌱 *Ферма улучшена!*\n\n"
            f"💰 Инвестировано: *{amount} ktn$*\n"
            f"📈 Доходность увеличена: *{old_value} ktn$ → {farm_values[user_id]} ktn$*\n\n"
            f"💹 Ваш баланс: *{user_balances[user_id]} ktn$*",
            parse_mode="Markdown"
        )
    else:
        # Upgrade farm immunity
        percentage_decrease = min(2.5, amount / 40)  # Max 2.5% decrease per upgrade
        
        old_chance = farm_fail_chances[user_id]
        farm_fail_chances[user_id] = max(1, round(old_chance - percentage_decrease, 1))  # Minimum 1%
        
        await update.message.reply_text(
            f"🛡️ *Защита фермы улучшена!*\n\n"
            f"💰 Инвестировано: *{amount} ktn$*\n"
            f"📉 Шанс неудачи снижен: *{old_chance}% → {farm_fail_chances[user_id]}%*\n\n"
            f"💹 Ваш баланс: *{user_balances[user_id]} ktn$*",
            parse_mode="Markdown"
        )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
    
    # Check arguments
    if len(context.args) < 1:
        await update.message.reply_text(
            "ℹ️ *Использование:* /shop [buy/stock] [предмет]\n\n"
            "Пример: `/shop buy defending_aura` или `/shop stock`",
            parse_mode="Markdown"
        )
        return
    
    action = context.args[0].lower()
    
    if action == "stock":
        # Show available items
        stock_text = "🛒 *Доступные предметы в магазине:*\n\n"
        
        for item_id, item in SHOP_ITEMS.items():
            stock_text += f"{item['emoji']} *{item['name']}* - {item['price']} ktn$\n"
            stock_text += f"└ {item['description']}\n\n"
        
        stock_text += f"💰 Ваш баланс: *{user_balances[user_id]} ktn$*\n\n"
        stock_text += "Для покупки используйте: `/shop buy [предмет]`"
        
        await update.message.reply_text(
            stock_text,
            parse_mode="Markdown"
        )
        return
    
    elif action == "buy":
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ *Ошибка!* Укажите предмет для покупки.\n"
                "Пример: `/shop buy defending_aura`\n\n"
                "Для просмотра доступных предметов используйте: `/shop stock`",
                parse_mode="Markdown"
            )
            return
        
        item_id = context.args[1].lower()
        
        if item_id not in SHOP_ITEMS:
            await update.message.reply_text(
                "❌ *Ошибка!* Указанный предмет не найден.\n\n"
                "Для просмотра доступных предметов используйте: `/shop stock`",
                parse_mode="Markdown"
            )
            return
        
        item = SHOP_ITEMS[item_id]
        
        # Check if user has enough money
        if user_balances[user_id] < item["price"]:
            await update.message.reply_text(
                f"❌ *Недостаточно средств!*\n\n"
                f"Ваш баланс: *{user_balances[user_id]} ktn$*\n"
                f"Стоимость предмета: *{item['price']} ktn$*",
                parse_mode="Markdown"
            )
            return
        
        # Process purchase
        user_balances[user_id] -= item["price"]
        
        if item_id not in user_inventories[user_id]:
            user_inventories[user_id][item_id] = 0
        
        user_inventories[user_id][item_id] += 1
        
        await update.message.reply_text(
            f"✅ *Покупка успешна!*\n\n"
            f"{item['emoji']} Вы приобрели: *{item['name']}*\n"
            f"💰 Стоимость: *{item['price']} ktn$*\n"
            f"📦 У вас в инвентаре: *{user_inventories[user_id][item_id]}* шт.\n\n"
            f"💹 Ваш баланс: *{user_balances[user_id]} ktn$*",
            parse_mode="Markdown"
        )
        return
    
    else:
        await update.message.reply_text(
            "❌ *Ошибка!* Неверное действие.\n\n"
            "Доступные действия: `buy`, `stock`",
            parse_mode="Markdown"
        )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    await update.message.reply_text(
        f"💰 *Баланс пользователя {user_name}*\n\n"
        f"*{user_balances[user_id]} ktn$*",
        parse_mode="Markdown"
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
                f"⏳ *Подождите {remaining_seconds} сек. перед открытием следующего кейса!*",
                parse_mode="Markdown"
            )
            return
    
    # Make sure user has balance
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    # Check arguments
    if len(context.args) != 1:
        await update.message.reply_text(
            "ℹ️ *Использование:* /opencase [номер_кейса]\n\n"
            "*Доступные кейсы:*\n"
            "1 - Бронзовый кейс (35 ktn$)",
            parse_mode="Markdown"
        )
        return
    
    case_type = context.args[0]
    
    # Validate case type
    if case_type not in CASE_COSTS:
        await update.message.reply_text(
            "❌ *Ошибка!* Указан неверный тип кейса.\n\n"
            "*Доступные кейсы:*\n"
            "1 - Бронзовый кейс (35 ktn$)",
            parse_mode="Markdown"
        )
        return
    
    case_cost = CASE_COSTS[case_type]
    
    # Check if user has enough balance
    if user_balances[user_id] < case_cost:
        await update.message.reply_text(
            f"❌ *Недостаточно средств!*\n\n"
            f"Ваш баланс: *{user_balances[user_id]} ktn$*\n"
            f"Стоимость кейса: *{case_cost} ktn$*",
            parse_mode="Markdown"
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
        f"🎁 *Открываем {case_names[case_type]} кейс...*\n\n"
        f"💰 Стоимость: *{case_cost} ktn$*\n"
        f"👤 Игрок: *{user_name}*\n\n"
        f"⏳ *Выбираем приз...*",
        parse_mode="Markdown"
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
                text=f"🎁 *Открываем {case_names[case_type]} кейс...*\n\n"
                     f"💰 Стоимость: *{case_cost} ktn$*\n"
                     f"👤 Игрок: *{user_name}*\n\n"
                     f"⏳ *Выпадает: {random_prize['emoji']} ({random_prize['value']} ktn$)*",
                parse_mode="Markdown"
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
    
    # Final message
    profit = final_prize["value"] - case_cost
    profit_str = f"+{profit}" if profit >= 0 else f"{profit}"
    
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=initial_message.message_id,
        text=f"🎁 *{case_names[case_type]} кейс открыт!*\n\n"
             f"🏆 *Вы выиграли: {final_prize['emoji']} {final_prize['value']} ktn$*\n"
             f"📊 Профит: *{profit_str} ktn$*\n\n"
             f"💰 Ваш баланс: *{user_balances[user_id]} ktn$*",
        parse_mode="Markdown"
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
            "🔄 *Ваша игра успешно сброшена!*\n"
            "Теперь вы можете начать новую игру.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ У вас нет активных игр, которые нужно сбросить.",
            parse_mode="Markdown"
        )

async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if user is admin (you can modify this check as needed)
    user_id = update.effective_user.id
    if user_id != int(os.getenv("ADMIN_ID", "0")):  # Set ADMIN_ID env var or modify this check
        return
    
    # Count before cleanup
    count_before = len(active_games)
    
    # Find stale games (older than 1 hour)
    current_time = datetime.now()
    stale_game_users = []
    
    for user_id, game in active_games.items():
        if 'start_time' not in game:
            game['start_time'] = current_time
            continue
            
        time_diff = current_time - game['start_time']
        if time_diff > timedelta(hours=1):
            stale_game_users.append(user_id)
    
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
    
    # Report results
    count_after = len(active_games)
    await update.message.reply_text(
        f"🧹 *Очистка завершена*\n\n"
        f"Было игр: *{count_before}*\n"
        f"Удалено: *{count_before - count_after}*\n"
        f"Осталось: *{count_after}*",
        parse_mode="Markdown"
    )

async def mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    if user_id not in user_inventories:
        user_inventories[user_id] = {}
    
    # Check if user already has an active game
    if user_id in active_games:
        await update.message.reply_text(
            "⚠️ *У вас уже есть активная игра!*\n"
            "Завершите её, прежде чем начать новую, или используйте /reset чтобы сбросить.",
            parse_mode="Markdown"
        )
        return
    
    # Parse arguments
    if len(context.args) != 2:
        await update.message.reply_text(
            "ℹ️ *Использование:* /mines [количество_мин] [ставка]\n\n"
            "Пример: `/mines 5 10`",
            parse_mode="Markdown"
        )
        return
    
    try:
        num_mines = int(context.args[0])
        bet = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ *Ошибка!* Оба аргумента должны быть числами.",
            parse_mode="Markdown"
        )
        return
    
    # Validate input
    if num_mines <= 0 or num_mines >= TOTAL_TILES:
        await update.message.reply_text(
            f"❌ *Ошибка!* Количество мин должно быть от 1 до {TOTAL_TILES-1}.",
            parse_mode="Markdown"
        )
        return
    
    if bet < MIN_BET:
        await update.message.reply_text(
            f"❌ *Ошибка!* Минимальная ставка: *{MIN_BET} ktn$*.",
            parse_mode="Markdown"
        )
        return
    
    if bet > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ *Недостаточно средств!*\n\n"
            f"Ваш баланс: *{user_balances[user_id]} ktn$*\n"
            f"Требуется: *{bet} ktn$*",
            parse_mode="Markdown"
        )
        return
    
    # Deduct bet from balance
    user_balances[user_id] -= bet
    
    # Generate mine positions
    all_positions = list(range(TOTAL_TILES))
    mine_positions = random.sample(all_positions, num_mines)
    
    # Check if user has defending aura
    has_aura = user_inventories.get(user_id, {}).get("defending_aura", 0) > 0
    
    # Create game state
    game_state = {
        "bet": bet,
        "num_mines": num_mines,
        "mine_positions": mine_positions,
        "revealed_positions": [],
        "protected_positions": [],  # For defending aura
        "game_over": False,
        "win": False,
        "user_id": user_id,
        "user_name": user_name,
        "chat_id": update.effective_chat.id,
        "start_time": datetime.now(),  # Track when the game started
        "has_aura": has_aura,
        "aura_used": False
    }
    
    active_games[user_id] = game_state
    
    # Create and send the game board
    await send_game_board(update, context, user_id)

async def send_game_board(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    try:
        if user_id not in active_games:
            return
            
        game = active_games[user_id]
        
        # Calculate multiplier based on revealed safe tiles
        revealed_count = len(game["revealed_positions"])
        
        # Calculate current multiplier
        mines_left = game["num_mines"]
        tiles_left = TOTAL_TILES - revealed_count
        
        if tiles_left > mines_left:
            multiplier = round((tiles_left / (tiles_left - mines_left)) * (1 + (revealed_count * 0.1)), 2)
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
                    f"🎉 *{game['user_name']} выиграл {game['win_amount']} ktn$!* 🎉\n\n"
                    f"💰 Множитель: *{multiplier}x*\n"
                    f"💵 Ставка: *{game['bet']} ktn$*\n"
                    f"💎 Выигрыш: *{game['win_amount']} ktn$*"
                )
            else:
                status = (
                    f"💥 *Ой! {game['user_name']} подорвался на мине!* 💥\n\n"
                    f"❌ Ставка *{game['bet']} ktn$* потеряна.\n"
                    f"🎮 Удачи в следующий раз!"
                )
        else:
            status = (
                f"🎮 *Минки* | Игрок: *{game['user_name']}*\n\n"
                f"💣 Мин на поле: *{game['num_mines']}*\n"
                f"💰 Ставка: *{game['bet']} ktn$*\n"
                f"✅ Открыто безопасных клеток: *{revealed_count}*\n"
                f"📈 Текущий множитель: *{multiplier}x*\n"
                f"💎 Потенциальный выигрыш: *{potential_win} ktn$*"
            )
            
            # Add aura info if available
            if game["has_aura"] and not game["aura_used"]:
                status += "\n🛡️ *Защитная аура активна* (10% шанс защиты от мины)"
            elif game["aura_used"]:
                status += "\n🛡️ *Защитная аура использована!*"
                
            status += "\n\n*Нажимайте на клетки, чтобы открыть их!*"
        
        # Update or send new message
        if "message_id" in game and "chat_id" in game:
            try:
                await context.bot.edit_message_text(
                    chat_id=game["chat_id"],
                    message_id=game["message_id"],
                    text=status,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as e:
                # If there's an error updating, send a new message
                message = await context.bot.send_message(
                    chat_id=game["chat_id"],
                    text=status,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
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
                reply_markup=reply_markup,
                parse_mode="Markdown"
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
    except Exception as e:
        print(f"Error in send_game_board: {e}")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        
        # Extract data from callback
        callback_parts = query.data.split('_')
        caller_id = update.effective_user.id
        
        # Extract user_id from callback data
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
        
        # Check if game is over
        if game["game_over"]:
            await query.answer("Эта игра уже завершена!", show_alert=True)
            return
        
        # Answer the callback query to stop loading indicator
        await query.answer()
        
        # Handle cashout
        if callback_parts[0] == "cashout":
            # Calculate win amount
            revealed_count = len(game["revealed_positions"])
            mines_left = game["num_mines"]
            tiles_left = TOTAL_TILES - revealed_count
            
            if tiles_left > mines_left:
                multiplier = round((tiles_left / (tiles_left - mines_left)) * (1 + (revealed_count * 0.1)), 2)
            else:
                multiplier = 1.0
            
            win_amount = round(game["bet"] * multiplier)
            
            # Update game state
            game["game_over"] = True
            game["win"] = True
            game["win_amount"] = win_amount
            
            # Update user balance
            user_balances[game_owner_id] += win_amount
            
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
                # Check if user has active aura
                if game["has_aura"] and not game["aura_used"] and random.random() < 0.1:  # 10% chance
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
                    await query.answer("🛡️ Защитная аура сработала! Будь акуратным бро!", show_alert=True)
                    await send_game_board(update, context, game_owner_id)
                    return
                
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
    except Exception as e:
        print(f"Error in handle_button: {e}")

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
        
        if tiles_left > mines_left:
            multiplier = round((tiles_left / (tiles_left - mines_left)) * (1 + (revealed_count * 0.1)), 2)
        else:
            multiplier = 1.0
            
        status = (
            f"🎉 *{game['user_name']} выиграл {game['win_amount']} ktn$!* 🎉\n\n"
            f"💰 Множитель: *{multiplier}x*\n"
            f"💵 Ставка: *{game['bet']} ktn$*\n"
            f"💎 Выигрыш: *{game['win_amount']} ktn$*\n\n"
            f"⏱️ *Сообщение будет удалено через 5 секунд*"
        )
    else:
        status = (
            f"💥 *Ой! {game['user_name']} подорвался на мине!* 💥\n\n"
            f"❌ Ставка *{game['bet']} ktn$* потеряна.\n"
            f"🎮 Удачи в следующий раз!\n\n"
            f"⏱️ *Сообщение будет удалено через 5 секунд*"
        )
    
    # Update message
    try:
        await context.bot.edit_message_text(
            chat_id=game["chat_id"],
            message_id=game["message_id"],
            text=status,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error in show_all_mines: {e}")

def main():
    # Create the Application
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CommandHandler("farm", farm))
    app.add_handler(CommandHandler("upgrade", upgrade_farm))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("opencase", opencase))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("mines", mines))
    app.add_handler(CommandHandler("reset", reset_game))
    app.add_handler(CommandHandler("cleanup", manual_cleanup))  # Admin command for manual cleanup
    app.add_handler(CallbackQueryHandler(handle_button))
    
    # Start the Bot
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
