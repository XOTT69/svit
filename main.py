import os
import time
import asyncio
from telegram import Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])
TAPO_EMAIL = os.environ["TAPO_EMAIL"]
TAPO_PASSWORD = os.environ["TAPO_PASSWORD"]
TAPO_IP = os.environ["TAPO_IP"]

CHECK_INTERVAL = 30
POWER_THRESHOLD = 1.0
CONFIRM_COUNT = 2

last_state = None
state_buffer = []

async def main():
    global last_state, state_buffer

    bot = Bot(BOT_TOKEN)

    plug = PyP110.P110(TAPO_IP, TAPO_EMAIL, TAPO_PASSWORD)
    plug.handshake()
    plug.login()

    await bot.send_message(CHAT_ID, "🤖 Світлобот запущено")

    while True:
        energy = plug.getEnergyUsage()
        power = energy.get("current_power", 0) / 1000  # mW → W

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
