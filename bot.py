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

# -------- CONFIGURACIÓN --------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "AQUI_VA_TU_TOKEN_DEL_BOT"
CSV_URL = "https://docs.google.com/spreadsheets/d/1cscTPpqlYWp9qXYaG7ERN_iCKx2_Qg_ygJB-67GHGXs/export?format=csv&gid=0"

cache = {"df": None, "last_update": 0}
CACHE_DURATION = 300  # segundos

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
            cache["df"] = df
            cache["last_update"] = ahora
            logger.info("CSV cargado y cache actualizado.")
        except Exception as e:
            logger.error(f"Error al cargar el CSV: {e}")
            return pd.DataFrame()
    return cache["df"]

# -------- COMANDOS --------
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

        hoy = datetime.now()
        encabezado = f"📋 *Resumen de pruebas de resistencia:* ({hoy.strftime('%d/%m/%Y %H:%M')})\n\n"

        def tiene_resultado(valor):
            if valor is None:
                return False
            val_str = str(valor).strip().lower()
            return val_str not in ("", "0", "none", "nan")

        bloques = []
        bloque_actual = ""

        for _, row in df.iterrows():
            fecha_colado = pd.to_datetime(row.get("fecha", ""), errors='coerce')
            if pd.isna(fecha_colado):
                continue

            dias = (hoy - fecha_colado).days
            fecha_str = fecha_colado.strftime("%d/%m/%y")

            s7 = row.get("7_dias")
            s14 = row.get("14_dias")
            s28 = row.get("28_dias")

            # Verificar si alguna prueba ya tiene resultado
            alguna_prueba_registrada = any([tiene_resultado(s7), tiene_resultado(s14), tiene_resultado(s28)])

            if alguna_prueba_registrada:
                # Si alguna está registrada, no pedir pruebas pendientes
                continue

            pruebas_pendientes = []
            if s7 in (None, "", 0) and dias >= 7:
                pruebas_pendientes.append("7 días")
            if s14 in (None, "", 0) and dias >= 14:
                pruebas_pendientes.append("14 días")
            if s28 in (None, "", 0) and dias >= 28:
                pruebas_pendientes.append("28 días")

            if pruebas_pendientes:
                texto_pruebas = ", ".join(pruebas_pendientes)
                linea = (
                    f"🏗️ *{row.get('puente','')}* - Eje: {row.get('apoyo','')} - {row.get('elemento','')} {row.get('no._elemento','')}\n"
                    f"🗒️ *Fecha colado:* {fecha_str}\n"
                    f"🗒️ *{dias}* días desde colado\n"
                    f"⏱ Se pueden pedir pruebas de: {texto_pruebas}\n\n"
                )
            else:
                # Ninguna prueba pendiente, pero faltan días para 7 (porque ninguna prueba registrada)
                if dias < 7:
                    faltan = 7 - dias
                    linea = (
                        f"🏗️ *{row.get('puente','')}* - Eje: {row.get('apoyo','')} - {row.get('elemento','')} {row.get('no._elemento','')}\n"
                        f"🗒️ *Fecha colado:* {fecha_str}\n"
                        f"🗒️ *{dias}* días desde colado\n"
                        f"⏱ Faltan {faltan} días para poder pedir pruebas\n\n"
                    )
                else:
                    # No hay pruebas pendientes y tiempo mínimo cumplido, no mostrar nada
                    continue

            if len(bloque_actual + linea) > 3500:
                bloques.append(bloque_actual)
                bloque_actual = ""
            bloque_actual += linea

        if bloque_actual.strip():
            bloques.append(bloque_actual)

        if not bloques:
            await context.bot.send_message(chat_id=chat_id, text="✅ No hay pruebas pendientes.")
            return

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

# -------- INICIO --------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("avance", avance))
    app.add_handler(CommandHandler("puentes", listar_puentes))
    app.add_handler(CommandHandler("resumen", comando_resumen))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mensaje_texto))

    logger.info("Bot iniciado.")
    app.run_polling()

if __name__ == "__main__":
    main()
