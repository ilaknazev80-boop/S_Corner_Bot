import os
import httpx
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
import uvicorn

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not OPENROUTER_API_KEY or not TELEGRAM_TOKEN:
    raise ValueError("Ошибка: не заданы переменные окружения")

user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_sessions[chat_id] = {"step": 1, "sport": "", "characteristics": "", "goal": ""}
    
    keyboard = [
        ["🏃 Бег", "🏊 Плавание"],
        ["⚽ Футбол", "💪 Фитнес"],
        ["🚴 Велоспорт", "🥋 Единоборства"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🏋️ Привет! Я S_Corner Bot — твой персональный AI-тренер на DeepSeek.\n\nВыбери свой вид спорта:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    
    if chat_id not in user_sessions:
        await start(update, context)
        return
    
    session = user_sessions[chat_id]
    
    if session["step"] == 1:
        session["sport"] = text
        session["step"] = 2
        await update.message.reply_text(
            "📊 Теперь напиши свои характеристики:\n\n"
            "`Возраст, Вес(кг), Рост(см), Уровень (новичок/средний/продвинутый)`\n\n"
            "Пример: 25, 75, 180, средний",
            parse_mode="Markdown"
        )
    
    elif session["step"] == 2:
        session["characteristics"] = text
        session["step"] = 3
        await update.message.reply_text(
            "🎯 Какая у тебя цель?\n\n"
            "1️⃣ Похудение\n2️⃣ Набор массы\n3️⃣ Выносливость\n4️⃣ Общее здоровье\n\n"
            "Напиши номер или текст цели:"
        )
    
    elif session["step"] == 3:
        session["goal"] = text
        session["step"] = 4
        
        await update.message.reply_text("🧠 Генерирую персональный план через DeepSeek AI...\n⏱️ Обычно 5-10 секунд.")
        
        plan = await generate_plan(session["sport"], session["characteristics"], session["goal"])
        await update.message.reply_text(plan, parse_mode="Markdown")
        
        del user_sessions[chat_id]
    
    else:
        await update.message.reply_text("Напиши /start, чтобы начать заново.")

async def generate_plan(sport: str, characteristics: str, goal: str) -> str:
    prompt = f"""Ты — профессиональный фитнес-тренер с 10-летним опытом.

Вид спорта: {sport}
Характеристики пользователя: {characteristics}
Цель: {goal}

Составь персонализированный план тренировок. ТРЕБОВАНИЯ:
- Ответь ТОЛЬКО на РУССКОМ языке
- Используй Markdown: **жирный**, *курсив*, • списки
- Укажи частоту тренировок (3-5 раз в неделю)
- Распиши упражнения по конкретным дням
- Обязательно добавь рекомендации по питанию
- Добавь мотивационную фразу в конце

Составь план тренировок:"""
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "microsoft/phi-3-mini-128k:free",  # ← МЕНЯЙ ЗДЕСЬ
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1500,
                "timeout": 30.0
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            print(f"Ошибка API: {response.status_code} - {response.text}")
            return f"⚠️ Ошибка API: {response.status_code}\n\nПопробуйте позже или сообщите разработчику."

# Создаем Telegram Application
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook обработчик
async def webhook(request: Request):
    try:
        body = await request.json()
        update = Update.de_json(body, telegram_app.bot)
        await telegram_app.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        print(f"Ошибка webhook: {e}")
        return Response(status_code=200)

async def health(request: Request):
    return JSONResponse({"status": "ok", "message": "S_Corner Bot is running!"})

async def homepage(request: Request):
    return JSONResponse({"message": "S_Corner Bot is alive! Use Telegram to interact."})

# Создаем Starlette приложение
app = Starlette(debug=False)
app.add_route("/", homepage)
app.add_route("/health", health)
app.add_route(f"/webhook/{TELEGRAM_TOKEN}", webhook, methods=["POST"])

# Установка webhook при запуске
async def setup_webhook():
    webhook_url = f"https://s-corner-bot.onrender.com/webhook/{TELEGRAM_TOKEN}"
    await telegram_app.bot.delete_webhook()
    result = await telegram_app.bot.set_webhook(webhook_url)
    if result:
        print(f"✅ Webhook успешно установлен: {webhook_url}")
    else:
        print(f"❌ Ошибка установки webhook")
    await telegram_app.initialize()  # ← ИНИЦИАЛИЗАЦИЯ ЗДЕСЬ!

@app.on_event("startup")
async def on_startup():
    await setup_webhook()
    print("🤖 Бот S_Corner запущен через webhook!")
