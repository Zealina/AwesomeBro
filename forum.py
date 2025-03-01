#!/usr/bin/env python3
"""Get forum topics"""

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext

TOKEN = "7939932702:AAHGO43zURpFteO21VZDrXzb-r7XVjo0D3U"
CHAT_ID = -1002384524300
TOPIC_IDS = set()

async def handle_new_topic(update: Update, context: CallbackContext):
    """Capture new topics from updates."""
    topic_id = update.message.message_thread_id
    topic_name = update.message.forum_topic_created.name
    if topic_id not in TOPIC_IDS:
        TOPIC_IDS.add(topic_id)
        print(f"New Topic: {topic_name} (ID: {topic_id})")

async def handle_message(update: Update, context: CallbackContext):
    """Capture topic IDs from regular messages in topics."""
    if update.message.message_thread_id:
        topic_id = update.message.message_thread_id
        if topic_id not in TOPIC_IDS:
            TOPIC_IDS.add(topic_id)
            print(f"Detected topic ID: {topic_id}")

app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.FORUM_TOPIC_CREATED, handle_new_topic))
app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_message))

print("Bot is running...")
app.run_polling()
