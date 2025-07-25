import logging
import pandas as pd
import requests
import io
import os
from datetime import datetime, time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)
import pytz

# -------- CONFIG --------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Falta definir el BOT_TOKEN en variables de entorno.")

CSV_URL = "https://docs.google.com/spreadsheets/d/1cscTPpqlYWp9qXYaG7ERN_iCKx2_Qg_ygJB-67GHGXs/export?format=csv&gid=0"

CACHE_DURATION = 20  # segundos
ZONA = pytz.timezone("America/Hermosillo")

cache = {"df": None, "last_update": 0}
chats_para_resumen = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------- CARGA DE CSV --------
def cargar_csv_drive(csv_url):
    import time as time_module
    ahora = time_module.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(csv_url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode("utf-8")))
            df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
            df["puente_normalizado"] = df["puente"].astype(str).str.strip().str.lower()
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            cache["df"] = df
            cache["last_update"] = ahora
            logger.info("CSV cargado y cache actualizado.")
        except Exception as e:
            logger.error(f"Error al cargar el CSV: {e}")
            return pd.DataFrame()
    return cache["df"]

def es_valor_vacio(val):
    return pd.isna(val) or str(val).strip() in ["", "0"]

# -------- COMANDOS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Puedes usar:\n"
        "/avance {puente}\n"
        "/puentes para listar puentes\n"
        "/resumen para ver pruebas pendientes\n"
        "/hoy para colados del día"
    )

async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        nombre_usuario = " ".join(context.args).strip().lower()
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return
        fila = df[df["puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["puente"]
            avance = fila.iloc[0].get("avance_(%)", "Sin dato")
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")
    else:
        await update.message.reply_text("Usa: /avance nombre del puente")

async def listar_puentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = cargar_csv_drive(CSV_URL)
    if df.empty:
        await update.message.reply_text("Error al cargar los datos.")
        return
    puentes = sorted(df["puente"].dropna().unique())
    texto = "Puentes disponibles:\n" + "\n".join(f"• {p}" for p in puentes)
    await update.message.reply_text(texto)

async def mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto.startswith("avance"):
        nombre_usuario = texto.replace("avance", "").strip()
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return
        fila = df[df["puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["puente"]
            avance = fila.iloc[0].get("avance_(%)", "Sin dato")
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")

# -------- RESUMEN --------
async def enviar_resumen_directo(context, chat_id):
    try:
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await context.bot.send_message(chat_id=chat_id, text="❌ No se pudo cargar el archivo.")
            return

        hoy = datetime.now(ZONA)
        encabezado = f"📋 *Resumen de pruebas de resistencia:* ({hoy.strftime('%d/%m/%Y %H:%M')})\n\n"

        bloques = []
        bloque_actual = ""

        for _, row in df.iterrows():
            puente = row.get("puente", "")
            apoyo = row.get("apoyo", "")
            num_elemento = row.get("no._elemento", "")
            elemento = row.get("elemento", "")
            fecha_colado = pd.to_datetime(row.get("fecha", ""), errors="coerce")

            if pd.isna(fecha_colado):
                continue

            dias = (hoy.date() - fecha_colado.date()).days
            fecha_colado_str = fecha_colado.strftime("%d/%m/%y")

            val7 = row.get("7_dias")
            val14 = row.get("14_dias")
            val28 = row.get("28_dias")

            recomendaciones = ""
            if dias >= 7 and es_valor_vacio(val7):
                recomendaciones += f"Pedir prueba de 7 días ({dias} días), "
            if dias >= 14 and es_valor_vacio(val14):
                recomendaciones += f"Pedir prueba de 14 días ({dias} días), "
            if dias >= 28 and es_valor_vacio(val28):
                recomendaciones += f"Pedir prueba de 28 días ({dias} días), "

            if not recomendaciones:
                continue

            linea = (
                f"🏗️ *{puente}* - Apoyo: {apoyo} - {elemento} {num_elemento}\n"
                f"🗒️ *Fecha colado:* {fecha_colado_str}\n"
                f"⏱ {recomendaciones.strip(', ')}\n\n"
            )

            if len(bloque_actual + linea) > 3500:
                bloques.append(bloque_actual)
                bloque_actual = ""

            bloque_actual += linea

        if bloque_actual.strip():
            bloques.append(bloque_actual)

        if not bloques:
            await context.bot.send_message(chat_id=chat_id, text="✅ No hay pruebas pendientes por solicitar.")
            return

        for i, bloque in enumerate(bloques):
            texto = encabezado + bloque if i == 0 else bloque
            await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en resumen: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error al generar el resumen:\n{e}")

async def comando_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chats_para_resumen.add(chat_id)
    await enviar_resumen_directo(context, chat_id)
    await update.message.reply_text("✅ Resumen enviado y programado para enviarse diario a las 7:55am en este chat.")

# -------- /hoy --------
async def colados_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = cargar_csv_drive(CSV_URL)
    if df.empty:
        await update.message.reply_text("Error al cargar los datos.")
        return
    hoy = datetime.now(ZONA).date()
    df["fecha"] = pd.to_datetime(df["fecha"], errors='coerce')
    hoy_df = df[df["fecha"].dt.date == hoy]
    if hoy_df.empty:
        await update.message.reply_text("Hoy no se ha registrado ningún colado.")
    else:
        mensajes = "\n".join(
            f"• {r['puente']} - {r['elemento']} {r['no._elemento']} (Apoyo {r['apoyo']})"
            for _, r in hoy_df.iterrows()
        )
        await update.message.reply_text(f"Colados hoy ({hoy.strftime('%d/%m/%Y')}):\n{mensajes}")

# -------- SCHEDULER --------
async def enviar_resumen_a_todos(context):
    for chat_id in chats_para_resumen:
        try:
            await enviar_resumen_directo(context, chat_id)
        except Exception as e:
            logger.error(f"Error enviando resumen a {chat_id}: {e}")

def programar_resumen_diario(app):
    hora_envio = time(hour=7, minute=55)
    app.job_queue.run_daily(enviar_resumen_a_todos, hora_envio, time_zone=ZONA, name="Resumen diario")

# -------- MAIN --------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(CommandHandler("puentes", listar_puentes))
    app.add_handler(CommandHandler("resumen", comando_resumen))
    app.add_handler(CommandHandler("hoy", colados_hoy))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))

    programar_resumen_diario(app)

    logger.info("✅ Bot iniciado.")
    app.run_polling()

if __name__ == "__main__":
    main()
