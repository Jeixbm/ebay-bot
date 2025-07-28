import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from notifier import send_notification, log_event

DATA_FOLDER = "data"
HISTORY_FILE = os.path.join(DATA_FOLDER, "history.json")
already_seen_links = set()
MAX_PRICE = 2500

def ensure_data_folder():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w") as f:
            json.dump({}, f)

def load_history():
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def is_url_valid(url):
    return url.startswith("https://www.ebay.com")

def default_validation(title, price):
    return (
        any(gpu in title for gpu in ["rtx 3060", "rtx 3070", "rtx 3080", "rtx 4060", "rtx 4070", "rtx 4080", "rtx 4090",
                                     "rx 6600m", "rx 6700m", "rx 6800m", "rx 6850m xt", "rx 7600m", "rx 7700s", "rx 7800m xt"]) and
        price <= MAX_PRICE
    )

# === ENHANCERS (puedes seguir agregando más abajo) ===
def extract_specs(result):
    title = result['title'].lower()
    specs = []
    cpu_match = re.search(r'(i[579]-\d{4,5}[a-zA-Z]*)|(ryzen\s[579]\s\d{4,5}[a-zA-Z]*)', title)
    gpu_match = re.search(r'(rtx\s?\d{4})|(rx\s?\d{4,5}[a-zA-Z]*)', title)
    ram_match = re.search(r'(\d{1,3})\s?gb\s?(ram)?', title)
    ssd_match = re.search(r'((\d+(\.\d+)?\s?tb)|(\d+\s?gb))\s?(ssd|nvme)', title)
    screen_match = re.search(r'(\d{2}\.\d?)\s?(\"|”|in)', title)
    if cpu_match:
        specs.append(f"• CPU: {cpu_match.group(0).upper()}")
    if gpu_match:
        specs.append(f"• GPU: {gpu_match.group(0).upper()}")
    if ram_match:
        specs.append(f"• RAM: {ram_match.group(0).upper()}")
    if ssd_match:
        specs.append(f"• SSD: {ssd_match.group(0).upper()}")
    if screen_match:
        specs.append(f"• Pantalla: {screen_match.group(1)}\")")
    if specs:
        result["formatted"] += "\n🧠 *Specs detectadas:*\n" + "\n".join(specs)

def check_returning_model(result, history):
    link = result["url"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    last_seen = history.get(link, [])[-1]["date"] if history.get(link) else None
    if last_seen:
        days = (datetime.utcnow() - datetime.strptime(last_seen, "%Y-%m-%d")).days
        if days >= 3:
            result["formatted"] += f"\n📢 Este modelo no aparecía desde hace *{days} días*."
    else:
        result["formatted"] += "\n🆕 Primera vez que se detecta este modelo."

def mark_good_deal(result):
    title = result['title'].lower()
    price = result['price']
    limits = {
        "rtx 4090": 2200, "rtx 4080": 1900, "rtx 4070": 1500, "rtx 4060": 1200, "rtx 4050": 1000,
        "rtx 3070": 1200, "rtx 3060": 1000, "rtx 3050": 900, "rx 6600m": 900, "rx 6700m": 1100,
        "rx 6800m": 1300, "rx 6850m xt": 1300, "rx 7600m": 1100, "rx 7700s": 1200, "rx 7800m xt": 1300
    }
    for gpu, max_p in limits.items():
        if gpu in title and price <= max_p:
            result["formatted"] += "\n🏷️ *BUENA OFERTA*"
            break

# === CONFIGURACIÓN FINAL ===
ENHANCERS = [extract_specs, check_returning_model, mark_good_deal]

# === FUNCIÓN PRINCIPAL ===
def search_ebay():
    ensure_data_folder()
    history = load_history()
    url = "https://www.ebay.com/sch/i.html?_nkw=gaming+laptop&LH_PrefLoc=1&_sop=10"
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []
    items = soup.select(".s-item")[:20]

    for item in items:
        title_elem = item.select_one(".s-item__title")
        link_elem = item.select_one("a.s-item__link")
        price_elem = item.select_one(".s-item__price")

        if not (title_elem and link_elem and price_elem):
            continue

        title = title_elem.text.lower()
        price_text = price_elem.text.replace('$', '').replace(',', '').split()[0]

        try:
            price = float(price_text)
        except ValueError:
            continue

        link = link_elem["href"]
        if link in already_seen_links:
            continue

        if not default_validation(title, price):
            continue

        if not is_url_valid(link):
            log_event("invalid_link", {"title": title_elem.text, "url": link})
            continue

        already_seen_links.add(link)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        history.setdefault(link, []).append({"date": today, "price": price, "title": title_elem.text})

        result = {
            "formatted": f"🎯 *{title_elem.text}*\n💲 {price_elem.text}\n🔗 {link}",
            "title": title_elem.text,
            "price": price,
            "url": link
        }

        for enhancer in ENHANCERS:
            enhancer(result, history) if enhancer.__code__.co_argcount == 2 else enhancer(result)

        results.append(result)

    save_history(history)
    return results

# === FUNCIÓN PARA MONITOREAR Y NOTIFICAR ===
def monitor_laptops():
    try:
        laptops = search_ebay()
        if laptops:
            for item in laptops:
                send_notification(item["formatted"])
                log_event("notification_sent", {
                    "title": item["title"],
                    "price": item["price"],
                    "url": item["url"]
                })
        else:
            send_notification("⚠️ No se encontraron laptops gaming premium.")
            log_event("no_results", {"message": "No se encontraron resultados."})
    except Exception as e:
        msg = f"❌ Error al monitorear laptops: {e}"
        send_notification(msg)
        log_event("error", {"error": str(e)})
