
import os
import re
import tempfile
import time
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

from telegram import Update, InputFile
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler
)

# ===== CONFIGURATION =====
TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"  # Your bot token
ADMIN_ID = 1485166650                                   # Your admin ID
ALLOWED_USERS = {6827784861,8179320771,1485166650}

# Validate credentials
if not re.match(r'^\d+:[\w-]+$', TOKEN):
    raise ValueError("Invalid bot token! Get new one from @BotFather")
if not isinstance(ADMIN_ID, int) or ADMIN_ID < 1:
    raise ValueError("Invalid ADMIN_ID! Get your ID from @userinfobot")

# Conversation states
GET_BASE_NAME, GET_FILE_NAME, GET_CONTACTS_PER_FILE = range(3)

def send_typing(action, update, context):
    """Show typing/busy animation"""
    context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=action
    )
    time.sleep(0.5)

def extract_base_and_number(name):
    """Smart extraction for names like twitter11 → ('twitter', 11)"""
    match = re.search(r'^(.*?)(\d+)$', name)
    return (match.group(1), int(match.group(2))) if match else (name, 1)

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

def start(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        send_typing("typing", update, context)
        update.message.reply_text("⛔ Access Denied! Contact admin")
        return
    
    send_typing("typing", update, context)
    update.message.reply_text(
        "✨ *Ultimate TXT-to-VCF Converter* ✨\n\n"
        "📁 Send your TXT file to begin\n"
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
    
    # Store file
    context.user_data['temp_file'] = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    file.get_file().download(context.user_data['temp_file'].name)
    
    send_typing("typing", update, context)
    update.message.reply_text("🔤 Enter Base Name (e.g., twitter11):")
    return GET_BASE_NAME

def get_base_name(update: Update, context: CallbackContext):
    context.user_data['base_name'] = update.message.text
    send_typing("typing", update, context)
    update.message.reply_text("📝 Enter File Prefix (e.g., batch5):")
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

        # Initialize progress
        last_percent = -1
        msg = update.message.reply_text("⚙️ Processing... 0%")

        # Read numbers
        with open(context.user_data['temp_file'].name, 'r') as f:
            numbers = [re.sub(r'\D', '', line.strip()) for line in f if line.strip()]
        
        if not numbers:
            msg.edit_text("❌ No valid numbers found!")
            return ConversationHandler.END

        # Extract numbering
        base_prefix, start_num = extract_base_and_number(context.user_data['base_name'])
        file_prefix, file_start_num = extract_base_and_number(context.user_data['file_name'])

        # Process batches
        for i in range(0, len(numbers), contacts_per_file):
            batch = numbers[i:i + contacts_per_file]
            current_percent = min(100, int((i + len(batch)) / len(numbers) * 100))
            
            # Update progress only if changed
            if current_percent != last_percent:
                try:
                    msg.edit_text(f"⚙️ Processing... {current_percent}%")
                    last_percent = current_percent
                except:
                    pass

            # Generate VCF
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
                
                # Send file
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

def main():
    try:
        keep_alive()
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher

        # Error handler
        dp.add_error_handler(lambda u, c: None)

        # File processing flow
        file_conv = ConversationHandler(
            entry_points=[MessageHandler(Filters.document, handle_file)],
            states={
                GET_BASE_NAME: [MessageHandler(Filters.text, get_base_name)],
                GET_FILE_NAME: [MessageHandler(Filters.text, get_file_name)],
                GET_CONTACTS_PER_FILE: [MessageHandler(Filters.text, process_file)]
            },
            fallbacks=[]
        )
        dp.add_handler(file_conv)

        # Start command
        dp.add_handler(CommandHandler("start", start))
        
        print("🤖 Bot starting...")
        updater.start_polling(drop_pending_updates=True)
        print("✅ Bot is now running!")
        updater.idle()

    except Exception as e:
        print(f"❌ Failed to start: {str(e)}")
        print("Please check your configurations!")

if __name__ == '__main__':
    main()
