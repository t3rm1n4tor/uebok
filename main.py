import os
import random
import time
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

# Game configuration
MIN_BET = 5
TOTAL_TILES = 25
FREE_COINS = 25
ROWS = 5
COLS = 5
FREE_COOLDOWN_HOURS = 0.5

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    await update.message.reply_text(
        f"🎮 *Добро пожаловать в игру мины, {user_name}!* 🎮\n\n"
        f"💰 Ваш баланс: *{user_balances[user_id]} ktn$*\n\n"
        "📋 *Доступные команды:*\n"
        "▫️ /free - Получить 10 ktn$ бесплатно (раз в 2 часа)\n"
        "▫️ /mines [кол-во_мин] [ставка] - Играть в минки\n"
        "▫️ /balance - Проверить баланс\n\n"
        "🎯 *НЕудачной игры!*",
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
        cooldown_time = timedelta(hours=FREE_COOLDOWN_HOURS)
        
        if time_since_last < cooldown_time:
            remaining = cooldown_time - time_since_last
            minutes = int(remaining.total_seconds() // 60)
            
            await update.message.reply_text(
                f"⏳ *Подождите!* Вы сможете получить бесплатные ктны через *{minutes} минут*\n\n"
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
        f"⏰ Следующие бесплатные ктны будут доступны через *{FREE_COOLDOWN_HOURS} часа*",
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

async def mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    # Check if user already has an active game
    if user_id in active_games:
        await update.message.reply_text(
            "⚠️ *У вас уже есть активная игра!*\n"
            "Завершите её, прежде чем начать новую :с",
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
            "❌ *Ошибка!* Оба аргумента должны быть числами, идиот блять",
            parse_mode="Markdown"
        )
        return
    
    # Validate input
    if num_mines <= 0 or num_mines >= TOTAL_TILES:
        await update.message.reply_text(
            f"❌ *Ошибка!* Количество мин должно быть от 1 до {TOTAL_TILES-1} тупой сука",
            parse_mode="Markdown"
        )
        return
    
    if bet < MIN_BET:
        await update.message.reply_text(
            f"❌ *Ошибка!* Минимальная ставка: *{MIN_BET} ktn$* понял?",
            parse_mode="Markdown"
        )
        return
    
    if bet > user_balances[user_id]:
        await update.message.reply_text(
            f"❌ *Недостаточно средств нищета блять 😂*\n\n"
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
    
    # Create game state
    game_state = {
        "bet": bet,
        "num_mines": num_mines,
        "mine_positions": mine_positions,
        "revealed_positions": [],
        "game_over": False,
        "win": False,
        "user_id": user_id,
        "user_name": user_name
    }
    
    active_games[user_id] = game_state
    
    # Create and send the game board
    await send_game_board(update, context, user_id)

async def send_game_board(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
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
            
            if position in game["revealed_positions"]:
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
            InlineKeyboardButton(f"💰 КЭШОУТ ({multiplier}x) 💰", callback_data=f"cashout_{user_id}")
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
                f"💥 *Пиздец! {game['user_name']} здох на мине нахуй(* 💥\n\n"
                f"❌ Ставка *{game['bet']} ktn$* потеряна, соси\n"
                f"😘 Удачи в следующий раз"
            )
    else:
        status = (
            f"🎮 *Минки* | Игрок: *{game['user_name']}*\n\n"
            f"💣 Мин на поле: *{game['num_mines']}*\n"
            f"💰 Ставка: *{game['bet']} ktn$*\n"
            f"✅ Открыто безопасных клеток: *{revealed_count}*\n"
            f"📈 Текущий множитель: *{multiplier}x*\n"
            f"💎 Выигрыш: *{potential_win} ktn$*\n\n"
            f"*Нажимайте на клетки, чтобы открыть их*"
        )
    
    # Update or send new message
    if "message_id" in game:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=game["message_id"],
                text=status,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            # If there's an error updating, send a new message
            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=status,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            game["message_id"] = message.message_id
    else:
        # First time sending the board
        message = await update.message.reply_text(
            text=status,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        game["message_id"] = message.message_id

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Answer the callback query
    
    caller_id = update.effective_user.id
    
    # Extract user_id from callback data
    callback_parts = query.data.split('_')
    game_owner_id = int(callback_parts[-1])
    
    # Security check: Only game owner can press buttons
    if caller_id != game_owner_id:
        await query.answer("⚠️ Ебалай это не твоя игра 💔", show_alert=True)
        return
    
    if game_owner_id not in active_games:
        await query.edit_message_text(
            "❌ *Игра не найдена!*\n"
            "Начните новую игру с помощью команды /mines 😋",
            parse_mode="Markdown"
        )
        return
    
    game = active_games[game_owner_id]
    
    if game["game_over"]:
        await query.edit_message_text(
            "⚠️ *Эта игра уже завершена!*\n"
            "Начните новую игру с помощью команды /mines",
            parse_mode="Markdown"
        )
        return
    
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
        
        # Clean up
        del active_games[game_owner_id]
        return
    
    # Handle tile click
    if callback_parts[0] == "tile":
        position = int(callback_parts[1])
        
        # Check if tile already revealed
        if position in game["revealed_positions"]:
            await query.answe("Бляять ты тупой что-ли")
            return
        
        # Check if tile is a mine
        if position in game["mine_positions"]:
            # Game over - user hit a mine
            game["game_over"] = True
            
            # Show all mines
            await show_all_mines(update, context, game_owner_id)
            
            # Clean up
            del active_games[game_owner_id]
        else:
            # Safe tile - reveal it
            game["revealed_positions"].append(position)
            
            # Update game board
            await send_game_board(update, context, game_owner_id)

async def show_all_mines(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    game = active_games[user_id]
    
    # Create keyboard with all mines revealed
    keyboard = []
    for row in range(ROWS):
        keyboard_row = []
        for col in range(COLS):
            position = row * COLS + col
            
            if position in game["mine_positions"]:
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
            f"💎 Выигрыш: *{game['win_amount']} ktn$*"
        )
    else:
        status = (
            f"💥 *Хуйня брат {game['user_name']} неповезло! :с* 💥\n\n"
            f"❌ Ставка *{game['bet']} ktn$* потеряна\n"
            f"**Надеюсь тебе повезёт в следующий раз...**"
        )
    
    # Update message
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=game["message_id"],
        text=status,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def main():
    # Create the Application
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("mines", mines))
    app.add_handler(CallbackQueryHandler(handle_button))
    
    # Start the Bot
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
