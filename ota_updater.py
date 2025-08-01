import os
import shutil
import subprocess
import sys
import threading
import time
import stat
import asyncio # Importa asyncio
from notifier import send_notification, log_event

# --- NUEVA FUNCIÓN DE AYUDA ---
def run_async(coro):
    """Ejecuta una corutina desde un contexto síncrono."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si ya hay un bucle corriendo, crea una tarea
            task = loop.create_task(coro)
            # Espera a que la tarea se complete
            loop.run_until_complete(asyncio.sleep(0)) 
        else:
            # Si no hay bucle, corre hasta que se complete
            asyncio.run(coro)
    except RuntimeError:
        # Si get_event_loop falla, crea uno nuevo
        asyncio.run(coro)

VERSION_FILE = "version.txt"
BACKUP_FOLDER = "backup_versions"
TMP_FOLDER = "ota_update_tmp"
GITHUB_URL = "https://github.com/Jeixbm/ebay-bot.git"

def get_current_version():
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"

def get_remote_version():
    try:
        subprocess.run(["git", "fetch"], check=True, capture_output=True)
        result = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True, check=True)
        return result.stdout.strip()[:7]
    except subprocess.CalledProcessError:
        log_event("get_remote_version_failed", {})
        return get_current_version()

def backup_code():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    folder = os.path.join(BACKUP_FOLDER, f"backup_{timestamp}")
    os.makedirs(folder, exist_ok=True)
    files_to_backup = ["bot.py", "ebay_scraper.py", "notifier.py", "ota_updater.py", "version.txt", "config.py", "requirements.txt"]
    for file in files_to_backup:
        if os.path.exists(file):
            shutil.copy(file, os.path.join(folder, file))
    print("🗂️ Código actual respaldado.")
    log_event("backup_created", {"folder": folder})

def restore_previous_version():
    try:
        folders = sorted(os.listdir(BACKUP_FOLDER), reverse=True)
        if folders:
            last_backup = os.path.join(BACKUP_FOLDER, folders[0])
            for file in os.listdir(last_backup):
                shutil.copy(os.path.join(last_backup, file), file)
            print("🔁 Restaurando versión anterior...")
            log_event("version_restored", {"backup_folder": last_backup})
    except Exception as e:
        print(f"Error al restaurar: {e}")
        log_event("restore_failed", {"error": str(e)})

def test_new_version(tmp_folder):
    test_script = "test_update.py"
    test_script_path = os.path.join(tmp_folder, test_script)
    if not os.path.isfile(test_script_path):
        return False, "test_update.py no existe en la nueva versión."
    try:
        result = subprocess.run([sys.executable, test_script], cwd=tmp_folder, capture_output=True, timeout=45)
        stdout_decoded = result.stdout.decode('utf-8', errors='ignore')
        stderr_decoded = result.stderr.decode('utf-8', errors='ignore')
        if result.returncode != 0:
            return False, stderr_decoded + "\n" + stdout_decoded
        return True, None
    except Exception as e:
        return False, str(e)

def fetch_new_version_to_tmp():
    if os.path.exists(TMP_FOLDER):
        safe_delete_folder(TMP_FOLDER)
    os.makedirs(TMP_FOLDER, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", "--branch", "main", GITHUB_URL, TMP_FOLDER]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.returncode != 0:
        raise Exception(f"Error clonando repo: {result.stderr}")

def update_code_from_tmp(tmp_folder):
    files_to_copy = ["bot.py", "ebay_scraper.py", "notifier.py", "ota_updater.py", "version.txt", "config.py", "requirements.txt"]
    for file in files_to_copy:
        src_file = os.path.join(tmp_folder, file)
        if os.path.exists(src_file):
            shutil.copy(src_file, file)
    print("✅ Código actualizado desde la nueva versión probada.")

def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"[DEBUG OTA] Error quitando solo-lectura: {e}")

def safe_delete_folder(folder):
    try:
        shutil.rmtree(folder, onerror=remove_readonly)
    except Exception as e:
        print(f"[DEBUG OTA] No se pudo borrar {folder}: {e} (ignorando)")

def check_for_updates():
    current = get_current_version()
    remote = get_remote_version()
    if remote != current and remote != "0.0.0":
        print(f"🔄 Actualizando de versión {current} a {remote}")
        run_async(send_notification(f"🔄 Nueva versión detectada: {remote}. Probando actualización..."))
        log_event("bot_update_detected", {"old_version": current, "new_version": remote})
        try:
            backup_code()
            fetch_new_version_to_tmp()
            test_ok, test_error = test_new_version(TMP_FOLDER)
            if not test_ok:
                safe_delete_folder(TMP_FOLDER)
                msg = f"❌ Test de nueva versión {remote} falló. No se aplicó la actualización.\n\nError:\n{test_error}"
                run_async(send_notification(msg))
                log_event("update_failed", {"error": test_error})
                return
            update_code_from_tmp(TMP_FOLDER)
            safe_delete_folder(TMP_FOLDER)
            with open("version.txt", "w") as f:
                f.write(remote)
            run_async(send_notification("✅ Actualización exitosa. Reiniciando bot..."))
            log_event("bot_updated", {"status": "success", "old_version": current, "new_version": remote})
            os.execv(sys.executable, ['python'] + sys.argv)
        except Exception as e:
            run_async(send_notification(f"❌ Error crítico durante el proceso de actualización: {e}"))
            log_event("update_failed_critical", {"error": str(e)})
            restore_previous_version()

def periodic_update_check(interval=300):
    thread = threading.Thread(target=lambda: loop_update_check(interval), daemon=True)
    thread.start()

def loop_update_check(interval):
    while True:
        try:
            check_for_updates()
        except Exception as e:
            error_message = f"❌ Error irrecuperable en el bucle de verificación OTA: {e}"
            run_async(send_notification(error_message))
            log_event("ota_check_loop_error", {"error": str(e)})
        time.sleep(interval)