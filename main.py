import os
import re
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"  # Replace with your bot token
ADMIN_ID = 1485166650
ALLOWED_USERS_FILE = "allowed_users.txt"

# Load and Save User Access
def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return set()

def save_allowed_users(users):
    with open(ALLOWED_USERS_FILE, "w") as f:
        f.write("\n".join(map(str, users)))

ALLOWED_USERS = load_allowed_users()

# States
ASKING_BASENAME, PROCESSING_FILE = range(2)

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied! Contact admin.")
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 *Welcome to the VCF Bot!*\n\n"
        "📤 Send a `.txt` file with numbers.\n"
        "📝 After that, enter a *base name* (e.g., Twitter Data).\n"
        "✅ The bot will generate `.vcf` files.\n\n"
        "_Only numbers will be processed._",
        parse_mode="Markdown"
    )
    return ASKING_BASENAME

# Handle Base Name
async def handle_basename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['basename'] = update.message.text.strip()
    await update.message.reply_text("📥 Now send me the `.txt` file with phone numbers.")
    return PROCESSING_FILE

# Process Uploaded TXT File
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied! Contact admin.")
        return ConversationHandler.END

    if not context.user_data.get("basename"):
        await update.message.reply_text("🔤 Enter Base Name (e.g., Twitter1):")
        return ASKING_BASENAME

    document = update.message.document
    if not document.file_name.endswith(".txt"):
        await update.message.reply_text("❌ Please send a `.txt` file.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ Processing file... Please wait.")
    file = await document.get_file()
    file_path = f"{user_id}_{document.file_name}"
    await file.download_to_drive(file_path)

    with open(file_path, "r") as f:
        lines = f.read().splitlines()

    valid_numbers = [re.sub(r"[^\d+]", "", line.strip()) for line in lines]
    valid_numbers = [num for num in valid_numbers if num and any(char.isdigit() for char in num)]

    vcf_count = 0
    base = context.user_data['basename']
    for i in range(0, len(valid_numbers), 5000):
        vcf_count += 1
        filename = f"{base} {vcf_count}.vcf"
        with open(filename, "w") as vcf:
            for number in valid_numbers[i:i + 5000]:
                vcf.write("BEGIN:VCARD\n")
                vcf.write("VERSION:3.0\n")
                vcf.write(f"N:;{number};;;\n")
                vcf.write(f"TEL;TYPE=CELL:{number}\n")
                vcf.write("END:VCARD\n")

        await update.message.reply_document(open(filename, "rb"))
        os.remove(filename)

    os.remove(file_path)
    await update.message.reply_text("✅ Done! All VCF files have been generated.")
    return ConversationHandler.END

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Admin: Add User
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.add(user_id)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"✅ User `{user_id}` added.", parse_mode="Markdown")
    except:
        await update.message.reply_text("⚠️ Usage: /adduser <user_id>")

# Admin: Remove User
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.discard(user_id)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"❌ User `{user_id}` removed.", parse_mode="Markdown")
    except:
        await update.message.reply_text("⚠️ Usage: /removeuser <user_id>")

# Run Bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASKING_BASENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_basename)],
            PROCESSING_FILE: [MessageHandler(filters.Document.ALL, handle_file)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))

    print("Bot is running...")
    app.run_polling()
