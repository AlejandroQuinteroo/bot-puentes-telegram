import logging
import pandas as pd
import requests
import io
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# ------------------ CONFIGURACIÓN ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "AQUI_VA_TU_TOKEN_DEL_BOT"
CSV_URL = (
    "https://docs.google.com/spreadsheets/d/1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw/"
    "export?format=csv&id=1s1C0MpybJ7h32N1aPBo0bPlWqwiezlEkFE2q8-OcRIw&gid=0"
)

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # segundos

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cargar_csv_drive(csv_url):
    import time as time_module
    ahora = time_module.time()
    if cache["df"] is None or ahora - cache["last_update"] > CACHE_DURATION:
        try:
            response = requests.get(csv_url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode("utf-8")))

            # Normalizar columnas: minúsculas, sin espacios
            df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

            # Normalizar nombre puente para búsquedas
            df["puente_normalizado"] = df["puente"].astype(str).str.strip().str.lower()

            cache["df"] = df
            cache["last_update"] = ahora
            logger.info("CSV cargado y cache actualizado.")
        except Exception as e:
            logger.error(f"Error al cargar el CSV: {e}")
            return pd.DataFrame()
    return cache["df"]

async def enviar_resumen_directo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        df = cargar_csv_drive(CSV_URL)
        if df.empty:
            await context.bot.send_message(chat_id=chat_id, text="Error al cargar los datos.")
            return

        hoy = datetime.now()
        fecha_str = hoy.strftime("%d/%m/%Y %H:%M")
        encabezado = f"📋 *Resumen de pruebas de resistencia:* ({fecha_str})\n\n"
        bloques = []
        bloque_actual = ""

        for _, row in df.iterrows():
            puente = row.get("puente", "")
            apoyo = row.get("apoyo", "")
            num_elemento = row.get("no._elemento", "")
            elemento = row.get("elemento", "")
            fecha_colado_raw = row.get("fecha", "")

            try:
                fecha_colado = pd.to_datetime(fecha_colado_raw)
            except Exception:
                continue

            dias = (hoy - fecha_colado).days

            s7 = row.get("7_dias", "")
            s14 = row.get("14_dias", "")
            s28 = row.get("28_dias", "")

            # Equivalente a: if s7 === 0 && s14 === 0 && s28 === 0
            if s7 == 0 and s14 == 0 and s28 == 0:
                continue

            pendientes = []

            # Detectar vacíos "" o nulos None como pendientes, y días cumplidos
            if (s7 == "" or pd.isna(s7)) and dias >= 7:
                pendientes.append("7 días")

            if (s14 == "" or pd.isna(s14)) and dias >= 14:
                pendientes.append("14 días")

            if (s28 == "" or pd.isna(s28)) and dias >= 28:
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
            await context.bot.send_message(chat_id=chat_id, text="✅ No hay pendientes en las pruebas.")
            return

        for i, bloque in enumerate(bloques):
            mensaje = encabezado + bloque if i == 0 else bloque
            await context.bot.send_message(chat_id=chat_id, text=mensaje, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al generar resumen: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"Error al generar resumen: {e}")
