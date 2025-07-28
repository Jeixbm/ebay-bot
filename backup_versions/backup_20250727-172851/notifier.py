import datetime
import os
import json
import requests
from config import TELEGRAM_TOKEN, CHAT_ID

# Enviar notificación a Telegram
def send_notification(message: str):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, data=data)
            if response.status_code != 200:
                print(f"❌ Error al enviar a Telegram: {response.text}")
                log_event("telegram_error", {"message": message, "response": response.text})
        except Exception as e:
            print(f"❌ Excepción al enviar a Telegram: {e}")
            log_event("telegram_exception", {"message": message, "exception": str(e)})
    else:
        print("⚠️ Faltan TELEGRAM_TOKEN o CHAT_ID.")
        log_event("telegram_credentials_missing", {})

    # Siempre loguear, incluso si falla
    log_event("manual_notification", {"message": message})

# Guardar logs en archivo
def log_event(event_type: str, data: dict):
    os.makedirs("logs", exist_ok=True)
    log_path = "logs/activity_log.txt"

    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "type": event_type,
        "data": data
    }

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"⚠️ Error al guardar en el log: {e}")
