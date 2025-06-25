import asyncio
import logging
import pandas as pd
import requests
import io
import os
import time
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ------------------ CONFIGURACIÓN ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "AQUI_VA_TU_TOKEN_DEL_BOT"
CHAT_ID_DESTINO = 5218342474660  # reemplaza con tu ID de usuario o grupo
CSV_URL = "https://docs.google.com/spreadsheets/d/1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw/export?format=csv&id=1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw&gid=0"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # segundos

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ FUNCIONES ------------------
def cargar_csv_drive(csv_url):
    ahora = time.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(csv_url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            df["Puente_normalizado"] = df["Puente"].astype(str).str.strip().str.lower()
            cache["df"] = df
            cache["last_update"] = ahora
            logger.info("CSV cargado y cache actualizado.")
        except Exception as e:
            logger.error(f"Error al cargar el CSV: {e}")
            return pd.DataFrame()
    return cache["df"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Puedes usar:\n"
        "/avance {puente}\n"
        "/puentes para listar puentes\n"
        "/resumen para ver pruebas pendientes"
    )

async def avance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        nombre_usuario = " ".join(context.args).strip().lower()
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await update.message.reply_text("Error al cargar los datos.")
            return
        fila = df[df["Puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["Puente"]
            avance = fila.iloc[0]["Avance (%)"]
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
    puentes = sorted(df["Puente"].dropna().unique())
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
        fila = df[df["Puente_normalizado"] == nombre_usuario]
        if not fila.empty:
            nombre_real = fila.iloc[0]["Puente"]
            avance = fila.iloc[0]["Avance (%)"]
            await update.message.reply_text(f"El avance de {nombre_real} es {avance}")
        else:
            await update.message.reply_text(f"No encontré información para '{nombre_usuario.title()}'")

# ------------------ RESUMEN AUTOMÁTICO ------------------
async def enviar_resumen_directo():
    try:
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await bot.send_message(chat_id=CHAT_ID_DESTINO, text="Error al cargar los datos.")
            return

        hoy = datetime.now()
        fecha_str = hoy.strftime("%d/%m/%Y %H:%M")
        encabezado = f"📋 *Resumen de pruebas de resistencia:* ({fecha_str})\n\n"
        bloques = []
        bloque_actual = ""

        for _, row in df.iterrows():
            puente = row.get("Puente", "")
            apoyo = row.get("Apoyo", "")
            num_elemento = row.get("#Elemento", "")
            elemento = row.get("Elemento", "")
            fecha_colado_raw = row.get("Fecha colado", "")
            try:
                fecha_colado = pd.to_datetime(fecha_colado_raw)
            except Exception:
                continue
            dias = (hoy - fecha_colado).days
            s7 = row.get("S7", 0)
            s14 = row.get("S14", 0)
            s28 = row.get("S28", 0)
            if s7 == 0 and s14 == 0 and s28 == 0:
                continue
            pendientes = []
            if pd.isna(s7) and dias >= 7:
                pendientes.append("7 días")
            if pd.isna(s14) and dias >= 14:
                pendientes.append("14 días")
            if pd.isna(s28) and dias >= 28:
                pendientes.append("28 días")
            if pendientes:
                linea = (
                    f"🏗️ *{puente}* - Eje: {apoyo} - {elemento} {num_elemento}\n"
                    f"🗒️ *Fecha colado:* {fecha_colado.strftime('%d/%m/%y')}\n"
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
            await bot.send_message(chat_id=CHAT_ID_DESTINO, text="✅ No hay pendientes en las pruebas.")
            return

        for i, bloque in enumerate(bloques):
            mensaje = encabezado + bloque if i == 0 else bloque
            await bot.send_message(chat_id=CHAT_ID_DESTINO, text=mensaje, parse_mode="Markdown")
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error al generar resumen: {e}")
        await bot.send_message(chat_id=CHAT_ID_DESTINO, text=f"Error al generar resumen: {e}")

# ------------------ HANDLER PARA /resumen ------------------
async def comando_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await enviar_resumen_directo()
        await update.message.reply_text("✅ Resumen enviado correctamente.")
    except Exception as e:
        logger.error(f"Error en /resumen: {e}")
        await update.message.reply_text(f"❌ Error al enviar el resumen: {e}")

# ------------------ EJECUCIÓN DIARIA ------------------
async def resumen_diario_job():
    await enviar_resumen_directo()

# ------------------ FUNCIÓN PRINCIPAL ------------------
async def main():
    global bot
    bot = Bot(token=BOT_TOKEN)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(CommandHandler("puentes", listar_puentes))
    app.add_handler(CommandHandler("resumen", comando_resumen))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))

    scheduler = AsyncIOScheduler(timezone="America/Mexico_City")
    scheduler.add_job(resumen_diario_job, CronTrigger(hour=7, minute=0))
    scheduler.start()

    logger.info("Bot iniciado y scheduler activo.")
    await app.run_polling()

# ------------------ ARRANQUE ------------------
if __name__ == "__main__":
    asyncio.run(main())
