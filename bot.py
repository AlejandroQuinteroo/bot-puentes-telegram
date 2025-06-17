from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import pandas as pd
import requests
import io
import os
import time

# Configuración
CACHE_DURATION = 300  # segundos (5 minutos)
cache = {"df": None, "last_update": 0}

# Enlace de descarga directa XLSX en Google Drive (archivo público)
EXCEL_URL = "https://drive.google.com/uc?export=download&id=1Pyuajead_Ng3D-j1QpQHOuKNk90TPvZ8"
HOJA = "Resumen_Puentes"

def cargar_excel_drive():
    ahora = time.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(EXCEL_URL)
            response.raise_for_status()
            contenido = io.BytesIO(response.content)
            df = pd.read_excel(contenido, sheet_name=HOJA)
            df["Puente_normalizado"] = df["Puente"].astype(str).str.strip().str.lower()
            cache["df"] = df
            cache["last_update"] = ahora
        except Exception as e:
            print(f"Error al cargar el archivo Excel: {e}")
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
        "/avance {nombre del puente}\n"
        "Ejemplo: /avance puente 20\n\n"
        "También puedes escribir directamente:\n"
        "avance puente 20\n\n"
        "Comando /puentes para listar los puentes disponibles."
    )

# /avance {puente}
async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        nombre_usuario = " ".join(context.args).strip().lower()

        df = cargar_excel_drive()
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

# Texto libre (ej: "avance puente 10", "avance mina de yeso", etc.)
async def mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto.startswith("avance"):
        nombre_usuario = texto.replace("avance", "").strip()

        df = cargar_excel_drive()
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

# /puentes lista todos los puentes disponibles
async def listar_puentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = cargar_excel_drive()
    if df.empty:
        await update.message.reply_text("Error al cargar los datos.")
        return
    puentes = sorted(df["Puente"].dropna().unique())
    texto = "Puentes disponibles:\n" + "\n".join(f"• {p}" for p in puentes)
    await update.message.reply_text(texto)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(CommandHandler("puentes", listar_puentes))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))

    app.run_polling()
