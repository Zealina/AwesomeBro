#!/usr/bin/env python3
"""Create MCQs and Organize Quizzes with Flask & PTB Webhooks"""

import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for webhooks
my_app = Flask(__name__)

@my_app.route("/greet")
def greet():
    return jsonify({"greeting": "Be thou greeted!"})

# Bot token from environment variable
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# Data file setup
DATA_FILE = "bot_data.json"
data = {"group_id": None, "topics": {}}

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Initialize PTB bot application
app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Welcome to the AwesomeBro!\n"
        "Commands:\n"
        "/start - Lists commands\n"
        "/setgroup <group_id> - Set group for quizzes\n"
        "/listtopics - List topics\n"
        "/addtopic <name> <id> - Add topic\n"
        "/addquiz - Add a quiz\n"
        "/bulkadd - Upload JSON file with quizzes\n"
        "/removetopic <name> - Remove a topic\n"
        "/clearresponses - Reset active quizzes"
    )

async def set_group(update: Update, context: CallbackContext):
    """Sets the group ID for the bot"""
    try:
        group_id = int(update.message.text.split()[-1])
    except ValueError:
        await update.message.reply_text("Usage: /setgroup <group_id>")
        return
    data["group_id"] = group_id
    save_data()
    await update.message.reply_text(f"Group set successfully: {group_id}!")

async def add_topic(update: Update, context: CallbackContext):
    """Manually adds a topic."""
    parts = update.message.text.split(" ", 2)
    if len(parts) < 3:
        await update.message.reply_text("Usage: /addtopic <topic_name> <topic_id>")
        return
    topic_name = parts[1].strip().lower()
    try:
        topic_id = int(parts[2].strip())
    except ValueError:
        await update.message.reply_text("Topic ID must be a number.")
        return
    data["topics"][topic_name] = topic_id
    save_data()
    await update.message.reply_text(f"Topic '{topic_name}' added successfully!")

async def list_topics(update: Update, context: CallbackContext):
    """Lists all manually added topics."""
    topics = "\n".join([f"{name}: {tid}" for name, tid in data["topics"].items()])
    await update.message.reply_text(f"Available topics:\n{topics if topics else 'No topics found.'}")

async def add_quiz(update: Update, context: CallbackContext):
    """Adds a quiz to a topic in the group."""
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
        await update.message.reply_text(f"Topic '{topic_name}' not found.")
        return

    topic_id = data["topics"][topic_name]
    await update.message.bot.send_poll(
        chat_id=data["group_id"],
        question=question,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index,
        message_thread_id=topic_id
    )
    await update.message.reply_text("Quiz added successfully!")

# Webhook endpoint
@my_app.route(f"/webhook", methods=["POST"])
def webhook():
    """Receives Telegram webhook updates and processes them"""
    update = Update.de_json(request.get_json(), app.bot)
    app.process_update(update)
    return "OK", 200

# Set up command handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setgroup", set_group))
app.add_handler(CommandHandler("addtopic", add_topic))
app.add_handler(CommandHandler("listtopics", list_topics))
app.add_handler(CommandHandler("addquiz", add_quiz))

# Start Flask server
if __name__ == "__main__":
    import asyncio
    from waitress import serve

    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.initialize())

    print("Bot is running on Render...")

    serve(my_app, host="0.0.0.0", port=5000)
