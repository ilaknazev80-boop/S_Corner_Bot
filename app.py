import os
import httpx
import asyncio
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

user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_sessions[chat_id] = {
        "step": 1,
        "sport": "",
        "characteristics": "",
        "level": "",
        "goal": ""
    }
    
    await update.message.reply_text(
        "🏋️ *Привет! Я S_Corner Bot — твой AI-тренер*\n\n"
        "📝 *Шаг 1:* Каким видом спорта занимаешься?\n"
        "Пример: бег, плавание, фитнес, бокс, йога",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    if chat_id not in user_sessions:
        await start(update, context)
        return
    
    session = user_sessions[chat_id]
    
    # Шаг 1: Вид спорта
    if session["step"] == 1:
        session["sport"] = text
        session["step"] = 2
        await update.message.reply_text(
            "📊 *Шаг 2:* Твои характеристики\n"
            "Возраст, вес, рост\n"
            "Пример: 30 лет, 75 кг, 180 см",
            parse_mode="Markdown"
        )
        return
    
    # Шаг 2: Характеристики
    if session["step"] == 2:
        session["characteristics"] = text
        session["step"] = 3
        await update.message.reply_text(
            "📈 *Шаг 3:* Уровень подготовки\n"
            "новичок / средний / продвинутый",
            parse_mode="Markdown"
        )
        return
    
    # Шаг 3: Уровень
    if session["step"] == 3:
        session["level"] = text
        session["step"] = 4
        await update.message.reply_text(
            "🎯 *Шаг 4:* Твоя цель\n"
            "Примеры: похудеть, набрать массу, улучшить выносливость",
            parse_mode="Markdown"
        )
        return
    
    # Шаг 4: Генерация плана
    if session["step"] == 4:
        session["goal"] = text
        
        await update.message.reply_text(
            "🧠 *Составляю план...*\n"
            "Подожди 10-20 секунд ⏱️",
            parse_mode="Markdown"
        )
        
        plan = await generate_workout_plan(
            session["sport"],
            session["characteristics"],
            session["level"],
            session["goal"]
        )
        
        await update.message.reply_text(plan, parse_mode="Markdown")
        
        await update.message.reply_text(
            "💬 *Теперь можешь задавать любые вопросы о спорте и тренировках!*\n\n"
            "Просто напиши свой вопрос.",
            parse_mode="Markdown"
        )
        
        session["step"] = 0
        return
    
    # Свободный режим
    if session["step"] == 0:
        msg = await update.message.reply_text("🤔 *Думаю...*", parse_mode="Markdown")
        
        answer = await ask_ai_free(text, session)
        
        await msg.edit_text(answer, parse_mode="Markdown")
        return

async def ask_ai_free(question: str, session: dict) -> str:
    prompt = f"""Фитнес-тренер. Данные пользователя:
Спорт: {session.get('sport', '?')}
Цель: {session.get('goal', '?')}
Уровень: {session.get('level', '?')}

Вопрос: {question}

Ответь кратко (2-3 предложения) на русском, дружелюбно, по делу."""
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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
                    "max_tokens": 300
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return "⚠️ Ошибка API. Попробуй еще раз."
    except httpx.TimeoutException:
        return "⏰ Таймаут. Повтори вопрос проще или чуть позже."
    except Exception:
        return "⚠️ Ошибка. Попробуй еще раз."

async def generate_workout_plan(sport: str, characteristics: str, level: str, goal: str) -> str:
    prompt = f"""Фитнес-тренер. Составь план на неделю для:
Спорт: {sport}
Данные: {characteristics}
Уровень: {level}
Цель: {goal}

Формат:
## 🗓️ План ({sport})
**ПН:** упражнения
**ВТ:** отдых/легкая
**СР:** упражнения
**ЧТ:** отдых
**ПТ:** упражнения
**СБ:** длительная
**ВС:** отдых

## 🍎 Питание
2-3 пункта

## 💪 Мотивация
Кратко (2-3 предложения) на русском"""

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
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
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return "⚠️ Ошибка генерации плана. Попробуй /start заново."
    except Exception:
        return "⚠️ Ошибка. Попробуй /start еще раз."

# --- Остальной код (Telegram Application, Webhook, Starlette) ---
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

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

app = Starlette(debug=False)
app.add_route("/", homepage)
app.add_route("/health", health)
app.add_route(f"/webhook/{TELEGRAM_TOKEN}", webhook, methods=["POST"])

async def setup_webhook():
    webhook_url = f"https://s-corner-bot.onrender.com/webhook/{TELEGRAM_TOKEN}"
    await telegram_app.bot.delete_webhook()
    result = await telegram_app.bot.set_webhook(webhook_url)
    if result:
        print(f"✅ Webhook: {webhook_url}")
    else:
        print(f"❌ Ошибка webhook")
    await telegram_app.initialize()

@app.on_event("startup")
async def on_startup():
    await setup_webhook()
    print("🤖 Бот S_Corner запущен!")
