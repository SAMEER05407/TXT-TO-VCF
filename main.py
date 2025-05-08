import os
import re
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# === CONFIG ===
TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"
ADMIN_ID = 1485166650
ALLOWED_USERS_FILE = "allowed_users.txt"
logging.basicConfig(level=logging.INFO)

# === STATES ===
ASK_BASE_NAME, PROCESS_FILE = range(2)

# === UTILITIES ===
def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return set()

def save_allowed_users(users):
    with open(ALLOWED_USERS_FILE, "w") as f:
        f.write("\n".join(map(str, users)))

ALLOWED_USERS = load_allowed_users()
ALLOWED_USERS.add(ADMIN_ID)
save_allowed_users(ALLOWED_USERS)

def is_valid_number(line):
    return line.strip().isdigit() and len(line.strip()) >= 6

def txt_to_vcf(file_path, base_name):
    with open(file_path, "r") as f:
        lines = [line.strip() for line in f if is_valid_number(line)]

    output_files = []
    for idx, number in enumerate(lines, 1):
        filename = f"{base_name} {idx}.vcf"
        with open(filename, "w") as vcf:
            vcf.write(f"BEGIN:VCARD\nVERSION:3.0\nFN:{base_name} {idx}\nTEL;TYPE=CELL:{number}\nEND:VCARD")
        output_files.append(filename)
    return output_files

# === COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied! Contact admin.")
        return
    await update.message.reply_text(
        "👋 *Welcome to VCF Converter Bot!*\n\n"
        "📄 Send me a TXT file containing phone numbers, and I’ll convert them into VCF format.\n"
        "🔠 You’ll be asked for a base name for contacts.\n\n"
        "➕ Use /adduser <id> to grant access\n"
        "➖ Use /removeuser <id> to revoke access\n\n"
        "*Enjoy seamless VCF generation!*",
        parse_mode="Markdown"
    )

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Only the admin can add users.")
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.add(user_id)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"✅ User {user_id} added successfully.")
    except:
        await update.message.reply_text("⚠️ Usage: /adduser <user_id>")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Only the admin can remove users.")
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.discard(user_id)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"✅ User {user_id} removed successfully.")
    except:
        await update.message.reply_text("⚠️ Usage: /removeuser <user_id>")

# === CONVERSION LOGIC ===
async def handle_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        return await update.message.reply_text("⛔ Access Denied!")

    if not update.message.document or not update.message.document.file_name.endswith(".txt"):
        return await update.message.reply_text("⚠️ Please upload a valid TXT file.")

    file = await update.message.document.get_file()
    file_path = f"{user_id}_temp.txt"
    await file.download_to_drive(file_path)

    context.user_data["file_path"] = file_path
    await update.message.reply_text("🔤 Enter Base Name (e.g., Twitter X):")
    return ASK_BASE_NAME

async def ask_base_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    base_name = update.message.text.strip()
    file_path = context.user_data.get("file_path")

    if not base_name or not file_path:
        return await update.message.reply_text("❌ Error! Please start again.")

    await update.message.reply_text("⏳ Processing file...")
    try:
        vcf_files = txt_to_vcf(file_path, base_name)
        for vcf_file in vcf_files:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(vcf_file, "rb"))
            os.remove(vcf_file)
        os.remove(file_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Error processing file: {e}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === MAIN ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.FILE_EXTENSION("txt"), handle_txt)],
        states={ASK_BASE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_base_name)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(conv_handler)

    app.run_polling()
