from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import pandas as pd
import requests
import io
import os
import time

CSV_URL = "https://docs.google.com/spreadsheets/d/1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw/export?format=csv&id=1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw&gid=0"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # 5 minutos

def cargar_csv_drive(csv_url):
    ahora = time.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(csv_url)
            response.raise_for_status()
            cache["df"] = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            cache["last_update"] = ahora
        except Exception as e:
            print(f"Error al cargar el CSV: {e}")
            return pd.DataFrame()
    return cache["df"]

BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    print("Error: No se encontró la variable de entorno BOT_TOKEN")
    exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Escribe: /avance puente <nombre> o simplemente 'avance puente <nombre>'")

async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Validar que haya al menos dos argumentos y el primero sea "puente"
    if len(context.args) >= 2 and context.args[0].lower() == "puente":
        nombre_puente = " ".join(context.args[1:]).lower().strip()

        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return

        if "Puente" in df.columns and "Avance (%)" in df.columns:
            fila = df[df["Puente"].str.strip().str.lower() == nombre_puente]
            if not fila.empty:
                avance = round(float(fila.iloc[0]["Avance (%)"]), 2)
                await update.message.reply_text(f"El avance de {nombre_puente.title()} es {avance}%")
            else:
                await update.message.reply_text(f"No encontré información para {nombre_puente.title()}")
        else:
            await update.message.reply_text("Las columnas necesarias no están en el archivo.")
    else:
        await update.message.reply_text("Usa: /avance puente <nombre>")

async def mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto.startswith("avance puente "):
        nombre_puente = texto[len("avance puente "):].strip()

        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return

        if "Puente" in df.columns and "Avance (%)" in df.columns:
            fila = df[df["Puente"].str.strip().str.lower() == nombre_puente]
            if not fila.empty:
                avance = round(float(fila.iloc[0]["Avance (%)"]), 2)
                await update.message.reply_text(f"El avance de {nombre_puente.title()} es {avance}%")
            else:
                await update.message.reply_text(f"No encontré información para {nombre_puente.title()}")
        else:
            await update.message.reply_text("Las columnas necesarias no están en el archivo.")
    else:
        await update.message.reply_text("Usa: avance puente <nombre>")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))
    app.run_polling()
