import logging
import pandas as pd
import requests
import io
import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# --- CONFIGURACIÓN ---
BOT_TOKEN = os.getenv("BOT_TOKEN") or "AQUI_VA_TU_TOKEN_DEL_BOT"
CSV_URL = "https://docs.google.com/spreadsheets/d/1cscTPpqlYWp9qXYaG7ERN_iCKx2_Qg_ygJB-67GHGXs/export?format=csv&gid=0"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # Segundos

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- VARIABLE GLOBAL PARA CHATS REGISTRADOS ---
chats_registrados = set()

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
            cache["df"] = df
            cache["last_update"] = ahora
            logger.info("CSV cargado y cache actualizado.")
        except Exception as e:
            logger.error(f"Error al cargar el CSV: {e}")
            return pd.DataFrame()
    return cache["df"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chats_registrados.add(chat_id)
    await update.message.reply_text(
        "¡Hola! Bot activado y chat registrado para resúmenes diarios.\n"
        "Usa:\n"
        "/avance {puente}\n"
        "/puentes\n"
        "/resumen"
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
            avance = fila.iloc[0].get("avance_(%)", "No disponible")
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")
    else:
        await update.message.reply_text("Usa: /avance nombre_del_puente")

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
            avance = fila.iloc[0].get("avance_(%)", "No disponible")
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")

async def enviar_resumen_directo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await context.bot.send_message(chat_id=chat_id, text="❌ No se pudo cargar el archivo.")
            return

        hoy = datetime.now()
        bloques = []
        bloque_actual = ""

        for _, row in df.iterrows():
            try:
                fecha_colado = pd.to_datetime(row.get("fecha", ""))
                dias = (hoy - fecha_colado).days
                fecha_str = fecha_colado.strftime("%d/%m/%y")
            except:
                continue

            s7 = row.get("7_dias", "")
            s14 = row.get("14_dias", "")
            s28 = row.get("28_dias", "")

            if s7 == 0 and s14 == 0 and s28 == 0:
                continue

            pendientes = []
            if (s7 == "" or pd.isna(s7)) and dias >= 7:
                pendientes.append("7 días")
            if (s14 == "" or pd.isna(s14)) and dias >= 14:
                pendientes.append("14 días")
            if (s28 == "" or pd.isna(s28)) and dias >= 28:
                pendientes.append("28 días")

            if pendientes:
                linea = (
                    f"🏗️ *{row.get('puente','')}* - Eje: {row.get('apoyo','')} - {row.get('elemento','')} {row.get('no._elemento','')}\n"
                    f"🗒️ *Fecha colado:* {fecha_str}\n"
                    f"🗒️ *{dias}* días desde colado\n"
                    f"⏱ Se pueden pedir a: {', '.join(pendientes)}\n\n"
                )
                if len(bloque_actual + linea) > 3500:
                    bloques.append(bloque_actual)
                    bloque_actual = ""
                bloque_actual += linea

        if bloque_actual.strip():
            bloques.append(bloque_actual)

        if not bloques:
            await context.bot.send_message(chat_id=chat_id, text="✅ No hay pruebas pendientes.")
            return

        encabezado = f"📋 *Resumen de pruebas de resistencia:* ({hoy.strftime('%d/%m/%Y %H:%M')})\n\n"
        for i, bloque in enumerate(bloques):
            texto = encabezado + bloque if i == 0 else bloque
            await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en resumen: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error al generar el resumen:\n{e}")

async def comando_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await enviar_resumen_directo(context, chat_id)
    await update.message.reply_text("✅ Resumen enviado correctamente.")

def resumen_diario_job(app):
    if not chats_registrados:
        logger.warning("No hay chats registrados para enviar el resumen diario.")
        return
    for chat_id in chats_registrados:
        asyncio.create_task(enviar_resumen_directo(app.bot, chat_id))

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(CommandHandler("puentes", listar_puentes))
    app.add_handler(CommandHandler("resumen", comando_resumen))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))

    scheduler = AsyncIOScheduler(timezone="America/Mexico_City")
    scheduler.add_job(lambda: resumen_diario_job(app), CronTrigger(hour=7, minute=0))
    scheduler.start()

    logger.info("Bot iniciado y programador activo.")
    app.run_polling()

if __name__ == "__main__":
    main()
