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

data = {"groups": [], "current_group": None}
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

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
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I don\'t know you!")
        return
    try:
        group_id = int(update.message.text.split()[-1])
        group_id = str(group_id)
    except ValueError:
        await update.message.reply_text("Usage: /setgroup <group_id>")
        return
    if group_id not in data["groups"]:
        data["groups"].append(group_id)
    if data.get(group_id) is None or data[group_id].get("topics") is None:
        data[group_id] = {"topics": {}}
    data["current_group"] = group_id
    save_data()
    await update.message.reply_text(f"Group set successfully: {group_id}!")


async def add_topic(update: Update, context: CallbackContext):
    """Manually adds a topic"""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I don\'t know you!")
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
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return
    current_group = data["current_group"]
    data[current_group]["topics"][topic_name] = topic_id
    save_data()
    with open(f"{current_group}_{topic_name}.json", 'w') as fp:
        json.dump([], fp)
        print(f"{topic_name}.json has been created!")
    await update.message.reply_text(f"Topic '{topic_name}' added successfully!")


async def list_topics(update: Update, context: CallbackContext):
    """Lists all manually added topics."""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return
    current_group = data["current_group"]
    topics = "\n".join([f"{name}: {tid}" for name, tid in data[current_group]["topics"].items()])
    await update.message.reply_text(f"Available topics:\n{topics if topics else 'No topics found.'}")

async def add_quiz(update: Update, context: CallbackContext):
    """Adds a quiz to a specific topic and stores it in a JSON file."""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
        return
    bot = context.bot
    if data["current_group"] is None:
        await update.message.reply_text("Set the current group first!!!")
        return
    current_group = data["current_group"]
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

    if topic_name not in data[current_group]["topics"]:
        await update.message.reply_text(f"Topic '{topic_name}' not found for {current_group}.")
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

    await update.message.reply_text(f"Quiz added to '{topic_name}' and stored successfully!")


async def bulk_add(update: Update, context: CallbackContext):
    """Handles JSON file upload and adds quizzes in bulk, storing them in separate topic files."""
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
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
    summary += "\n".join([f"{topic}: {count} added" for topic, count in added.items()])
    summary += f"\nFailed: {failed}"
    await update.message.reply_text(summary)


async def remove_topic(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I am a bot!")
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
        await update.message.reply_text(f"Topic '{topic_name}' removed from {current_group} successfully!")
    else:
        await update.message.reply_text(f"Topic '{topic_name}' not found in {current_group}.")


async def list_groups(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER:
        await update.message.reply_text("Do not chat with me, I don\'t know you!")
        return
    groups_list = "\n".join(data["groups"])
    text = f"Available Groups:: \n {groups_list}"
    await update.message.reply_text(text)


app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("removetopic", remove_topic))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setgroup", set_group))
app.add_handler(CommandHandler("addtopic", add_topic))
app.add_handler(CommandHandler("listtopics", list_topics))
app.add_handler(CommandHandler("addquiz", add_quiz))
app.add_handler(CommandHandler("listgroups", list_groups))
app.add_handler(MessageHandler(filters.Document.ALL, bulk_add))


if __name__ == "__main__":
    print("Bot is running...!")
    app.run_polling()
