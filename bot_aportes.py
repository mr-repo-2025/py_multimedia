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
USERS = {}  # user_id -> name
BOT_TOKEN = "8501657323:AAGP-qG3fqPMobffqlP9PsZgVx9zhZvc3N8"

logging.basicConfig(level=logging.INFO)

# ---------------- UTILIDADES ----------------
def load_data():
    """Carga puntos, usuarios y fecha de último reset."""
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text())
            for user_id, points in data.get("points", {}).items():
                POINTS[int(user_id)] = points
            for user_id, name in data.get("users", {}).items():
                USERS[int(user_id)] = name
            return data.get("last_reset")
        except Exception as e:
            logging.warning(f"No se pudo leer ranking.json: {e}")
    return None


def save_data(last_reset: str):
    """Guarda puntos, usuarios y fecha del último reset."""
    with open(DATA_FILE, "w") as f:
        json.dump({
            "points": POINTS,
            "users": USERS,
            "last_reset": last_reset
        }, f, indent=2, ensure_ascii=False)


def save_history(last_reset_date):
    """Guarda los puntos actuales (con nombres y fechas) en un histórico y limpia los puntos."""
    now = datetime.now()
    period_start = datetime.strptime(last_reset_date, "%Y-%m-%d") if last_reset_date else now - timedelta(days=14)
    period_end = now
    label = f"{period_start.strftime('%Y-%m-%d')} → {period_end.strftime('%Y-%m-%d')}"

    history_data = []
    if HISTORY_FILE.exists():
        try:
            history_data = json.loads(HISTORY_FILE.read_text())
        except Exception as e:
            logging.warning(f"No se pudo leer ranking_history.json: {e}")

    # Construir ranking detallado
    ranking_periodo = []
    for uid, pts in POINTS.items():
        ranking_periodo.append({
            "user_id": uid,
            "name": USERS.get(uid, f"Usuario {uid}"),
            "points": pts
        })

    history_data.append({
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": period_end.strftime("%Y-%m-%d"),
        "ranking": ranking_periodo
    })

    # Guardamos histórico
    with open(HISTORY_FILE, "w") as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)

    # Reiniciamos puntos
    POINTS.clear()
    save_data(last_reset=period_end.strftime("%Y-%m-%d"))
    logging.info(f"✅ Reset quincenal completado: {label}")


def check_biweekly_reset(last_reset_date):
    """Verifica si han pasado 2 semanas y hace el cierre si corresponde."""
    try:
        last_reset = datetime.strptime(last_reset_date, "%Y-%m-%d")
    except Exception:
        last_reset = datetime.now() - timedelta(days=15)  # fuerza reset inicial

    if datetime.now() - last_reset >= timedelta(days=14):
        save_history(last_reset_date)


def get_current_period(last_reset_date):
    """Devuelve texto con el rango de fechas de la quincena actual."""
    try:
        start = datetime.strptime(last_reset_date, "%Y-%m-%d")
    except Exception:
        start = datetime.now() - timedelta(days=14)
    end = start + timedelta(days=14)
    return f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"


# ---------------- HANDLERS ----------------
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.full_name
    USERS[user.id] = name  # guardamos el nombre

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

    last_reset_date = load_data()
    period_text = get_current_period(last_reset_date)

    sorted_points = sorted(POINTS.items(), key=lambda x: x[1], reverse=True)
    top = sorted_points[:10]
    text = f"🏆 *Top aportes valiosos*\n📆 Periodo: {period_text}\n\n"
    for i, (uid, pts) in enumerate(top, start=1):
        name = USERS.get(uid, f"Usuario {uid}")
        text += f"{i}. {name} — {pts} pts\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los últimos registros de histórico (con nombres)."""
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
        period_label = f"{entry['period_start']} → {entry['period_end']}"
        text += f"🗓 *{period_label}*\n"
        sorted_ranking = sorted(entry["ranking"], key=lambda x: x["points"], reverse=True)
        for i, user in enumerate(sorted_ranking[:5], start=1):
            text += f"  {i}. {user['name']} — {user['points']} pts\n"
        text += "\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola! Soy el *bot monitor*.\n\n"
        "📸 Envía una foto para ganar puntos.\n"
        "🏆 Usa /ranking para ver el top actual (con fechas).\n"
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
