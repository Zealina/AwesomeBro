#!/usr/bin/env python3
"""Create MCQs on Telegram from JSON"""

import asyncio
from flask import Flask, Response, abort, make_response, request
import html
from http import HTTPStatus
import logging
import os
import json
import uvicorn
from asgiref.wsgi import WsgiToAsgi
from telegram import Poll, Update, MessageEntity, InputFile
from telegram.ext import (
        Application,
        CommandHandler,
        CallbackContext,
        MessageHandler,
        filters,
    )
from telegram.constants import ParseMode
from telegram.ext import Application
from dotenv import load_dotenv


# ========= LOGGING ==========
logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ========= CONFIG ===========
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL is not set!")

WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT"))
if not WEBHOOK_PORT:
    raise ValueError("WEBHOOK_PORT is not set!")

WEBHOOK_PATH = f"/{TOKEN}"
SSL_CONTEXT = None

DATA_FILE = "bot_data.json"

OWNER = os.getenv("OWNER_ID")
if not OWNER:
    raise ValueError("OWNER ID MUST BE SET")
try:
    OWNER = int(OWNER)
except Exception:
    raise ValueError("OWNER ID MUST BE A NUMBER")

data = {"groups": [], "current_group": None}
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)


# =========== HELPER FUNCTIONS ===========
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def verify_user(update: Update):
    if update.effective_user.id != OWNER:
        await update.message.reply_text("You are not the boss of me!")
        return False
    return True


# ============ HANDLERS ============
async def start(update: Update, context: CallbackContext):
    if await verify_user(update) is False:
        return
    message = (
        "*Welcome to AwesomeBro!*\n\n"
        "Here are the available commands:\n\n"
        "🔹 *Basic Commands:*\n"
        "  ➤ `/start` – Shows this help message.\n\n"
        "🔹 *Group & Topics:*\n"
        "  ➤ `/setgroup` – Select a group for adding questions.\n"
        "  > `/listgroups` - List all the groups that have been added\n"
        "     _Usage:_ `/setgroup @YourGroupName`\n"
        "  ➤ `/listtopics` – List all topics in the selected group.\n"
        "  ➤ `/addtopic` – Manually add a topic.\n"
        "     _Usage:_ `/addtopic Biology`\n"
        "  ➤ `/removetopic` – Remove a topic from the list.\n"
        "     _Usage:_ `/removetopic Biology`\n\n"
        "🔹 *Quiz Management:*\n"
        "  ➤ `/addquiz` – Add a single question to the bot.\n"
        "     _Usage:_ `/addquiz What is the capital of France?; Paris`\n"
    )
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def set_group(update: Update, context: CallbackContext):
    """Sets the group ID for the bot"""
    if await verify_user(update) is False:
        return

    group_id = update.message.text
    group_id = group_id.split()[-1]

    if group_id not in data["groups"]:
        data["groups"].append(group_id)
    if data.get(group_id) is None or data[group_id].get("topics") is None:
        data[group_id] = {"topics": {}}
    data["current_group"] = group_id
    save_data()
    await update.message.reply_text(f"Group set successfully: {group_id}!")


async def add_topic(update: Update, context: CallbackContext):
    """Manually adds a topic"""
    if await verify_user(update) is False:
        return
    parts = update.message.text.split(" ", 2)
    if len(parts) < 3:
        text = "Usage: /addtopic <topic_name> <topic_id>"
        await update.message.reply_text(text)
        return
    topic_name = parts[1].strip().lower()
    try:
        topic_id = int(parts[2].strip())
    except ValueError:
        await update.message.reply_text("Topic ID must be a number.")
        return
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return
    current_group = data["current_group"]
    data[current_group]["topics"][topic_name] = topic_id
    save_data()
    with open(f"{current_group}_{topic_name}.json", 'w') as fp:
        json.dump([], fp)
        print(f"{topic_name}.json has been created!")
    await update.message.reply_text(f"Topic '{topic_name}' added!")


async def list_topics(update: Update, context: CallbackContext):
    """Lists all manually added topics."""
    if await verify_user(update) is False:
        return
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return
    cg = data["current_group"]
    topics = [f"{name}: {tid}" for name, tid in data[cg]["topics"].items()]
    topics = "\n".join(topics)
    await update.message.reply_text(f"Topics:\n{topics if topics else 'None'}")


async def add_quiz(update: Update, context: CallbackContext):
    """Adds a quiz to a specific topic and stores it in a JSON file."""
    if await verify_user(update) is False:
        return
    bot = context.bot
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return
    current_group = data["current_group"]
    parts = update.message.text.split("|")

    if len(parts) < 4:
        text = "Usage: /addquiz topic | question | option1 | option2 \
        | ... | correct_option_index"
        await update.message.reply_text(text)
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

    if topic_name not in data[current_group]["topics"]:
        text = f"Topic '{topic_name}' not found for {current_group}."
        await update.message.reply_text(text)
        return

    topic_id = data[current_group]["topics"][topic_name]
    topic_file = f"{current_group}_{topic_name}.json"
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
        chat_id=int(current_group),
        question=question,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index,
        message_thread_id=topic_id
    )

    await update.message.reply_text(f"Quiz added to {topic_name}!")


async def bulk_add(update: Update, context: CallbackContext):
    """Handles JSON file upload and adds quizzes in bulk"""
    if await verify_user(update) is False:
        return
    if not update.message.document:
        await update.message.reply_text("Please upload a JSON file.")
        return
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return

    current_group = data["current_group"]
    file = await context.bot.get_file(update.message.document.file_id)
    file_path = f"{file.file_id}.json"
    await file.download_to_drive(file_path)

    try:
        with open(file_path, "r") as f:
            quizzes = json.load(f)
    except json.JSONDecodeError as e:
        os.remove(file_path)
        await update.message.reply_text(f"Invalid JSON file: {e}.")
        return

    os.remove(file_path)
    bot = context.bot
    added = {}
    failed = 0
    count = 0

    await update.message.reply_text("The file has been read successfully!")

    for quiz in quizzes:
        count += 1
        try:
            topic_name = quiz["topic"].strip().lower()
            question = quiz["question"].strip()
            options = quiz["options"]
            correct_index = int(quiz["correct_option"])

            if topic_name not in data[current_group]["topics"].keys():
                failed += 1
                continue

            topic_id = data[current_group]["topics"][topic_name]
            topic_file = f"{current_group}_{topic_name}.json"

            await bot.send_poll(
                chat_id=int(current_group),
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
    summary += "\n".join([f"{t}: {c} added" for t, c in added.items()])
    summary += f"\nFailed: {failed}"
    await update.message.reply_text(summary)


async def remove_topic(update: Update, context: CallbackContext):
    if await verify_user(update) is False:
        return
    """Removes a topic from the bot."""
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return

    current_group = data["current_group"]
    parts = update.message.text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("Usage: /removetopic <topic_name>")
        return
    topic_name = parts[1].strip().lower()
    if topic_name in data["topics"]:
        del data[current_group]["topics"][topic_name]
        save_data()
        await update.message.reply_text(f"Topic '{topic_name}' removed!")
    else:
        await update.message.reply_text(f"Topic '{topic_name}' not found!")


async def list_groups(update: Update, context: CallbackContext):
    if await verify_user(update) is False:
        return
    groups_list = "\n".join(data["groups"])
    text = f"Available Groups:: \n {groups_list}"
    await update.message.reply_text(text)


app = Application.builder().token(TOKEN).updater(None).build()
app.add_handler(CommandHandler("removetopic", remove_topic))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setgroup", set_group))
app.add_handler(CommandHandler("addtopic", add_topic))
app.add_handler(CommandHandler("listtopics", list_topics))
app.add_handler(CommandHandler("addquiz", add_quiz))
app.add_handler(CommandHandler("listgroups", list_groups))
app.add_handler(MessageHandler(filters.Document.ALL, bulk_add))


flask_app = Flask(__name__)


# ========== FLASK ROUTES ============
@flask_app.post("/telegram")
async def telegram():
    await app.update_queue.put(Update.de_json(data=request.json, bot=app.bot))
    return Response(status=HTTPStatus.OK)


@flask_app.get("/healthcheck")
async def healthcheck():
    return make_response("✅ Bot is alive and kicking", HTTPStatus.OK)


# =========== MAIN ==============
async def main():
    await app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/telegram",
            allowed_updates=Update.ALL_TYPES
        )
    server = uvicorn.Server(
            config=uvicorn.Config(app=WsgiToAsgi(flask_app),
                                  host="0.0.0.0", port=WEBHOOK_PORT)
        )

    async with app:
        await app.start()
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
