# -*- coding: utf-8 -*-
import time
import threading
import asyncio
from ota_updater import periodic_update_check, check_for_updates
# ... resto de imports ...
from ebay_scraper import monitor_laptops
from notifier import send_notification, log_event
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config

async def version_handler(update, context):
    try:
        with open('version.txt', 'r') as f:
            version = f.read().strip()
        await update.message.reply_text(f'🤖 Versión actual del bot: {version}')
    except Exception as e:
        await update.message.reply_text(f'No se pudo obtener la versión: {e}')

def mostrar_uptime(start_time):
    while True:
        uptime = int(time.time() - start_time)
        mins, secs = divmod(uptime, 60)
        hrs, mins = divmod(mins, 60)
        print(f"\r🕒 Uptime: {hrs:02d}:{mins:02d}:{secs:02d}", end="")
        time.sleep(1)

def run_scraper():
    while True:
        try:
            monitor_laptops()
            time.sleep(300)
        except Exception as e:
            msg = f"⚠️ Error en ejecución del bot: {e}"
            send_notification(msg)
            log_event("execution_error", {"error": str(e)})
            time.sleep(60)

async def main_telegram():
    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("version", version_handler))

    print("✅ Bot iniciado correctamente.")
    send_notification("✅ Bot iniciado correctamente.")
    log_event("bot_started", {"status": "ok", "source": "manual"})

    start_time = time.time()
    threading.Thread(target=mostrar_uptime, args=(start_time,), daemon=True).start()
    log_event("ota_check", {"status": "background_started"})
    periodic_update_check(interval=60)
    threading.Thread(target=run_scraper, daemon=True).start()
    await app.run_polling()

if __name__ == "__main__":
    check_for_updates()  # Verifica actualizaciones inmediatamente
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si el loop ya está corriendo (notebooks, VSCode, Windows…)
            task = loop.create_task(main_telegram())
            loop.run_until_complete(task)
        else:
            loop.run_until_complete(main_telegram())
    except RuntimeError:
        # Si no existe loop, créalo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main_telegram())
