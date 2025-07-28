import time
import threading
from ota_updater import periodic_update_check, check_for_updates
from ebay_scraper import monitor_laptops
from notifier import send_notification, log_event
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config  # <--- Importa tus tokens

def version_command(update, context):
    try:
        with open('version.txt', 'r') as f:
            version = f.read().strip()
        # En PTB 20+, reply_text debe ser await
        return update.message.reply_text(f'🤖 Versión actual del bot: {version}')
    except Exception as e:
        return update.message.reply_text(f'No se pudo obtener la versión: {e}')

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
            time.sleep(300)  # Espera 5 minutos
        except Exception as e:
            msg = f"⚠️ Error en ejecución del bot: {e}"
            send_notification(msg)
            log_event("execution_error", {"error": str(e)})
            time.sleep(60)  # Espera 1 minuto antes de intentar otra vez

async def version_handler(update, context):
    try:
        with open('version.txt', 'r') as f:
            version = f.read().strip()
        await update.message.reply_text(f'🤖 Versión actual del bot: {version}')
    except Exception as e:
        await update.message.reply_text(f'No se pudo obtener la versión: {e}')

async def main_telegram():
    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("version", version_handler))

    print("✅ Bot iniciado correctamente.")
    send_notification("✅ Bot iniciado correctamente.")
    log_event("bot_started", {"status": "ok", "source": "manual"})

    start_time = time.time()
    # Hilo uptime
    threading.Thread(target=mostrar_uptime, args=(start_time,), daemon=True).start()
    # Hilo OTA
    log_event("ota_check", {"status": "background_started"})
    periodic_update_check(interval=60)
    # Hilo scraper
    threading.Thread(target=run_scraper, daemon=True).start()
    # Telegram bot principal
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    check_for_updates()  # Verifica actualizaciones inmediatamente
    asyncio.run(main_telegram())
