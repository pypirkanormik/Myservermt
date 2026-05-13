import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8753745508:AAEP92rHGV5A8BKcXklkQ7ByjPDRLwXZ_bM"
GAME_PORT = 19132 # Стандартный порт Minecraft Bedrock
# =============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class TunnelManager:
    def __init__(self):
        self.is_running = False
        self.process = None
        self.public_address = "Нажмите /start_server для генерации IP"

    async def start_tunnel(self):
        """Запуск UDP-туннеля Pinggy через встроенный SSH Linux"""
        print("[Tunnel] Подключение к серверам Pinggy...")
        # Запускаем туннель без скачивания утилит, используя стандартный SSH
        cmd = f"ssh -o StrictHostKeyChecking=no -R 0:localhost:{GAME_PORT} udp@a.pinggy.io"
        
        self.process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Читаем консоль туннеля, чтобы вытащить сгенерированный IP
        await asyncio.sleep(3)
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode('utf-8', errors='ignore')
                print(f"[Pinggy Log] {decoded_line.strip()}")
                
                # Ищем строку с публичным адресом во временных логах
                if "a.pinggy.io" in decoded_line:
                    # Извлекаем адрес и порт регулярным выражением
                    match = re.search(r'([a-zA-Z0-9\.]+):(\d+)', decoded_line)
                    if match:
                        self.public_address = match.group(0)
                        print(f"[Tunnel] УСПЕХ! Сервер доступен по IP: {self.public_address}")
                        break
        except Exception as e:
            print(f"[Tunnel Error] Не удалось прочитать логи: {e}")

# Инициализируем менеджер
tunnel = TunnelManager()

# --- КЛАСС ОБРАБОТКИ ПАКЕТОВ MINECRAFT PE (UDP) ---
class MinecraftBedrockProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        print(f"[Minecraft] Сетевое ядро слушает порт {GAME_PORT}")

    def datagram_received(self, data, addr):
        # Базовый ответ на пинг (Unconnected Pong) для отображения сервера в списке
        if data.startswith(b'\x05') or data.startswith(b'\x07'):
            pong_packet = b'\x1c' + data[1:9] + b'\x00\x00\x00\x00\x00\x00\x00\x00' + b'\x00\xff\xff\x00\xfe\xfe\xfe\xfe\xdf\xdf\xdf\xdf\x12\x34\x56\x78'
            self.transport.sendto(pong_packet, addr)

async def game_loop():
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: MinecraftBedrockProtocol(),
        local_addr=('127.0.0.1', GAME_PORT)
    )
    while tunnel.is_running:
        await asyncio.sleep(1)
    transport.close()

# --- КОМАНДЫ ТЕЛЕГРАМ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "📱 Управление сервером Minecraft PE через BotHost:\n\n"
        "/start_server — Включить сервер и сгенерировать IP\n"
        "/status — Проверить работу и узнать IP\n"
        "/stop_server — Полностью выключить сервер"
    )

@dp.message(Command("start_server"))
async def cmd_start_server(message: types.Message):
    if tunnel.is_running:
        return await message.answer(f"Сервер уже работает! IP: {tunnel.public_address}")
    
    tunnel.is_running = True
    await message.answer("⏳ Запуск ядра и генерация сетевого туннеля...")
    
    # Запускаем туннель и игровой цикл параллельно
    asyncio.create_task(tunnel.start_tunnel())
    asyncio.create_task(game_loop())
    
    await asyncio.sleep(4) # Ждем синхронизации
    await message.answer(
        f"🟢 Сервер успешно запущен!\n\n"
        f"🔗 Данные для входа в Minecraft PE:\n"
        f"Узнать точный IP: Нажмите /status через 5 секунд"
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    status = "🟢 Запущен" if tunnel.is_running else "🔴 Выключен"
    await message.answer(
        f"📊 Текущее состояние:\n"
        f"Статус: {status}\n"
        f"Адрес для Minecraft PE: `{tunnel.public_address}`",
        parse_mode="Markdown"
    )

@dp.message(Command("stop_server"))
async def cmd_stop_server(message: types.Message):
    if not tunnel.is_running:
        return await message.answer("Сервер и так выключен.")
    
    tunnel.is_running = False
    if tunnel.process:
        try:
            tunnel.process.terminate()
        except:
            pass
    tunnel.public_address = "Нажмите /start_server для генерации IP"
    await message.answer("🛑 Сервер и туннель успешно остановлены.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
