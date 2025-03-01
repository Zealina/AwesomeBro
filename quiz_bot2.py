#!/usr/bin/env python3
"""Automate stuff questions"""

import os
import json
from telegram import Bot, Poll, Update, ChatMember, MessageEntity
from telegram.ext import Application, CommandHandler, CallbackContext

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

DATA_FILE = "bot_data.json"

data = {"group_id": None, "topics": {}}
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Welcome to the Quiz Bot! Commands:\n"
        "/start - Lists all the available commands\n"
        "/setgroup - selects the group to add the questions\n" 
        "/listtopics - lists all available topics in the group\n"
        "/refreshtopics - updates the list of available topics\n"
        "/addquiz - add a single question to the bot"
    )

async def set_group(update: Update, context: CallbackContext):
    """Sets the group id for the bot"""
    try:
        group_id = update.message.text.split()
        group_id = int(group_id[-1])
    except Exception as e:
        await update.message.reply_text("Usage: /setgroup <group_id>")
        return
    data["group_id"] = group_id
    await update.message.reply_text(f"Group set successfully {group_id}!")
    return
    

async def list_topics(update: Update, context: CallbackContext):
    """Lists all cached topics."""
    topics = "\n".join([f"{name}: {tid}" for name, tid in data["topics"].items()])
    await update.message.reply_text(f"Available topics:\n{topics if topics else 'No topics found.'}")


async def refresh_topics(update: Update, context: CallbackContext):
    """Refreshes the list of available topics in the group."""
    bot = context.bot
    try:
        chat = await bot.get_chat(data["group_id"])  # Get chat details
        print(chat)
#        if not chat.has_protected_content:  # Ensure it's a forum-enabled group
#           await update.message.reply_text("This group does not support topics.")
#            return
        
        # Extract topic IDs and names
        topics = {topic.title: topic.id for topic in chat.available_topics}
        print(chat.available_topics)
        data["topics"] = topics
        save_data()
        
        await update.message.reply_text("Topics refreshed successfully!")
    except Exception as e:
        await update.message.reply_text(f"Error refreshing topics: {str(e)}")


async def add_quiz(update: Update, context: CallbackContext):
    """Adds a quiz to a specific topic in the group."""
    bot = context.bot
    
    parts = update.message.text.split("|")
    if len(parts) < 4:
        await update.message.reply_text("Usage: /addquiz topic | question | option1 | option2 | ... | correct_option_index")
        return
    
    topic_name = parts[0].replace("/addquiz ", "").strip().lower()
    question = parts[1].strip()
    options = [opt.strip() for opt in parts[2:-1]]
    
    try:
        correct_index = int(parts[-1].strip())
        if correct_index < 0 or correct_index >= len(options):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Invalid correct option index.")
        return

    if topic_name not in data["topics"]:
        await refresh_topics(update, context)
        if topic_name not in data["topics"]:
            await update.message.reply_text(f"Topic '{topic_name}' not found in the group.")
            return
    
    topic_id = data["topics"][topic_name]
    await bot.send_poll(
        chat_id=data["group_id"],
        question=question,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index,
        message_thread_id=topic_id
    )
    await update.message.reply_text("Quiz added successfully!")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setgroup", set_group))
app.add_handler(CommandHandler("refreshtopics", refresh_topics))
app.add_handler(CommandHandler("listtopics", list_topics))
app.add_handler(CommandHandler("addquiz", add_quiz))

if __name__ == "__main__":
    print("Bot is running...")
    app.run_polling()
