#!/usr/bin/env python3
"""Create MCQs and Organize Quizzes"""
import asyncio
import os
import json
from telegram import Bot, Poll, Update, MessageEntity, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
from telegram.constants import ParseMode


TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")


DATA_FILE = "bot_data.json"

OWNER = os.getenv("OWNER_ID")
if not OWNER:
    raise ValueError("OWNER ID MUST BE SET")
try:
    OWNER = int(OWNER)
except:
    raise ValueError("OWNER ID MUST BE A NUMBER")

data = {"group_id": None, "topics": {}}
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


async def start(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
    message = (
        "*Welcome to AwesomeBro!*\n\n"
        "Here are the available commands:\n\n"
        "🔹 *Basic Commands:*\n"
        "  ➤ `/start` – Shows this help message.\n\n"
        "🔹 *Group & Topics:*\n"
        "  ➤ `/setgroup` – Select a group for adding questions.\n"
        "     _Usage:_ `/setgroup @YourGroupName`\n"
        "  ➤ `/listtopics` – List all topics in the selected group.\n"
        "  ➤ `/addtopic` – Manually add a topic.\n"
        "     _Usage:_ `/addtopic Biology`\n"
        "  ➤ `/removetopic` – Remove a topic from the list.\n"
        "     _Usage:_ `/removetopic Biology`\n\n"
        "🔹 *Quiz Management:*\n"
        "  ➤ `/addquiz` – Add a single question to the bot.\n"
        "     _Usage:_ `/addquiz What is the capital of France?; Paris`\n"
        "  ➤ `/clearresponses` – Reset active quizzes."
    )
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def set_group(update: Update, context: CallbackContext):
    """Sets the group ID for the bot"""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
    try:
        group_id = int(update.message.text.split()[-1])
    except ValueError:
        await update.message.reply_text("Usage: /setgroup <group_id>")
        return
    data["group_id"] = group_id
    save_data()
    await update.message.reply_text(f"Group set successfully: {group_id}!")


async def add_topic(update: Update, context: CallbackContext):
    """Manually adds a topic"""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
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
    with open(f"{topic_name}.json", 'w') as fp:
        json.dump(fp, [])
        print(f"{topic_name}.json has been created!")
    await update.message.reply_text(f"Topic '{topic_name}' added successfully!")


async def list_topics(update: Update, context: CallbackContext):
    """Lists all manually added topics."""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
    topics = "\n".join([f"{name}: {tid}" for name, tid in data["topics"].items()])
    await update.message.reply_text(f"Available topics:\n{topics if topics else 'No topics found.'}")

async def add_quiz(update: Update, context: CallbackContext):
    """Adds a quiz to a specific topic and stores it in a JSON file."""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
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
    topic_file = f"{topic_name}.json"
    quiz_entry = {
        "question": question,
        "options": options,
        "correct_option": correct_index
    }

    if os.path.exists(topic_file):
        with open(topic_file, "r") as f:
            quizzes = json.load(f)
    else:
        quizzes = []

    quizzes.append(quiz_entry)
    with open(topic_file, "w") as f:
        json.dump(quizzes, f, indent=4)

    await bot.send_poll(
        chat_id=data["group_id"],
        question=question,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index,
        message_thread_id=topic_id
    )

    await update.message.reply_text(f"Quiz added to '{topic_name}' and stored successfully!")


async def bulk_add(update: Update, context: CallbackContext):
    """Handles JSON file upload and adds quizzes in bulk, storing them in separate topic files."""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
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
    count = 0

    for quiz in quizzes:
        count += 1
        try:
            topic_name = quiz["topic"].strip().lower()
            question = quiz["question"].strip()
            options = quiz["options"]
            correct_index = int(quiz["correct_option"])

            if topic_name not in data["topics"]:
                failed += 1
                continue

            topic_id = data["topics"][topic_name]
            topic_file = f"{topic_name}.json"
            
            if os.path.exists(topic_file):
                with open(topic_file, "r") as f:
                    topic_quizzes = json.load(f)
            else:
                topic_quizzes = []

            topic_quizzes.append({
                "question": question,
                "options": options,
                "correct_option": correct_index
            })

            with open(topic_file, "w") as f:
                json.dump(topic_quizzes, f, indent=4)

            await bot.send_poll(
                chat_id=data["group_id"],
                question=question,
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_index,
                message_thread_id=topic_id
            )

            added[topic_name] = added.get(topic_name, 0) + 1
            await asyncio.sleep(5.1)
        except Exception as e:
            print(f"{count}. {e}")
            failed += 1

    summary = "Bulk upload summary:\n"
    summary += "\n".join([f"{topic}: {count} added" for topic, count in added.items()])
    summary += f"\nFailed: {failed}"
    await update.message.reply_text(summary)


async def remove_topic(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
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
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
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
    print("Bot is running...!")
    app.run_polling()
