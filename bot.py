from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import pandas as pd
import requests
import io
import os
import time

XLSX_URL = "https://drive.google.com/uc?export=download&id=1Pyuajead_Ng3D-j1QpQHOuKNk90TPvZ8"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # 5 minutos

def cargar_excel_drive(xlsx_url):
    ahora = time.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(xlsx_url)
            response.raise_for_status()
            cache["df"] = pd.read_excel(io.BytesIO(response.content), sheet_name="Resumen_Puentes")
            cache["df"]["Puente_normalizado"] = cache["df"]["Puente"].astype(str).str.strip().str.lower()
            cache["last_update"] = ahora
        except Exception as e:
            print(f"Error al cargar el XLSX: {e}")
            return pd.DataFrame()
    return cache["df"]

BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    print("Error: No se encontró la variable de entorno BOT_TOKEN")
    exit(1)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Puedes escribir:\n"
        "/avance {puente x}\n"
        "O también escribir: avance mina de yeso\n"
        "/puentes : para listar puentes disponibles"
    )

# /avance ...
async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        nombre_usuario = " ".join(context.args).strip().lower()

        df = cargar_excel_drive(XLSX_URL)
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

# Texto libre: "avance puente 10", "avance mina de yeso", etc.
async def mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto.startswith("avance"):
        nombre_usuario = texto.replace("avance", "").strip()

        df = cargar_excel_drive(XLSX_URL)
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

# /puentes
async def listar_puentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = cargar_excel_drive(XLSX_URL)
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
    app.add_handler(CommandHandler("puentes", listar_puentes))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))

    app.run_polling()
