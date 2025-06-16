from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import pandas as pd
import requests
import io
import os

# Función para cargar CSV desde Google Sheets público
def cargar_csv_drive(csv_url):
    response = requests.get(csv_url)
    return pd.read_csv(io.StringIO(response.content.decode('utf-8')))

# URL pública CSV de tu Google Sheets (reemplaza con tu URL si cambias de hoja)
CSV_URL = "https://docs.google.com/spreadsheets/d/1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw/export?format=csv&id=1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw&gid=0"

# Carga el DataFrame
df_avances = cargar_csv_drive(CSV_URL)

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Escribe: /avance puente X")

async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    
    if "avance" in texto:
        partes = texto.split()
        if len(partes) >= 3:
            nombre_puente = f"puente {partes[2]}"
            fila = df_avances[df_avances["Puente"].str.lower() == nombre_puente]
            if not fila.empty:
                avance = fila.iloc[0]["Avance (%)"]
                await update.message.reply_text(f"El avance de {nombre_puente.title()} es {avance}%")
            else:
                await update.message.reply_text(f"No encontré información para {nombre_puente.title()}")
        else:
            await update.message.reply_text("Usa: /avance puente X")
    else:
        await update.message.reply_text("Comando no reconocido.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))
    app.run_polling()
