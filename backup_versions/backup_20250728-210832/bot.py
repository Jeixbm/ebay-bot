# -*- coding: utf-8 -*-
import time
import threading
import asyncio
from ota_updater import periodic_update_check, check_for_updates
from ebay_scraper import monitor_laptops
from notifier import send_notification, log_event
from telegram.ext import Application, CommandHandler

# Se importa el módulo de configuración para acceder a las variables
import config

async def version_handler(update, context):
    """Manejador del comando /version. Responde con el hash de la versión actual."""
    try:
        with open('version.txt', 'r', encoding='utf-8') as f:
            version = f.read().strip()
        await update.message.reply_text(f'🤖 Versión actual del bot: {version}')
    except Exception as e:
        await update.message.reply_text(f'No se pudo obtener la versión: {e}')

def mostrar_uptime(start_time):
    """Muestra el tiempo de actividad del bot en la consola."""
    while True:
        uptime = int(time.time() - start_time)
        mins, secs = divmod(uptime, 60)
        hrs, mins = divmod(mins, 60)
        print(f"\r🕒 Uptime: {hrs:02d}:{mins:02d}:{secs:02d}", end="")
        time.sleep(1)

def run_scraper():
    """Bucle principal para la ejecución del scraper en un hilo separado."""
    while True:
        try:
            monitor_laptops()
            time.sleep(300)  # Espera 5 minutos entre cada ciclo
        except Exception as e:
            msg = f"⚠️ Error en el hilo del scraper: {e}"
            send_notification(msg)
            log_event("execution_error", {"error": str(e)})
            time.sleep(60)

async def main():
    """Función principal que configura y ejecuta el bot."""
    # 1. Ejecuta una comprobación de actualización al iniciar
    check_for_updates()

    # 2. Construye la aplicación del bot
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # 3. Añade los manejadores de comandos
    app.add_handler(CommandHandler("version", version_handler))

    # 4. Inicia los hilos de fondo (daemon)
    start_time = time.time()
    threading.Thread(target=mostrar_uptime, args=(start_time,), daemon=True).start()
    threading.Thread(target=run_scraper, daemon=True).start()
    periodic_update_check(interval=60)  # Este ya corre en un hilo

    # 5. Notifica el inicio y arranca el bot
    print("✅ Bot iniciado correctamente. Presiona Ctrl+C para detenerlo.")
    await send_notification("✅ Bot iniciado correctamente.")
    log_event("bot_started", {"status": "ok", "source": "manual"})

    # run_polling se encarga de todo el ciclo de vida y del cierre con Ctrl+C
    await app.run_polling()

if __name__ == "__main__":
    # Esta es la forma moderna y correcta de iniciar una aplicación asyncio.
    # Se encarga del bucle de eventos y del cierre limpio automáticamente.
    asyncio.run(main())