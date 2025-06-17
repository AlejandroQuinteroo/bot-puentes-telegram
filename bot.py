from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import pandas as pd
import requests
import io
import os
import time

# URL pública para descargar el archivo Excel (xlsx)
EXCEL_URL = "https://docs.google.com/spreadsheets/d/1Pyuajead_Ng3D-j1QpQHOuKNk90TPvZ8/export?format=xlsx&id=1Pyuajead_Ng3D-j1QpQHOuKNk90TPvZ8&gid=951665795"
HOJA = "Resumen_Puentes"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # segundos (5 minutos)

def cargar_excel_drive():
    ahora = time.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(EXCEL_URL)
            response.raise_for_status()
            contenido = io.BytesIO(response.content)
            # Cargamos solo el rango B5:W29 con encabezados en la primera fila de ese rango
            df = pd.read_excel(
                contenido,
                sheet_name=HOJA,
                header=0,        # encabezado en la primera fila del rango (B5)
                usecols="B:W",
                skiprows=4,      # saltar primeras 4 filas, para que la fila 5 sea encabezado
                nrows=25         # filas desde la fila 5 a la 29 (29-5+1 = 25)
            )
            # Imprimir para debug (puedes comentar esta línea luego)
            print("Columnas del Excel:", df.columns.tolist())

            # Normalizar nombre de puente para comparación
            if "Puente" not in df.columns:
                raise ValueError("No se encontró la columna 'Puente' en la tabla")
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
        "¡Hola!² Puedes escribir:\n/avance {nombre del puente}\nEjemplo: /avance puente 10\nTambién puedes escribir en texto libre:\navance puente 10\n /puentes : para listar puentes disponibles"
    )

# /avance ...
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

# Texto libre: "avance puente 10", "avance mina de yeso", etc.
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

# /puentes para listar disponibles
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
