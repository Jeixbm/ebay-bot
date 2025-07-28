import time
import threading
from ota_updater import periodic_update_check, check_for_updates
from ebay_scraper import monitor_laptops
from notifier import send_notification, log_event

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
