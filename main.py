import os
import time
import json
import asyncio
import base64
import hashlib
import requests
from telegram import Bot
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])
TAPO_EMAIL = os.environ["TAPO_EMAIL"]
TAPO_PASSWORD = os.environ["TAPO_PASSWORD"]

CHECK_INTERVAL = 30
POWER_THRESHOLD = 1.0
CONFIRM_COUNT = 2

state_buffer = []
last_state = None

def encrypt(data, key):
    iv = b"\x00" * 16
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    pad = 16 - len(data) % 16
    data += chr(pad) * pad
    return base64.b64encode(encryptor.update(data.encode()) + encryptor.finalize()).decode()

def get_token():
    payload = {
        "method": "login",
        "params": {
            "appType": "Tapo_Android",
            "cloudUserName": TAPO_EMAIL,
            "cloudPassword": hashlib.md5(TAPO_PASSWORD.encode()).hexdigest(),
            "terminalUUID": "render-light-bot"
        }
    }
    r = requests.post(
        "https://wap.tplinkcloud.com",
        json=payload,
        timeout=10
    )
    return r.json()["result"]["token"]

def get_device(token):
    r = requests.post(
        f"https://wap.tplinkcloud.com?token={token}",
        json={"method": "getDeviceList"},
        timeout=10
    )
    devices = r.json()["result"]["deviceList"]
    return next(d for d in devices if "P110" in d["deviceModel"])

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

    data = json.loads(
        base64.b64decode(r.json()["result"]["response"]).decode()
    )
    return data["result"]["current_power"] / 1000  # W

async def main():
    global last_state, state_buffer

    bot = Bot(BOT_TOKEN)
    await bot.send_message(CHAT_ID, "🤖 Світлобот запущено")

    token = get_token()
    device = get_device(token)

    while True:
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

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
