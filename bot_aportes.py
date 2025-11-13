import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ---------------- CONFIG ----------------
DATA_FILE = Path("ranking.json")
HISTORY_FILE = Path("ranking_history.json")
POINTS = defaultdict(int)
BOT_TOKEN = "8501657323:AAGP-qG3fqPMobffqlP9PsZgVx9zhZvc3N8"

logging.basicConfig(level=logging.INFO)

# ---------------- UTILIDADES ----------------
def load_data():
    """Carga puntos y última fecha de actualización."""
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text())
            for user_id, points in data.get("points", {}).items():
                POINTS[int(user_id)] = points
            return data.get("last_reset")
        except Exception as e:
            logging.warning(f"No se pudo leer ranking.json: {e}")
    return None


def save_data(last_reset: str):
    """Guarda puntos y fecha del último reset."""
    with open(DATA_FILE, "w") as f:
        json.dump({"points": POINTS, "last_reset": last_reset}, f, indent=2)


def save_history():
    """Guarda los puntos actuales en un histórico y limpia los puntos."""
    now = datetime.now()
    period_label = now.strftime("%Y-%m-%d")

    history_data = []
    if HISTORY_FILE.exists():
        try:
            history_data = json.loads(HISTORY_FILE.read_text())
        except Exception as e:
            logging.warning(f"No se pudo leer ranking_history.json: {e}")

    # Añadimos registro actual
    history_data.append({
        "period": period_label,
        "points": dict(POINTS),
    })

    # Guardamos histórico
    with open(HISTORY_FILE, "w") as f:
        json.dump(history_data, f, indent=2)

    # Reiniciamos puntos
    POINTS.clear()
    save_data(last_reset=now.strftime("%Y-%m-%d"))
    logging.info(f"✅ Reset quincenal completado el {period_label}")


def check_biweekly_reset(last_reset_date):
    """Verifica si han pasado 2 semanas y hace el cierre si corresponde."""
    try:
        last_reset = datetime.strptime(last_reset_date, "%Y-%m-%d")
    except Exception:
        last_reset = datetime.now() - timedelta(days=15)  # fuerza reset inicial

    if datetime.now() - last_reset >= timedelta(days=14):
        save_history()


# ---------------- HANDLERS ----------------
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
    save_data(last_reset=datetime.now().strftime("%Y-%m-%d"))

    await update.message.reply_text(
        f"📸 Gracias {name}! Se registró tu aporte.\n"
        f"Resolución: {w}x{h}\n"
        f"Has ganado +{puntos} puntos.\n"
        f"Total: {POINTS[user.id]} pts."
    )


async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not POINTS:
        await update.message.reply_text("Aún no hay aportes registrados.")
        return

    sorted_points = sorted(POINTS.items(), key=lambda x: x[1], reverse=True)
    top = sorted_points[:10]
    text = "🏆 *Top aportes valiosos (actual quincena)*\n\n"
    for i, (uid, pts) in enumerate(top, start=1):
        try:
            user = await context.bot.get_chat(uid)
            name = user.full_name
        except Exception:
            name = f"Usuario {uid}"
        text += f"{i}. {name} — {pts} pts\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los últimos registros de histórico."""
    if not HISTORY_FILE.exists():
        await update.message.reply_text("No hay histórico registrado aún.")
        return

    try:
        history_data = json.loads(HISTORY_FILE.read_text())
    except Exception as e:
        await update.message.reply_text(f"Error al leer histórico: {e}")
        return

    text = "📅 *Histórico de quincenas*\n\n"
    for entry in history_data[-5:]:  # últimas 5 quincenas
        total = sum(entry["points"].values())
        text += f"🗓 {entry['period']} — Total acumulado: {total} pts\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola! Soy el *bot monitor*.\n\n"
        "📸 Envía una foto para ganar puntos.\n"
        "🏆 Usa /ranking para ver el top actual.\n"
        "🗓 Usa /history para ver el histórico quincenal."
    )


# ---------------- MAIN ----------------
def main():
    last_reset_date = load_data()
    check_biweekly_reset(last_reset_date)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))

    app.run_polling()


if __name__ == "__main__":
    main()
