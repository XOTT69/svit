import os
import asyncio
from telegram import Bot
from tapo_cloud import TapoCloudClient

# ===== ENV =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])
TAPO_EMAIL = os.environ["TAPO_EMAIL"]
TAPO_PASSWORD = os.environ["TAPO_PASSWORD"]

# ===== НАСТРОЙКИ =====
CHECK_INTERVAL = 30        # секунд
POWER_THRESHOLD = 1.0      # Вт
CONFIRM_COUNT = 2          # підтвердження зміни

last_state = None
state_buffer = []

async def main():
    global last_state, state_buffer

    bot = Bot(BOT_TOKEN)

    client = TapoCloudClient(TAPO_EMAIL, TAPO_PASSWORD)
    devices = await client.get_devices()

    plug = next(d for d in devices if "P110" in d.model)

    await bot.send_message(CHAT_ID, "🤖 Світлобот запущено")

    while True:
        usage = await plug.get_device_usage()
        power = usage.current_power or 0

        state = "on" if power > POWER_THRESHOLD else "off"

        state_buffer.append(state)
        if len(state_buffer) > CONFIRM_COUNT:
            state_buffer.pop(0)

        if len(state_buffer) == CONFIRM_COUNT and all(s == state for s in state_buffer):
            if state != last_state:
                if state == "on":
                    await bot.send_message(CHAT_ID, "💡 Світло зʼявилось")
                else:
                    await bot.send_message(CHAT_ID, "🚫 Світло зникло")
                last_state = state

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
