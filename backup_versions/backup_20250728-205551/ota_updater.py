import os
import shutil
import subprocess
import sys
import threading
import time
import stat
from notifier import send_notification, log_event

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
        # Use short commit hash for versioning
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
    """
    Ejecuta test_update.py en la versión descargada temporal.
    Si falla, retorna False y el error. Si pasa, retorna True y None.
    """
    test_script = "test_update.py"
    test_script_path = os.path.join(tmp_folder, test_script)
    print(f"[DEBUG OTA] Intentando correr {test_script} en {tmp_folder}")
    if not os.path.isfile(test_script_path):
        print(f"[DEBUG OTA] No existe {test_script_path}")
        return False, "test_update.py no existe en la nueva versión."

    try:
        print(f"[DEBUG OTA] Ejecutando: {sys.executable} {test_script} (cwd={tmp_folder})")
        result = subprocess.run([sys.executable, test_script], cwd=tmp_folder, capture_output=True, timeout=45)
        
        # --- LÍNEAS CORREGIDAS ---
        stdout_decoded = result.stdout.decode('utf-8', errors='ignore')
        stderr_decoded = result.stderr.decode('utf-8', errors='ignore')
        # --- FIN DE LÍNEAS CORREGIDAS ---

        print(f"[DEBUG OTA] returncode={result.returncode}")
        print(f"[DEBUG OTA] stdout:\n{stdout_decoded}")
        print(f"[DEBUG OTA] stderr:\n{stderr_decoded}")

        if result.returncode != 0:
            error_msg = stderr_decoded + "\n" + stdout_decoded
            return False, error_msg
        return True, None
    except Exception as e:
        print(f"[DEBUG OTA] Exception: {str(e)}")
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
    """
    Copia los archivos actualizados del tmp_folder al directorio principal
    """
    files_to_copy = ["bot.py", "ebay_scraper.py", "notifier.py", "ota_updater.py", "version.txt", "config.py", "requirements.txt"]
    for file in files_to_copy:
        src_file = os.path.join(tmp_folder, file)
        if os.path.exists(src_file):
            shutil.copy(src_file, file)
    print("✅ Código actualizado desde la nueva versión probada.")

# --- FUNCIONES DE BORRADO ROBUSTAS ---
def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"[DEBUG OTA] Error quitando solo-lectura: {e}")

def safe_delete_folder(folder):
    try:
        shutil.rmtree(folder, onerror=remove_readonly)
        print(f"[DEBUG OTA] Borrada carpeta temporal {folder}")
    except Exception as e:
        print(f"[DEBUG OTA] No se pudo borrar {folder}: {e} (ignorando)")

# --- MAIN OTA LOGIC ---
def check_for_updates():
    current = get_current_version()
    remote = get_remote_version()

    if remote != current:
        print(f"🔄 Actualizando de versión {current} a {remote}")
        send_notification(f"🔄 Nueva versión detectada: {remote}. Probando actualización...")
        log_event("bot_update_detected", {
            "old_version": current,
            "new_version": remote
        })

        try:
            backup_code()
            fetch_new_version_to_tmp()
            test_ok, test_error = test_new_version(TMP_FOLDER)

            if not test_ok:
                safe_delete_folder(TMP_FOLDER)
                msg = f"❌ Test de nueva versión {remote} falló. No se aplicó la actualización.\n\nError:\n{test_error}"
                send_notification(msg)
                log_event("update_failed", {"error": test_error})
                print(msg)
                # No se restaura el backup aquí para no entrar en bucles si el backup también falla
                return

            update_code_from_tmp(TMP_FOLDER)
            safe_delete_folder(TMP_FOLDER)

            with open("version.txt", "w") as f:
                f.write(remote)

            send_notification("✅ Actualización exitosa. Reiniciando bot...")
            log_event("bot_updated", {
                "status": "success",
                "old_version": current,
                "new_version": remote
            })

            os.execv(sys.executable, ['python'] + sys.argv)

        except Exception as e:
            send_notification(f"❌ Error crítico durante el proceso de actualización: {e}")
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
            send_notification(error_message)
            log_event("ota_check_loop_error", {"error": str(e)})
        time.sleep(interval)