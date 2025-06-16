
#from dotenv import load_dotenv
#import os

#load_dotenv()  # Esto carga las variables del archivo .env

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import pandas as pd
import requests
import io
import os

# URL pública CSV de tu Google Sheets
CSV_URL = "https://docs.google.com/spreadsheets/d/1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw/export?format=csv&id=1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw&gid=0"

# Función para cargar CSV desde Google Sheets
def cargar_csv_drive(csv_url):
    try:
        response = requests.get(csv_url)
        response.raise_for_status()
        return pd.read_csv(io.StringIO(response.content.decode('utf-8')))
    except Exception as e:
        print(f"Error al cargar el CSV: {e}")
        return pd.DataFrame()  # Retorna DataFrame vacío en caso de error

#BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Escribe: /avance puente X")

async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 2 and context.args[0].lower() == "puente":
        num_puente = context.args[1]
        nombre_puente = f"puente {num_puente}".lower()

        # Cargar hoja actualizada en cada consulta
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return

        if "Puente" in df.columns and "Avance (%)" in df.columns:
            fila = df[df["Puente"].str.lower() == nombre_puente]
            if not fila.empty:
                avance = fila.iloc[0]["Avance (%)"]
                await update.message.reply_text(f"El avance de {nombre_puente.title()} es {avance}%")
            else:
                await update.message.reply_text(f"No encontré información para {nombre_puente.title()}")
        else:
            await update.message.reply_text("Las columnas necesarias no están en el archivo.")
    else:
        await update.message.reply_text("Usa: /avance puente X")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.run_polling()
