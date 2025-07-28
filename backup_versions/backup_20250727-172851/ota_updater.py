import os
import shutil
import subprocess
import sys
import threading
import time
from notifier import send_notification, log_event  # ✅ Agregado log_event

VERSION_FILE = "version.txt"
BACKUP_FOLDER = "backup_versions"

def get_current_version():
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"

def get_remote_version():
    try:
        result = subprocess.run(["git", "ls-remote", "origin", "HEAD"], capture_output=True, text=True, check=True)
        subprocess.run(["git", "fetch"], check=True)
        result = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True, check=True)
        return result.stdout.strip()[:7]
    except subprocess.CalledProcessError:
        return get_current_version()

def backup_code():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    folder = os.path.join(BACKUP_FOLDER, f"backup_{timestamp}")
    os.makedirs(folder, exist_ok=True)
    for file in ["bot.py", "ebay_scraper.py", "notifier.py", "ota_updater.py", "version.txt"]:
        if os.path.exists(file):
            shutil.copy(file, os.path.join(folder, file))
    print("🗂️ Código actual respaldado.")

def restore_previous_version():
    folders = sorted(os.listdir(BACKUP_FOLDER), reverse=True)
    if folders:
        last_backup = os.path.join(BACKUP_FOLDER, folders[0])
        for file in os.listdir(last_backup):
            shutil.copy(os.path.join(last_backup, file), file)
        print("🔁 Restaurando versión anterior...")

def check_for_updates():
    current = get_current_version()
    remote = get_remote_version()

    if remote != current:
        print(f"🔄 Actualizando de versión {current} a {remote}")
        send_notification(f"🔄 Nueva versión detectada: {remote}. Iniciando actualización...")
        log_event("bot_update_detected", {
            "old_version": current,
            "new_version": remote
        })

        try:
            backup_code()
            subprocess.run(["git", "stash"], check=True)
            subprocess.run(["git", "pull"], check=True)

            with open("version.txt", "w") as f:
                f.write(remote)

            send_notification("✅ Actualización exitosa. Reiniciando bot...")
            log_event("bot_updated", {
                "status": "success",
                "old_version": current,
                "new_version": remote
            })

            os.execv(sys.executable, ['python'] + sys.argv)

        except subprocess.CalledProcessError as e:
            send_notification(f"❌ Error al buscar o aplicar actualizaciones: {e}")
            log_event("update_failed", {"error": str(e)})
            restore_previous_version()

def periodic_update_check(interval=300):
    thread = threading.Thread(target=lambda: loop_update_check(interval), daemon=True)
    thread.start()

def loop_update_check(interval):
    while True:
        try:
            check_for_updates()
        except Exception as e:
            send_notification(f"❌ Error durante la verificación OTA: {e}")
            log_event("ota_check_error", {"error": str(e)})
        time.sleep(interval)
