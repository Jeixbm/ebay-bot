import time
import threading
import asyncio
from ota_updater import periodic_update_check, check_for_updates
from ebay_scraper import monitor_laptops
from notifier import send_notification, log_event
from telegram.ext import Application, CommandHandler
import config

async def version_handler(update, context):
    try:
        with open('version.txt', 'r', encoding='utf-8') as f:
            version = f.read().strip()
        await update.message.reply_text(f'?? Versi車n actual del bot: {version}')
    except Exception as e:
        await update.message.reply_text(f'No se pudo obtener la versi車n: {e}')

def mostrar_uptime(start_time):
    while True:
        uptime = int(time.time() - start_time)
        mins, secs = divmod(uptime, 60)
        hrs, mins = divmod(mins, 60)
        print(f"\r?? Uptime: {hrs:02d}:{mins:02d}:{secs:02d}", end="")
        time.sleep(1)

def run_scraper():
    while True:
        try:
            monitor_laptops()
            time.sleep(300)
        except Exception as e:
            msg = f"?? Error en el hilo del scraper: {e}"
            # Usamos la nueva funci車n de ayuda para llamar a la corutina
            try:
                asyncio.run(send_notification(msg))
            except RuntimeError: # Si ya hay un loop corriendo
                 loop = asyncio.get_running_loop()
                 loop.create_task(send_notification(msg))
            log_event("execution_error", {"error": str(e)})
            time.sleep(60)

async def main():
    # --- LA LLAMADA AHORA EST芍 AQU赤 DENTRO ---
    check_for_updates()

    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("version", version_handler))

    start_time = time.time()
    threading.Thread(target=mostrar_uptime, args=(start_time,), daemon=True).start()
    threading.Thread(target=run_scraper, daemon=True).start()
    periodic_update_check(interval=60)

    print("? Bot iniciado correctamente. Presiona Ctrl+C para detenerlo.")
    # La notificaci車n de inicio se mueve aqu赤 para asegurar que el loop est芍 listo
    await send_notification("? Bot iniciado correctamente.")
    log_event("bot_started", {"status": "ok", "source": "manual"})

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())