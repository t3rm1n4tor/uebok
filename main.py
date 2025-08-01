import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    CallbackQueryHandler
)

# Store user data in memory
user_balances = {}
active_games = {}

# Game configuration
MIN_BET = 5
TOTAL_TILES = 24
FREE_COINS = 10
ROWS = 4
COLS = 6

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    await update.message.reply_text(
        f"Welcome to the Mines gambling bot!\n"
        f"Your balance: {user_balances[user_id]} ktn$\n\n"
        "Commands:\n"
        "/free - Get 10 ktn$ for free\n"
        "/mines [number_of_mines] [bet] - Play Mines game\n"
        "/balance - Check your balance"
    )

async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    user_balances[user_id] += FREE_COINS
    await update.message.reply_text(f"You received {FREE_COINS} ktn$! Your balance: {user_balances[user_id]} ktn$")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    await update.message.reply_text(f"Your balance: {user_balances[user_id]} ktn$")

async def mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_balances:
        user_balances[user_id] = 0
    
    # Check if user already has an active game
    if user_id in active_games:
        await update.message.reply_text("You already have an active game. Finish it first!")
        return
    
    # Parse arguments
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /mines [number_of_mines] [bet]")
        return
    
    try:
        num_mines = int(context.args[0])
        bet = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Both arguments must be numbers.")
        return
    
    # Validate input
    if num_mines <= 0 or num_mines >= TOTAL_TILES:
        await update.message.reply_text(f"Number of mines must be between 1 and {TOTAL_TILES-1}.")
        return
    
    if bet < MIN_BET:
        await update.message.reply_text(f"Minimum bet is {MIN_BET} ktn$.")
        return
    
    if bet > user_balances[user_id]:
        await update.message.reply_text(f"Not enough balance. Your balance: {user_balances[user_id]} ktn$")
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
        "win": False
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
                
            callback_data = f"tile_{position}"
            keyboard_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        keyboard.append(keyboard_row)
    
    # Add cashout button if at least 3 safe tiles revealed
    if revealed_count >= 3 and not game["game_over"]:
        keyboard.append([
            InlineKeyboardButton(f"CASHOUT ({multiplier}x)", callback_data="cashout")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Calculate potential win
    potential_win = round(game["bet"] * multiplier)
    
    # Create status message
    if game["game_over"]:
        if game["win"]:
            status = f"You won {game['win_amount']} ktn$! 🎉"
        else:
            status = "You hit a mine! 💥 Better luck next time."
    else:
        status = (
            f"Mines: {game['num_mines']} | Bet: {game['bet']} ktn$\n"
            f"Safe tiles revealed: {revealed_count}\n"
            f"Current multiplier: {multiplier}x\n"
            f"Potential win: {potential_win} ktn$"
        )
    
    # Update or send new message
    if "message_id" in game:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=game["message_id"],
                text=status,
                reply_markup=reply_markup
            )
        except Exception:
            # If there's an error updating, send a new message
            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
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

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Answer the callback query
    
    user_id = update.effective_user.id
    
    if user_id not in active_games:
        await query.edit_message_text("No active game found. Start a new one with /mines.")
        return
    
    game = active_games[user_id]
    
    if game["game_over"]:
        await query.edit_message_text("This game is already over. Start a new one with /mines.")
        return
    
    # Handle cashout
    if query.data == "cashout":
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
        user_balances[user_id] += win_amount
        
        # Reveal all mines
        await show_all_mines(update, context, user_id)
        
        # Clean up
        del active_games[user_id]
        return
    
    # Handle tile click
    if query.data.startswith("tile_"):
        position = int(query.data.split("_")[1])
        
        # Check if tile already revealed
        if position in game["revealed_positions"]:
            await query.answer("This tile is already revealed!")
            return
        
        # Check if tile is a mine
        if position in game["mine_positions"]:
            # Game over - user hit a mine
            game["game_over"] = True
            
            # Show all mines
            await show_all_mines(update, context, user_id)
            
            # Clean up
            del active_games[user_id]
        else:
            # Safe tile - reveal it
            game["revealed_positions"].append(position)
            
            # Update game board
            await send_game_board(update, context, user_id)

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
                
            callback_data = f"tile_{position}"
            keyboard_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        keyboard.append(keyboard_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create status message
    if game["win"]:
        status = f"You won {game['win_amount']} ktn$! 🎉"
    else:
        status = "You hit a mine! 💥 Better luck next time."
    
    # Update message
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=game["message_id"],
        text=status,
        reply_markup=reply_markup
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
