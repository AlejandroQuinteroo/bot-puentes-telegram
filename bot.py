from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import pandas as pd
import requests
import io
import os
import time

# URL del CSV público exportado desde Google Sheets (Reemplaza con el tuyo)
CSV_PUBLICO_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-XXXXXXXX/pub?gid=951665795&single=true&output=csv"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # 5 minutos

def cargar_csv_publico(url_csv):
    ahora = time.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(url_csv)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.text))
            # Normaliza el nombre del puente para facilitar búsqueda
            df["Puente_normalizado"] = df["Puente"].astype(str).str.strip().str.lower()
            cache["df"] = df
            cache["last_update"] = ahora
        except Exception as e:
            print(f"Error al cargar CSV público: {e}")
            return pd.DataFrame()
    return cache["df"]

BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    print("Error: No se encontró la variable de entorno BOT_TOKEN")
    exit(1)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Puedes escribir:\n"
        "/avance {nombre del puente}\n"
        "O también escribir: avance san lazaro\n"
        "/puentes : para listar puentes disponibles"
    )

# Comando /avance {puente}
async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        nombre_usuario = " ".join(context.args).strip().lower()

        df = cargar_csv_publico(CSV_PUBLICO_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return

        fila = df[df["Puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["Puente"]
            avance = fila.iloc[0]["Avance"]
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")
    else:
        await update.message.reply_text("Usa: /avance nombre del puente")

# Maneja mensajes de texto libre tipo "avance puente 10", "avance mina de yeso", etc.
async def mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto.startswith("avance"):
        nombre_usuario = texto.replace("avance", "").strip()

        df = cargar_csv_publico(CSV_PUBLICO_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return

        fila = df[df["Puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["Puente"]
            avance = fila.iloc[0]["Avance"]
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")

# Comando /puentes para listar puentes disponibles
async def listar_puentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = cargar_csv_publico(CSV_PUBLICO_URL)
    if df.empty:
        await update.message.reply_text("Error al cargar los datos.")
        return
    puentes = sorted(df["Puente"].dropna().unique())
    texto = "Puentes disponibles:\n" + "\n".join(f"• {p}" for p in puentes)
    await update.message.reply_text(texto)

# Lanzamiento del bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(CommandHandler("puentes", listar_puentes))  # opcional
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))

    app.run_polling()
