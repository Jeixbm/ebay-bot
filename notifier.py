import datetime
import os
import json
import asyncio
import aiohttp  # Se usa aiohttp en lugar de requests
from config import TELEGRAM_TOKEN, CHAT_ID

# Guardar logs en archivo
def log_event(event_type: str, data: dict):
    """Guarda un evento en el archivo de logs. Esta es una función síncrona."""
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

# Enviar notificación a Telegram de forma asíncrona
async def send_notification(message: str):
    """Envía una notificación a Telegram. Esta es una función asíncrona."""
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message
        }
        try:
            # Usamos aiohttp para hacer la petición HTTP sin bloquear el event loop
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        print(f"❌ Error al enviar a Telegram: {response_text}")
                        log_event("telegram_error", {"message": message, "response": response_text})
        except Exception as e:
            print(f"❌ Excepción al enviar a Telegram: {e}")
            log_event("telegram_exception", {"message": message, "exception": str(e)})
    else:
        print("⚠️ Faltan TELEGRAM_TOKEN o CHAT_ID.")
        log_event("telegram_credentials_missing", {})

    # Loguear la notificación (sigue siendo una llamada síncrona, lo cual está bien)
    log_event("manual_notification", {"message": message})