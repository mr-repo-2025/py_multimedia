import json
import logging
import datetime
from collections import defaultdict
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- Archivos y configuración ---
DATA_FILE = Path("ranking.json")
HISTORY_FILE = Path("ranking_history.json")
POINTS = defaultdict(int)
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8501657323:AAGP-qG3fqPMobffqlP9PsZgVx9zhZvc3N8"

# --- Funciones base de almacenamiento ---
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

def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception as e:
            logging.warning(f"No se pudo leer ranking_history.json: {e}")
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# --- Lógica quincenal ---
def get_current_period():
    """Determina el rango de fechas de la quincena actual."""
    today = datetime.date.today()
    first_day = today.replace(day=1)
    mid_month = first_day + datetime.timedelta(days=14)

    if today.day <= 14:
        period_start = first_day
        period_end = mid_month - datetime.timedelta(days=1)
    else:
        period_start = mid_month
        next_month = (first_day.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        period_end = next_month - datetime.timedelta(days=1)

    return period_start, period_end


def save_history_if_due():
    """Guarda histórico automáticamente cada quincena (dos veces al mes)."""
    today = datetime.date.today()
    history = load_history()

    if not POINTS:
        return  # No hay puntos aún

    period_start, period_end = get_current_period()

    # Evitar duplicar registros
    for h in history:
        if h["period_start"] == str(period_start) and h["period_end"] == str(period_end):
            return

    # Crear lista de ranking actual
    ranking_list = []
    for user_id, points in POINTS.items():
        ranking_list.append({
            "user_id": user_id,
            "name": str(user_id),  # Nombre se resolverá al mostrar
            "points": points
        })

    if ranking_list:
        history.append({
            "period_start": str(period_start),
            "period_end": str(period_end),
            "ranking": ranking_list
        })
        save_history(history)
        logging.info(f"Histórico guardado para {period_start} - {period_end}")

        # Reiniciar puntos después de guardar
        POINTS.clear()
        save_data()


# --- Manejadores del bot ---
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suma puntos cuando un usuario envía una foto."""
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
        f"📸 Gracias {name}! Se registró tu aporte.\n"
        f"Resolución: {w}x{h}\n"
        f"Has ganado +{puntos} puntos.\n"
        f"Total actual: {POINTS[user.id]} pts."
    )

    # Intentar guardar histórico si toca
    save_history_if_due()


async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el ranking actual con fechas."""
    if not POINTS:
        await update.message.reply_text("Aún no hay aportes registrados.")
        return

    period_start, period_end = get_current_period()
    sorted_points = sorted(POINTS.items(), key=lambda x: x[1], reverse=True)

    text = f"🏆 *Ranking actual*\n🗓 {period_start} → {period_end}\n\n"
    for i, (uid, pts) in enumerate(sorted_points, start=1):
        try:
            user = await context.bot.get_chat(uid)
            name = user.full_name
        except Exception:
            name = f"Usuario {uid}"
        text += f"{i}. {name} — {pts} pts\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el histórico quincenal."""
    history = load_history()

    if not history:
        await update.message.reply_text("No hay histórico registrado aún.")
        return

    text = "📅 *Histórico de quincenas*\n\n"

    for period in history:
        text += f"🗓 {period['period_start']} → {period['period_end']}\n"
        ranking = period.get("ranking", [])

        if not ranking:
            text += "  (Sin participantes)\n\n"
            continue

        ranking = sorted(ranking, key=lambda x: x["points"], reverse=True)
        for i, user in enumerate(ranking, start=1):
            name = user.get("name", f"Usuario {user['user_id']}")
            text += f"  {i}. {name} — {user['points']} pts\n"
        text += "\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola! Soy el bot monitor.\n"
        "Envía una foto para ganar puntos 📸\n"
        "Usa /ranking para ver el top actual 🏆\n"
        "Usa /history para ver los históricos quincenales 📅"
    )

# --- Inicio del bot ---
def main():
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
