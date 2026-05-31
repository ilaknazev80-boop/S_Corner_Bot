from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn
import os
import asyncio
from threading import Thread

# Импортируем и запускаем Telegram-бота в отдельном потоке
import bot

async def health(request):
    return JSONResponse({"status": "ok", "message": "S_Corner Bot is running!"})

async def homepage(request):
    return JSONResponse({"message": "S_Corner Bot is alive. Use Telegram to interact."})

# Запускаем бота в фоновом потоке
def start_bot():
    bot.main()

# Стартуем поток с ботом при загрузке приложения
thread = Thread(target=start_bot, daemon=True)
thread.start()

# Настраиваем веб-сервер для Render (healthcheck)
app = Starlette(debug=False, routes=[
    Route("/", homepage),
    Route("/health", health),
])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)