#!/usr/bin/env python3
"""Automate setting quiz"""

import os
import json
import csv
from telegram import Bot, Poll, Update, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Load environment variables
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

DATA_FILE = "bot_data.json"

# Load or initialize data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"groups": {}, "allowed_users": []}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Check if a user is an admin of the group
async def is_admin(update: Update, group_id: int):
    bot = update.get_bot()
    chat_member = await bot.get_chat_member(group_id, update.message.from_user.id)
    return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Welcome to the Quiz Bot! Commands:\n"
        "/addgroup group_name group_id - Add a new group\n"
        "/removegroup group_name - Remove a group\n"
        "/adduser user_id - Add an allowed user\n"
        "/removeuser user_id - Remove an allowed user\n"
        "/listgroups - Show available groups\n"
        "/listusers - Show allowed users\n"
        "/clearanswers group_name - Clear answers from all questions in a group\n"
        "/clearallanswers - Clear answers from all groups\n"
        "/bulkadd - Upload a CSV file with questions\n"
        "/addquiz - add a single question to the bot"
    )

async def add_group(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /addgroup group_name group_id")
        return
    group_name, group_id = context.args[0], context.args[1]
    try:
        group_id = int(group_id)
        if not await is_admin(update, group_id):
            await update.message.reply_text("You must be an admin of this group to add it.")
            return
        data["groups"][group_name] = group_id
        save_data()
        await update.message.reply_text(f"Group '{group_name}' added successfully!")
    except ValueError:
        await update.message.reply_text("Invalid group ID.")

async def remove_group(update: Update, context: CallbackContext):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removegroup group_name")
        return
    group_name = context.args[0]
    if group_name in data["groups"]:
        del data["groups"][group_name]
        save_data()
        await update.message.reply_text(f"Group '{group_name}' removed successfully!")
    else:
        await update.message.reply_text("Group not found.")

async def add_user(update: Update, context: CallbackContext):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adduser user_id")
        return
    try:
        new_user_id = int(context.args[0])
        if new_user_id not in data["allowed_users"]:
            data["allowed_users"].append(new_user_id)
            save_data()
            await update.message.reply_text(f"User {new_user_id} added successfully!")
        else:
            await update.message.reply_text("User already exists.")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")

async def remove_user(update: Update, context: CallbackContext):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removeuser user_id")
        return
    try:
        user_id = int(context.args[0])
        if user_id in data["allowed_users"]:
            data["allowed_users"].remove(user_id)
            save_data()
            await update.message.reply_text(f"User {user_id} removed successfully!")
        else:
            await update.message.reply_text("User not found.")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")

async def list_groups(update: Update, context: CallbackContext):
    msg = "\n".join([f"{name}: {chat_id}" for name, chat_id in data["groups"].items()])
    await update.message.reply_text(f"Available groups:\n{msg if msg else 'No groups added yet.'}")

async def list_users(update: Update, context: CallbackContext):
    msg = "\n".join(map(str, data["allowed_users"]))
    await update.message.reply_text(f"Allowed users:\n{msg if msg else 'No users added yet.'}")

async def clear_answers(update: Update, context: CallbackContext):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /clearanswers group_name")
        return
    group_name = context.args[0]
    if group_name in data["groups"]:
        await update.message.reply_text(f"Answers cleared for group '{group_name}'.")
    else:
        await update.message.reply_text("Group not found.")

async def clear_all_answers(update: Update, context: CallbackContext):
    await update.message.reply_text("Answers cleared for all groups.")

async def bulk_add(update: Update, context: CallbackContext):
    if not update.message.document:
        await update.message.reply_text("Please upload a CSV file.")
        return
    file = await update.message.document.get_file()
    file_path = f"/tmp/{update.message.document.file_name}"
    await file.download_to_drive(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 6:
                continue
            group_name, question, *options, correct_index = [p.strip() for p in row]
            if group_name not in data["groups"]:
                continue
            try:
                correct_index = int(correct_index)
                if correct_index < 0 or correct_index >= len(options):
                    continue
            except ValueError:
                continue
            await context.bot.send_poll(
                chat_id=data["groups"][group_name],
                question=question,
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_index
            )
    await update.message.reply_text("Bulk upload complete!")

async def add_quiz(update: Update, context: CallbackContext):
    parts = update.message.text.split("|")
    if len(parts) < 4:
        await update.message.reply_text("Usage: /addquiz group_name | question | option1 | option2 | ... | correct_option_index")
        return
    
    group_name = parts[0].replace("/addquiz ", "").strip()
    question = parts[1].strip()
    options = [opt.strip() for opt in parts[2:-1]]
    
    try:
        correct_index = int(parts[-1].strip())
        if correct_index < 0 or correct_index >= len(options):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Invalid correct option index.")
        return
    
    if group_name not in data["groups"]:
        await update.message.reply_text("Group not found.")
        return
    
    await context.bot.send_poll(
        chat_id=data["groups"][group_name],
        question=question,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index
    )
    await update.message.reply_text("Quiz added successfully!")

# Initialize the bot
app = Application.builder().token(TOKEN).build()

# Register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addgroup", add_group))
app.add_handler(CommandHandler("removegroup", remove_group))
app.add_handler(CommandHandler("adduser", add_user))
app.add_handler(CommandHandler("removeuser", remove_user))
app.add_handler(CommandHandler("listgroups", list_groups))
app.add_handler(CommandHandler("listusers", list_users))
app.add_handler(CommandHandler("clearanswers", clear_answers))
app.add_handler(CommandHandler("clearallanswers", clear_all_answers))
app.add_handler(CommandHandler("bulkadd", bulk_add))
app.add_handler(CommandHandler("addquiz", add_quiz))

# Start the bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run_polling()
