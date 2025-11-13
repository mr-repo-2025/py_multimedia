import json
import logging
from collections import defaultdict
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

DATA_FILE = Path("ranking.json")
POINTS = defaultdict(int)
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "AQUÍ_TU_TOKEN_DEL_BOT"

def load_data():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text())
            for user_id, points in data.items():
                POINTS[int(user_id)] = points
        except Exception as e:
            logging.warning(f"No se pudo leer ranking.json: {e}")

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(POINTS, f)

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.full_name
    photos = update.message.photo
    best = photos[-1]
    w, h = best.width, best.height

    puntos = 1
    if w >= 800 and h >= 800:
        puntos += 1

    POINTS[user.id] += puntos
    save_data()

    await update.message.reply_text(
        f"📸 Gracias {name}! Se registró tu aporte.\nResolución: {w}x{h}\nHas ganado +{puntos} puntos.\nTotal: {POINTS[user.id]} pts."
    )

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not POINTS:
        await update.message.reply_text("Aún no hay aportes registrados.")
        return

    sorted_points = sorted(POINTS.items(), key=lambda x: x[1], reverse=True)
    top = sorted_points[:10]
    text = "🏆 *Top aportes valiosos*\n\n"
    for i, (uid, pts) in enumerate(top, start=1):
        try:
            user = await context.bot.get_chat(uid)
            name = user.full_name
        except Exception:
            name = f"Usuario {uid}"
        text += f"{i}. {name} — {pts} pts\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola! Soy el bot  monitor .\n"
        "Envía una foto para ganar puntos o usa /ranking para ver el top."
    )

def main():
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
