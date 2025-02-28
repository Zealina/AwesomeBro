#!/usr/bin/env python3
"""Automate Stuff"""

import os
import json
from telegram import Bot, Poll, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Load bot token from environment variable
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

DATA_FILE = "bot_data.json"

# Load stored data (groups and allowed users)
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"groups": {}, "allowed_users": []}

# Helper function to save data
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Command Handlers
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Welcome! I am a quiz bot.\n\n"
        "Commands:\n"
        "/addgroup group_name group_id - Add a new group\n"
        "/adduser user_id - Add an allowed user\n"
        "/listgroups - Show available groups\n"
        "/listusers - Show allowed users\n"
        "To send a quiz, use:\n"
        "GroupName | Question | Option1 | Option2 | Option3 | Option4 | CorrectIndex"
    )

async def add_group(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in data["allowed_users"]:
        await update.message.reply_text("You are not authorized to add groups.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /addgroup group_name group_id")
        return

    group_name, group_id = args[0], args[1]
    try:
        group_id = int(group_id)
    except ValueError:
        await update.message.reply_text("Invalid group ID. It should be a number.")
        return

    data["groups"][group_name] = group_id
    save_data()
    await update.message.reply_text(f"Group '{group_name}' added successfully!")

async def add_user(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in data["allowed_users"]:
        await update.message.reply_text("You are not authorized to add users.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /adduser user_id")
        return

    try:
        new_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID. It should be a number.")
        return

    if new_user_id in data["allowed_users"]:
        await update.message.reply_text("User is already authorized.")
    else:
        data["allowed_users"].append(new_user_id)
        save_data()
        await update.message.reply_text(f"User {new_user_id} added successfully!")

async def list_groups(update: Update, context: CallbackContext):
    if not data["groups"]:
        await update.message.reply_text("No groups added yet.")
    else:
        groups_list = "\n".join([f"{name}: {chat_id}" for name, chat_id in data["groups"].items()])
        await update.message.reply_text(f"Available groups:\n{groups_list}")

async def list_users(update: Update, context: CallbackContext):
    if not data["allowed_users"]:
        await update.message.reply_text("No users added yet.")
    else:
        users_list = "\n".join([str(user_id) for user_id in data["allowed_users"]])
        await update.message.reply_text(f"Allowed users:\n{users_list}")

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in data["allowed_users"]:
        await update.message.reply_text("You are not authorized to send quizzes.")
        return

    text = update.message.text.strip()
    parts = text.split("|")

    if len(parts) < 6:
        await update.message.reply_text(
            "Invalid format! Use:\nGroupName | Question | Option1 | Option2 | Option3 | Option4 | CorrectIndex"
        )
        return

    group_name = parts[0].strip()
    if group_name not in data["groups"]:
        await update.message.reply_text(
            f"Unknown group: {group_name}. Use /listgroups to see available groups."
        )
        return

    chat_id = data["groups"][group_name]
    question = parts[1].strip()
    options = [parts[2].strip(), parts[3].strip(), parts[4].strip(), parts[5].strip()]

    try:
        correct_option = int(parts[6].strip())  # Extract correct index
        if correct_option < 0 or correct_option >= len(options):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Invalid correct answer index. It should be 0, 1, 2, or 3.")
        return

    bot = Bot(TOKEN)
    await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_option
    )
    await update.message.reply_text(f"Quiz sent to {group_name}.")

# Initialize the bot
app = Application.builder().token(TOKEN).build()

# Register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addgroup", add_group))
app.add_handler(CommandHandler("adduser", add_user))
app.add_handler(CommandHandler("listgroups", list_groups))
app.add_handler(CommandHandler("listusers", list_users))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Start the bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run_polling()
