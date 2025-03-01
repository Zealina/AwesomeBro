#!/usr/bin/env python3
"""Automate stuff questions"""

import os
import json
from telegram import Bot, Poll, Update, MessageEntity, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters

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
        "/setgroup - Selects the group to add the questions\n"
        "/listtopics - Lists all available topics in the group\n"
        "/addtopic - Manually add a topic\n"
        "/addquiz - Add a single question to the bot\n"
        "/bulkadd - Upload a JSON file with multiple questions\n"
        "/removetopic - Removes a topic from the list\n"
        "/clearresponses - Resets the active quizzes"
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
        await update.message.reply_text(f"Topic '{topic_name}' not found.")
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

async def bulk_add(update: Update, context: CallbackContext):
    """Handles JSON file upload and adds quizzes in bulk."""
    if not update.message.document:
        await update.message.reply_text("Please upload a JSON file.")
        return
    file = await context.bot.get_file(update.message.document.file_id)
    file_path = f"{file.file_id}.json"
    await file.download_to_drive(file_path)
    try:
        with open(file_path, "r") as f:
            quizzes = json.load(f)
    except json.JSONDecodeError:
        await update.message.reply_text("Invalid JSON file.")
        return
    os.remove(file_path)
    
    bot = context.bot
    added = {}
    failed = 0
    
    for quiz in quizzes:
        try:
            topic_name = quiz["topic"].strip().lower()
            question = quiz["question"].strip()
            options = quiz["options"]
            correct_index = int(quiz["correct_option"])
            
            if topic_name not in data["topics"]:
                failed += 1
                continue
            
            topic_id = data["topics"][topic_name]
            await bot.send_poll(
                chat_id=data["group_id"],
                question=question,
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_index,
                message_thread_id=topic_id
            )
            added[topic_name] = added.get(topic_name, 0) + 1
        except Exception:
            failed += 1
    
    summary = "Bulk upload summary:\n"
    summary += "\n".join([f"{topic}: {count} added" for topic, count in added.items()])
    summary += f"\nFailed: {failed}"
    await update.message.reply_text(summary)

async def remove_topic(update: Update, context: CallbackContext):
    """Removes a topic from the bot."""
    parts = update.message.text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("Usage: /removetopic <topic_name>")
        return
    topic_name = parts[1].strip().lower()
    if topic_name in data["topics"]:
        del data["topics"][topic_name]
        save_data()
        await update.message.reply_text(f"Topic '{topic_name}' removed successfully!")
    else:
        await update.message.reply_text(f"Topic '{topic_name}' not found.")

async def clear_responses(update: Update, context: CallbackContext):
    """Clears responses by stopping active quizzes."""
    bot = context.bot
    try:
        chat_id = data["group_id"]
        if not chat_id:
            await update.message.reply_text("Group ID is not set. Use /setgroup first.")
            return
        async for message in bot.get_chat_history(chat_id, limit=50):
            if message.poll:
                await bot.stop_poll(chat_id, message.message_id)
        await update.message.reply_text("All active quiz responses have been reset!")
    except Exception as e:
        await update.message.reply_text(f"Error resetting responses: {str(e)}")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("removetopic", remove_topic))
app.add_handler(CommandHandler("clearresponses", clear_responses))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setgroup", set_group))
app.add_handler(CommandHandler("addtopic", add_topic))
app.add_handler(CommandHandler("listtopics", list_topics))
app.add_handler(CommandHandler("addquiz", add_quiz))
app.add_handler(MessageHandler(filters.Document.ALL, bulk_add))

if __name__ == "__main__":
    print("Bot is running...")
    app.run_polling()
