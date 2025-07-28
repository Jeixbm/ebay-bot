import time
import threading
from ota_updater import periodic_update_check, check_for_updates
from ebay_scraper import monitor_laptops
from notifier import send_notification, log_event
from telegram.ext import ApplicationBuilder, CommandHandler  # <--- CAMBIO AQUI
import config  # <--- Importa tus tokens

def version_command(update, context):
    try:
        with open('version.txt', 'r') as f:
            version = f.read().strip()
        update.message.reply_text(f'🤖 Versión actual del bot: {version}')
    except Exception as e:
        update.message.reply_text(f'No se pudo obtener la versión: {e}')

def telegram_bot_loop():
    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()  # <--- CAMBIO AQUI
    app.add_handler(CommandHandler("version", version_command))       # <--- CAMBIO AQUI
    app.run_polling()                                                 # <--- CAMBIO AQUI

def mostrar_uptime(start_time):
    while True:
        uptime = int(time.time() - start_time)
        mins, secs = divmod(uptime, 60)
        hrs, mins = divmod(mins, 60)
        print(f"\r🕒 Uptime: {hrs:02d}:{mins:02d}:{secs:02d}", end="")
        time.sleep(1)

def main():
    print("✅ Bot iniciado correctamente.")
    send_notification("✅ Bot iniciado correctamente.")
    log_event("bot_started", {"status": "ok", "source": "manual"})

    start_time = time.time()

    # Mostrar uptime en un hilo separado
    threading.Thread(target=mostrar_uptime, args=(start_time,), daemon=True).start()

    # Arranca el sistema de actualización OTA en segundo plano
    log_event("ota_check", {"status": "background_started"})
    periodic_update_check(interval=60)  # Revisa cada 60 segundos

    # Arranca el hilo de Telegram Bot
    threading.Thread(target=telegram_bot_loop, daemon=True).start()

    while True:
        try:
            monitor_laptops()
            time.sleep(300)  # Espera 5 minutos

        except Exception as e:
            msg = f"⚠️ Error en ejecución del bot: {e}"
            send_notification(msg)
            log_event("execution_error", {"error": str(e)})
            time.sleep(60)  # Espera 1 minuto antes de intentar otra vez

if __name__ == "__main__":
    check_for_updates()  # Verifica actualizaciones inmediatamente
    main()
