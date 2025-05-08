import os import re import tempfile import time from flask import Flask from threading import Thread from telegram import Update, InputFile from telegram.ext import ( Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler )

===== Flask for Keep Alive =====

app = Flask('')

@app.route('/') def home(): return "Bot is online!"

def run(): app.run(host='0.0.0.0', port=8080)

def keep_alive(): t = Thread(target=run) t.start()

===== Bot Configuration =====

TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg" ADMIN_ID = 1485166650 ALLOWED_USERS_FILE = "allowed_users.txt"

Load allowed users from file

def load_allowed_users(): if os.path.exists(ALLOWED_USERS_FILE): with open(ALLOWED_USERS_FILE, "r") as f: return set(map(int, f.read().splitlines())) return {ADMIN_ID}

Save allowed users to file

def save_allowed_users(users): with open(ALLOWED_USERS_FILE, "w") as f: f.write("\n".join(map(str, users)))

ALLOWED_USERS = load_allowed_users()

Conversation states

GET_BASE_NAME, GET_FILE_NAME, GET_CONTACTS_PER_FILE = range(3)

def is_allowed(user_id): return user_id in ALLOWED_USERS

def send_typing(action, update, context): context.bot.send_chat_action(chat_id=update.effective_chat.id, action=action) time.sleep(0.5)

def extract_base_and_number(name): match = re.search(r'^(.*?)(\d+)$', name) return (match.group(1), int(match.group(2))) if match else (name, 1)

def start(update: Update, context: CallbackContext): if not is_allowed(update.effective_user.id): update.message.reply_text("⛔ Access Denied! Contact admin") return update.message.reply_text("Welcome! Send your .txt file to begin conversion.")

def add_user(update: Update, context: CallbackContext): if update.effective_user.id != ADMIN_ID: return update.message.reply_text("⛔ Only admin can use this command.") try: new_id = int(context.args[0]) ALLOWED_USERS.add(new_id) save_allowed_users(ALLOWED_USERS) update.message.reply_text(f"✅ User {new_id} added!") except: update.message.reply_text("❌ Invalid user ID.")

def remove_user(update: Update, context: CallbackContext): if update.effective_user.id != ADMIN_ID: return update.message.reply_text("⛔ Only admin can use this command.") try: rem_id = int(context.args[0]) ALLOWED_USERS.discard(rem_id) save_allowed_users(ALLOWED_USERS) update.message.reply_text(f"✅ User {rem_id} removed!") except: update.message.reply_text("❌ Invalid user ID.")

def handle_file(update: Update, context: CallbackContext): if not is_allowed(update.effective_user.id): update.message.reply_text("⛔ Access Denied!") return

file = update.message.document
if not file.file_name.lower().endswith('.txt'):
    update.message.reply_text("❌ Only TXT files allowed!")
    return

context.user_data['temp_file'] = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
file.get_file().download(custom_path=context.user_data['temp_file'].name)
update.message.reply_text("Enter base name (e.g. twitter11):")
return GET_BASE_NAME

def get_base_name(update: Update, context: CallbackContext): context.user_data['base_name'] = update.message.text.strip() update.message.reply_text("Enter file name prefix (e.g. batch1):") return GET_FILE_NAME

def get_file_name(update: Update, context: CallbackContext): context.user_data['file_name'] = update.message.text.strip() update.message.reply_text("How many contacts per file?") return GET_CONTACTS_PER_FILE

def process_file(update: Update, context: CallbackContext): try: per_file = int(update.message.text) if per_file <= 0: raise ValueError

with open(context.user_data['temp_file'].name, 'r') as f:
        numbers = [re.sub(r'\D', '', line.strip()) for line in f if line.strip()]

    if not numbers:
        update.message.reply_text("❌ No valid numbers found.")
        return ConversationHandler.END

    base_prefix, base_start = extract_base_and_number(context.user_data['base_name'])
    file_prefix, file_start = extract_base_and_number(context.user_data['file_name'])

    for i in range(0, len(numbers), per_file):
        batch = numbers[i:i+per_file]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".vcf") as vcf:
            for j, num in enumerate(batch):
                name = f"{base_prefix}{base_start + i + j}"
                vcf.write(f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL:{num}\nEND:VCARD\n".encode())
            vcf.flush()

            with open(vcf.name, 'rb') as f:
                update.message.reply_document(
                    document=f,
                    filename=f"{file_prefix}{file_start + (i // per_file)}.vcf",
                    caption=f"{len(batch)} contacts saved."
                )
        os.unlink(vcf.name)

    update.message.reply_text("✅ All contacts converted!")
except Exception as e:
    update.message.reply_text(f"❌ Error processing file.")
finally:
    if 'temp_file' in context.user_data:
        os.unlink(context.user_data['temp_file'].name)
return ConversationHandler.END

def main(): keep_alive() updater = Updater(TOKEN, use_context=True) dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("adduser", add_user))
dp.add_handler(CommandHandler("removeuser", remove_user))

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document.mime_type("text/plain"), handle_file)],
    states={
        GET_BASE_NAME: [MessageHandler(Filters.text & ~Filters.command, get_base_name)],
        GET_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, get_file_name)],
        GET_CONTACTS_PER_FILE: [MessageHandler(Filters.text & ~Filters.command, process_file)]
    },
    fallbacks=[]
)

dp.add_handler(conv_handler)

updater.start_polling()
print("Bot is running...")
updater.idle()

if name == 'main': main()

