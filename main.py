import os
import re
import tempfile
import time
from flask import Flask
from threading import Thread

from telegram import Update, InputFile
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler
)

app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===== CONFIGURATION =====
TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"  # Your bot token
ADMIN_ID = 1485166650                                   # Your admin ID
ALLOWED_USERS = {ADMIN_ID}

# Conversation states
GET_BASE_NAME, GET_FILE_NAME, GET_CONTACTS_PER_FILE, GET_NUMBERS = range(4)

# ==== Helpers ====
def send_typing(action, update, context):
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=action)
    time.sleep(0.5)

def extract_base_and_number(name):
    match = re.search(r'^(.*?)(\d+)$', name)
    return (match.group(1), int(match.group(2))) if match else (name, 1)

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

# ==== Handlers ====
def start(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        send_typing("typing", update, context)
        update.message.reply_text("⛔ Access Denied! Contact admin")
        return

    send_typing("typing", update, context)
    update.message.reply_text(
        "✨ *Ultimate TXT-to-VCF Converter* ✨\n\n"
        "📁 Send your TXT file to begin\n"
        "✍️ Or type /manual to enter numbers manually\n"
        "⚡ Auto numbering: C1→C2, twitter11→twitter12",
        parse_mode="Markdown"
    )

def handle_file(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        send_typing("typing", update, context)
        update.message.reply_text("🔒 Unauthorized!")
        return

    file = update.message.document
    if not file.file_name.lower().endswith('.txt'):
        send_typing("typing", update, context)
        update.message.reply_text("❌ Only TXT files accepted")
        return

    context.user_data['manual_numbers'] = []
    context.user_data['temp_file'] = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    file.get_file().download(context.user_data['temp_file'].name)

    send_typing("typing", update, context)
    update.message.reply_text("ENTER BASE NAME")
    return GET_BASE_NAME

def get_base_name(update: Update, context: CallbackContext):
    context.user_data['base_name'] = update.message.text
    send_typing("typing", update, context)
    update.message.reply_text("ENTER BASE FILE NAME")
    return GET_FILE_NAME

def get_file_name(update: Update, context: CallbackContext):
    context.user_data['file_name'] = update.message.text
    send_typing("typing", update, context)
    update.message.reply_text("🔢 Contacts per File (e.g., 50):")
    return GET_CONTACTS_PER_FILE

def process_file(update: Update, context: CallbackContext):
    try:
        contacts_per_file = int(update.message.text)
        if contacts_per_file <= 0:
            raise ValueError

        last_percent = -1
        msg = update.message.reply_text("⚙️ Processing... 0%")

        if context.user_data.get('manual_numbers'):
            numbers = context.user_data['manual_numbers']
        else:
            with open(context.user_data['temp_file'].name, 'r') as f:
                numbers = [re.sub(r'\D', '', line.strip()) for line in f if line.strip()]

        if not numbers:
            msg.edit_text("❌ No valid numbers found!")
            return ConversationHandler.END

        base_prefix, start_num = extract_base_and_number(context.user_data['base_name'])
        file_prefix, file_start_num = extract_base_and_number(context.user_data['file_name'])

        for i in range(0, len(numbers), contacts_per_file):
            batch = numbers[i:i + contacts_per_file]
            current_percent = min(100, int((i + len(batch)) / len(numbers) * 100))
            if current_percent != last_percent:
                try:
                    msg.edit_text(f"⚙️ Processing... {current_percent}%")
                    last_percent = current_percent
                except:
                    pass

            with tempfile.NamedTemporaryFile(delete=False, suffix='.vcf') as vcf_file:
                for j, num in enumerate(batch):
                    contact_num = start_num + i + j
                    vcf_file.write(
                        f"BEGIN:VCARD\n"
                        f"VERSION:3.0\n"
                        f"FN:{base_prefix}{contact_num}\n"
                        f"TEL:{num}\n"
                        f"END:VCARD\n".encode()
                    )
                vcf_file.flush()

                with open(vcf_file.name, 'rb') as f:
                    update.message.reply_document(
                        document=f,
                        filename=f"{file_prefix}{file_start_num + (i//contacts_per_file)}.vcf",
                        caption=f"✅ {len(batch)} contacts ({base_prefix}{start_num + i}-{base_prefix}{start_num + i + len(batch) - 1})"
                    )
            os.unlink(vcf_file.name)

        msg.edit_text(f"🎉 Converted {len(numbers)} contacts!")

    except ValueError:
        update.message.reply_text("❌ Enter valid number > 0!")
        return GET_CONTACTS_PER_FILE
    except Exception as e:
        update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        if 'temp_file' in context.user_data:
            os.unlink(context.user_data['temp_file'].name)
    return ConversationHandler.END

def manual(update: Update, context: CallbackContext):
    context.user_data['manual_numbers'] = []
    update.message.reply_text("✍️ Send numbers one by one. Type /done when finished.")
    return GET_NUMBERS

def collect_numbers(update: Update, context: CallbackContext):
    number = re.sub(r'\D', '', update.message.text)
    if number:
        context.user_data['manual_numbers'].append(number)
    return GET_NUMBERS

def done(update: Update, context: CallbackContext):
    if not context.user_data.get('manual_numbers'):
        update.message.reply_text("❌ No numbers added!")
        return ConversationHandler.END

    update.message.reply_text("ENTER BASE NAME")
    return GET_BASE_NAME

def add_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.add(user_id)
        update.message.reply_text(f"✅ User {user_id} added")
    except:
        update.message.reply_text("❌ Invalid usage")

def remove_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.discard(user_id)
        update.message.reply_text(f"✅ User {user_id} removed")
    except:
        update.message.reply_text("❌ Invalid usage")

def main():
    keep_alive()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    file_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.document, handle_file)],
        states={
            GET_BASE_NAME: [MessageHandler(Filters.text, get_base_name)],
            GET_FILE_NAME: [MessageHandler(Filters.text, get_file_name)],
            GET_CONTACTS_PER_FILE: [MessageHandler(Filters.text, process_file)]
        },
        fallbacks=[]
    )

    manual_conv = ConversationHandler(
        entry_points=[CommandHandler("manual", manual)],
        states={
            GET_NUMBERS: [MessageHandler(Filters.text & ~Filters.command, collect_numbers)],
            GET_BASE_NAME: [MessageHandler(Filters.text, get_base_name)],
            GET_FILE_NAME: [MessageHandler(Filters.text, get_file_name)],
            GET_CONTACTS_PER_FILE: [MessageHandler(Filters.text, process_file)]
        },
        fallbacks=[CommandHandler("done", done)]
    )

    dp.add_handler(file_conv)
    dp.add_handler(manual_conv)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("adduser", add_user))
    dp.add_handler(CommandHandler("removeuser", remove_user))

    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()
