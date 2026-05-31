import os
import httpx
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
import uvicorn

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not OPENROUTER_API_KEY or not TELEGRAM_TOKEN:
    raise ValueError("Ошибка: не заданы переменные окружения")

# Хранилище сессий пользователей
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога"""
    chat_id = update.effective_chat.id
    user_sessions[chat_id] = {
        "step": 1,
        "characteristics": "",
        "level": "",
        "goal": ""
    }
    
    await update.message.reply_text(
        "🏋️ *Привет! Я S_Corner Bot — твой персональный AI-тренер*\n\n"
        "Расскажи о себе, чтобы я мог составить идеальный план тренировок.\n\n"
        "_Напиши свой возраст, вес, рост:_\n"
        "Пример: `25 лет, 75 кг, 180 см`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех сообщений через AI"""
    chat_id = update.effective_chat.id
    text = update.message.text
    
    # Если сессии нет — начинаем сначала
    if chat_id not in user_sessions:
        await start(update, context)
        return
    
    session = user_sessions[chat_id]
    
    # Шаг 1: Характеристики
    if session["step"] == 1:
        session["characteristics"] = text
        session["step"] = 2
        await update.message.reply_text(
            "📊 *Какой у тебя уровень подготовки?*\n\n"
            "Напиши: `новичок`, `средний` или `продвинутый`\n\n"
            "_Также можешь описать свой опыт подробнее_",
            parse_mode="Markdown"
        )
        return
    
    # Шаг 2: Уровень подготовки
    if session["step"] == 2:
        session["level"] = text
        session["step"] = 3
        await update.message.reply_text(
            "🎯 *Какая у тебя цель?*\n\n"
            "Например:\n"
            "• Похудеть на 5 кг\n"
            "• Набрать мышечную массу\n"
            "• Улучшить выносливость\n"
            "• Подготовиться к марафону\n\n"
            "_Напиши свою цель подробно_",
            parse_mode="Markdown"
        )
        return
    
    # Шаг 3: Цель → Генерируем план
    if session["step"] == 3:
        session["goal"] = text
        
        await update.message.reply_text(
            "🧠 *Генерирую персональный план тренировок...*\n"
            "⏱️ Обычно это занимает 10-15 секунд",
            parse_mode="Markdown"
        )
        
        # Генерируем план через AI
        plan = await generate_workout_plan(
            session["characteristics"],
            session["level"],
            session["goal"]
        )
        
        await update.message.reply_text(plan, parse_mode="Markdown")
        
        # Предлагаем продолжить общение с AI
        await update.message.reply_text(
            "💬 *Теперь ты можешь задавать любые вопросы о тренировках, питании или технике упражнений!*\n\n"
            "Просто напиши, что хочешь узнать, и я помогу.\n\n"
            "_Например:_\n"
            "• Как правильно делать приседания?\n"
            "• Что есть перед тренировкой?\n"
            "• Составь тренировку на грудь и спину\n"
            "• Как убрать боль в коленях?",
            parse_mode="Markdown"
        )
        
        # Сбрасываем шаг, но не удаляем сессию — теперь бот в свободном режиме
        session["step"] = 0
        return
    
    # Шаг 0: Свободный режим — отвечаем на любые вопросы через AI
    if session["step"] == 0:
        await update.message.reply_text(
            "🤔 *Думаю...*\n",
            parse_mode="Markdown"
        )
        
        answer = await ask_ai_free(text, session)
        await update.message.reply_text(answer, parse_mode="Markdown")
        return

async def ask_ai_free(question: str, session: dict) -> str:
    """Свободный диалог с AI на основе контекста пользователя"""
    prompt = f"""Ты — профессиональный фитнес-тренер S_Corner. У тебя есть пользователь со следующими данными:

Характеристики: {session.get('characteristics', 'не указаны')}
Уровень подготовки: {session.get('level', 'не указан')}
Цель: {session.get('goal', 'не указана')}

Пользователь задает вопрос: "{question}"

Требования к ответу:
- Отвечай на РУССКОМ языке
- Будь дружелюбным и мотивирующим
- Давай практические советы
- Если вопрос не про спорт/здоровье — вежливо направь в тему

Ответ:"""
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://s-corner-bot.onrender.com",
                "X-Title": "S_Corner_Training_Bot"
            },
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 2000
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            return f"⚠️ Ошибка: {response.status_code}\nПопробуй переформулировать вопрос."

async def generate_workout_plan(characteristics: str, level: str, goal: str) -> str:
    """Генерация тренировочного плана на неделю"""
    prompt = f"""Ты — профессиональный фитнес-тренер S_Corner с 10-летним опытом.

Данные пользователя:
- Характеристики: {characteristics}
- Уровень подготовки: {level}
- Цель: {goal}

Составь ПЕРСОНАЛЬНЫЙ ТРЕНИРОВОЧНЫЙ ПЛАН НА НЕДЕЛЮ.

ТРЕБОВАНИЯ:
- Ответь только на РУССКОМ языке
- Используй Markdown: **жирный**, *курсив*, • списки
- Распиши каждый день недели (ПН, ВТ, СР, ЧТ, ПТ, СБ, ВС)
- Укажи: какие упражнения, сколько подходов и повторений
- Добавь дни отдыха и восстановления
- Включи рекомендации по питанию
- Добавь мотивационную фразу в конце

СТРУКТУРА ОТВЕТА:
## 🗓️ Твоя недельная программа
**Уровень:** {level}
**Цель:** {goal}

### Понедельник
• Упражнение 1 — 3x10
• ...

### Вторник
• ...

... и так до воскресенья

## 🍎 Рекомендации по питанию
- Совет 1
- Совет 2

## 💪 Мотивация
Твоя мотивационная фраза

Напиши план тренировок:"""
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://s-corner-bot.onrender.com",
                "X-Title": "S_Corner_Training_Bot"
            },
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            return f"⚠️ Ошибка генерации плана: {response.status_code}\n\nПопробуй позже."

# --- Telegram Application ---
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Webhook ---
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
    return JSONResponse({"status": "ok"})

async def homepage(request: Request):
    return JSONResponse({"message": "S_Corner Bot is running!"})

# --- Starlette приложение ---
app = Starlette(debug=False)
app.add_route("/", homepage)
app.add_route("/health", health)
app.add_route(f"/webhook/{TELEGRAM_TOKEN}", webhook, methods=["POST"])

async def setup_webhook():
    webhook_url = f"https://s-corner-bot.onrender.com/webhook/{TELEGRAM_TOKEN}"
    await telegram_app.bot.delete_webhook()
    result = await telegram_app.bot.set_webhook(webhook_url)
    if result:
        print(f"✅ Webhook успешно установлен: {webhook_url}")
    else:
        print(f"❌ Ошибка установки webhook")
    await telegram_app.initialize()

@app.on_event("startup")
async def on_startup():
    await setup_webhook()
    print("🤖 Бот S_Corner запущен через webhook!")
