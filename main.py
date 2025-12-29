import os
import time
import json
import asyncio
import base64
import hashlib
import requests
from telegram import Bot
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ===== ENV =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])
TAPO_EMAIL = os.environ["TAPO_EMAIL"]
TAPO_PASSWORD = os.environ["TAPO_PASSWORD"]

# ===== SETTINGS =====
CHECK_INTERVAL = 30        # сек
POWER_THRESHOLD = 1.0      # Вт
CONFIRM_COUNT = 2
RELOGIN_INTERVAL = 60 * 60 * 6  # 6 годин

last_state = None
state_buffer = []
last_login = 0
token = None
device = None


# ===== CRYPTO =====
def encrypt(data: str, key: bytes) -> str:
    iv = b"\x00" * 16
    pad = 16 - len(data) % 16
    data += chr(pad) * pad

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(data.encode()) + encryptor.finalize()
    return base64.b64encode(encrypted).decode()


# ===== TP-LINK CLOUD =====
def get_token(retries=5):
    payload = {
        "method": "login",
        "params": {
            "appType": "Tapo_Android",
            "cloudUserName": TAPO_EMAIL,
            "cloudPassword": hashlib.md5(TAPO_PASSWORD.encode()).hexdigest(),
            "terminalUUID": "render-light-bot"
        }
    }

    for _ in range(retries):
        r = requests.post("https://wap.tplinkcloud.com", json=payload, timeout=10)
        data = r.json()
        if "result" in data and "token" in data["result"]:
            return data["result"]["token"]
        time.sleep(2)

    raise Exception(f"TP-Link login failed: {data}")


def get_device(token):
    r = requests.post(
        f"https://wap.tplinkcloud.com?token={token}",
        json={"method": "getDeviceList"},
        timeout=10
    )
    devices = r.json()["result"]["deviceList"]

    for d in devices:
        if "P110" in d.get("deviceModel", ""):
            return d

    raise Exception("Tapo P110 not found")


def get_power(token, device):
    key = base64.b64decode(device["deviceKey"])

    request = encrypt(json.dumps({
        "method": "get_energy_usage"
    }), key)

    r = requests.post(
        f"https://{device['appServerUrl']}/?token={token}",
        json={"method": "passthrough", "params": {"request": request}},
        timeout=10
    )

    response = json.loads(
        base64.b64decode(r.json()["result"]["response"]).decode()
    )

    return response["result"]["current_power"] / 1000  # W


# ===== MAIN LOOP =====
async def main():
    global last_state, state_buffer, token, device, last_login

    bot = Bot(BOT_TOKEN)
    await bot.send_message(CHAT_ID, "🤖 Світлобот запущено")

    token = get_token()
    device = get_device(token)
    last_login = time.time()

    while True:
        try:
            # перевхід у cloud раз на 6 годин
            if time.time() - last_login > RELOGIN_INTERVAL:
                token = get_token()
                device = get_device(token)
                last_login = time.time()

            power = get_power(token, device)
            state = "on" if power > POWER_THRESHOLD else "off"

            state_buffer.append(state)
            if len(state_buffer) > CONFIRM_COUNT:
                state_buffer.pop(0)

            if len(state_buffer) == CONFIRM_COUNT and all(s == state for s in state_buffer):
                if state != last_state:
                    await bot.send_message(
                        CHAT_ID,
                        "💡 Світло зʼявилось" if state == "on" else "🚫 Світло зникло"
                    )
                    last_state = state

        except Exception as e:
            # не падаємо, просто перечекаємо
            print("ERROR:", e)
            time.sleep(10)

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
