from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

import pandas as pd
import gspread
import os
import time
import json

from google.oauth2.service_account import Credentials

# ================== Configuración de credenciales ==================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Cargar las credenciales desde la variable de entorno GOOGLE_CREDENTIALS
google_creds = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = Credentials.from_service_account_info(google_creds, scopes=scope)
client = gspread.authorize(creds)

# Nombre de la hoja
HOJA = "Resumen_Puentes"
SPREADSHEET_ID = "1Pyuajead_Ng3D-j1QpQHOuKNk90TPvZ8"

# Rango exacto donde está la tabla
RANGO = "Resumen_Puentes!B5:W29"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # segundos

def cargar_datos():
    ahora = time.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            # Abrir la hoja y obtener el rango de datos
            sheet = client.open_by_key(SPREADSHEET_ID)
            values = sheet.values_get(RANGO)["values"]

            # Crear DataFrame
            encabezados = values[0]
            datos = values[1:]
            df = pd.DataFrame(datos, columns=encabezados)

            # Asegurar que los nombres de columna estén limpios
            df.columns = [c.strip() for c in df.columns]

            # Normalizar nombre de puente
            if "Puente" not in df.columns:
                raise ValueError("No se encontró la columna 'Puente'")
            df["Puente_normalizado"] = df["Puente"].str.strip().str.lower()

            cache["df"] = df
            cache["last_update"] = ahora
        except Exception as e:
            print(f"Error al cargar datos de Google Sheets: {e}")
            return pd.DataFrame()
    return cache["df"]

BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    print("Error: BOT_TOKEN no está definido en variables de entorno")
    exit(1)

# ================== Comandos de Telegram ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Puedes escribir:\n"
        "/avance nombre del puente\n"
        "Ejemplo: /avance puente 10\n"
        "También puedes escribir: avance puente 10\n"
        "/puentes : lista de puentes disponibles"
    )

async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        nombre_usuario = " ".join(context.args).strip().lower()
        df = cargar_datos()
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return
        fila = df[df["Puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["Puente"]
            avance = fila.iloc[0].get("Avance", "¿Sin dato?")
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")
    else:
        await update.message.reply_text("Usa: /avance nombre del puente")

async def mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto.startswith("avance"):
        nombre_usuario = texto.replace("avance", "").strip()
        df = cargar_datos()
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return
        fila = df[df["Puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["Puente"]
            avance = fila.iloc[0].get("Avance", "¿Sin dato?")
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")

async def listar_puentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = cargar_datos()
    if df.empty:
        await update.message.reply_text("Error al cargar los datos.")
        return
    puentes = sorted(df["Puente"].dropna().unique())
    texto = "Puentes disponibles:\n" + "\n".join(f"• {p}" for p in puentes)
    await update.message.reply_text(texto)

# ================== Lanzar el bot ==================

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(CommandHandler("puentes", listar_puentes))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))
    app.run_polling()
