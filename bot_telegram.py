import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
import json
import sqlite3
from datetime import datetime

# ==========================================
# 1. INITIALIZATION & CREDENTIALS
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Base nutrition goals
TARGET_PROTEIN = 160  
TARGET_CARBS = 300    
TARGET_WATER = 3.5    
TARGET_CREATINE = 5.0 

DB_NAME = "nutricion.db"

# ==========================================
# 2. DATABASE MANAGEMENT (The Shield)
# ==========================================
def init_db():
    """Creates the local database file and tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT UNIQUE,
            chicken REAL DEFAULT 0.0,
            rice REAL DEFAULT 0.0,
            water REAL DEFAULT 0.0,
            creatine REAL DEFAULT 0.0,
            protein REAL DEFAULT 0.0,
            carbs REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

def get_or_create_today_record():
    """Fetches today's record or creates a clean one if the day just started."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT chicken, rice, water, creatine, protein, carbs FROM registros WHERE fecha = ?', (today,))
    row = cursor.fetchone()
    
    if row is None:
        # It's a new day! Insert a blank row
        cursor.execute('INSERT INTO registros (fecha) VALUES (?)', (today,))
        conn.commit()
        row = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        
    conn.close()
    
    # Return as a dictionary to handle easily in Python
    return {
        "chicken": row[0],
        "rice": row[1],
        "water": row[2],
        "creatine": row[3],
        "protein": row[4],
        "carbs": row[5]
    }

def update_today_record(data_to_add):
    """Updates the data permanently inside the Dell's hard drive."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Get existing data
    current = get_or_create_today_record()
    
    # 2. Calculate new totals
    new_chicken = current["chicken"] + data_to_add.get("chicken", 0.0)
    new_rice = current["rice"] + data_to_add.get("rice", 0.0)
    new_water = current["water"] + data_to_add.get("water", 0.0)
    new_creatine = current["creatine"] + data_to_add.get("creatine", 0.0)
    new_protein = current["protein"] + data_to_add.get("protein", 0.0)
    new_carbs = current["carbs"] + data_to_add.get("carbs", 0.0)
    
    # 3. Save to database file
    cursor.execute('''
        UPDATE registros 
        SET chicken = ?, rice = ?, water = ?, creatine = ?, protein = ?, carbs = ?
        WHERE fecha = ?
    ''', (new_chicken, new_rice, new_water, new_creatine, new_protein, new_carbs, today))
    
    conn.commit()
    conn.close()

def reset_today_record():
    """Resets today's values back to zero in the database."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE registros 
        SET chicken = 0.0, rice = 0.0, water = 0.0, creatine = 0.0, protein = 0.0, carbs = 0.0
        WHERE fecha = ?
    ''', (today,))
    conn.commit()
    conn.close()

# Initialize the database on startup
init_db()
print("💾 Base de datos SQLite inicializada y protegida en la Dell.")

# ==========================================
# 3. INTERACTIVE KEYBOARDS & TEXT GENERATION
# ==========================================
def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    btn_food = InlineKeyboardButton("🍗 Registrar Comida (IA)", callback_data="nav_food")
    btn_water = InlineKeyboardButton("💧 +250ml Agua", callback_data="quick_water")
    btn_creatine = InlineKeyboardButton("💪 +5g Creatina", callback_data="quick_creatine")
    btn_status = InlineKeyboardButton("📊 Ver Estado", callback_data="nav_status")
    btn_reset = InlineKeyboardButton("🔄 Reiniciar Día", callback_data="nav_reset")
    markup.add(btn_food, btn_water, btn_creatine, btn_status, btn_reset)
    return markup

def build_status_text():
    # Read directly from the secure database file, NOT from RAM variables!
    data = get_or_create_today_record()
    
    protein_left = TARGET_PROTEIN - data["protein"]
    carbs_left = TARGET_CARBS - data["carbs"]
    water_left = TARGET_WATER - data["water"]
    creatine_left = TARGET_CREATINE - data["creatine"]
    
    return f"""
📊 **PANEL DE CONTROL NUTRICIONAL (PROTEGIDO)**
----------------------------------
🍗 Pollo total: {data["chicken"]:.1f}g
🍚 Arroz total: {data["rice"]:.1f}g

🔥 **PROGRESO NUTRICIONAL:**
• **Proteína:** {data["protein"]:.1f}g / {TARGET_PROTEIN}g (Faltan: {max(0.0, protein_left):.1f}g)
• **Carbohidratos:** {data["carbs"]:.1f}g / {TARGET_CARBS}g (Faltan: {max(0.0, carbs_left):.1f}g)

💧 **HIDRATACIÓN Y SUPLEMENTOS:**
• **Agua:** {data["water"]:.2f}L / {TARGET_WATER}L (Faltan: {max(0.0, water_left):.2f}L)
• **Creatina:** {data["creatine"]:.1f}g / {TARGET_CREATINE}g (Faltan: {max(0.0, creatine_left):.1f}g)
----------------------------------
📌 *¿Qué deseas registrar ahora? Usa los botones o escribe texto libre.*
"""

# ==========================================
# 4. IA PARSING LOGIC
# ==========================================
def parse_food_with_ai(user_text):
    prompt = f"""
    Eres un asistente de nutrición. Analiza este texto: "{user_text}"
    Responde ÚNICAMENTE con un objeto JSON estricto, sin texto adicional, sin bloques ```json:
    {{
        "chicken": float,
        "rice": float,
        "water": float,
        "creatine": float
    }}
    """
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ AI Parsing Error: {e}")
        return None

# ==========================================
# 5. TELEGRAM EVENT HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    text = "👋 **¡Hola Luis! Panel interactivo sincronizado con la Base de Datos.**\n" + build_status_text()
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_button_clicks(call):
    bot.answer_callback_query(call.id)
    
    if call.data == "nav_food":
        instructions = "✍️ **Registro por IA:** Escríbeme de forma natural lo que consumiste.\n*Ejemplo: 'Me comí 100g de pollo'*"
        bot.send_message(call.message.chat.id, instructions, parse_mode="Markdown")
        
    elif call.data == "quick_water":
        update_today_record({"water": 0.25})  # Writes to file instantly
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text="💧 +250ml de agua guardados en el disco.\n" + build_status_text(), parse_mode="Markdown", reply_markup=get_main_keyboard())
        
    elif call.data == "quick_creatine":
        update_today_record({"creatine": 5.0})  # Writes to file instantly
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text="💪 Dosis de 5g de creatina asegurada en base de datos.\n" + build_status_text(), parse_mode="Markdown", reply_markup=get_main_keyboard())
        
    elif call.data == "nav_status":
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text=build_status_text(), parse_mode="Markdown", reply_markup=get_main_keyboard())
        
    elif call.data == "nav_reset":
        reset_today_record()  # Wipes file values for today
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text="🔄 Base de datos reiniciada para el día de hoy.\n" + build_status_text(), parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_natural_language(message):
    thinking = bot.reply_to(message, "🧠 Procesando tu texto con Gemini y guardando en base de datos...")
    extracted_data = parse_food_with_ai(message.text)
    
    if extracted_data:
        chicken = extracted_data.get("chicken", 0.0)
        rice = extracted_data.get("rice", 0.0)
        water = extracted_data.get("water", 0.0)
        creatine = extracted_data.get("creatine", 0.0)
        
        protein_gained = (chicken * 31 / 100) + (rice * 2.7 / 100)
        carbs_gained = (rice * 28 / 100)
        
        # Structure payload to push into SQLite
        payload = {
            "chicken": chicken,
            "rice": rice,
            "water": water,
            "creatine": creatine,
            "protein": protein_gained,
            "carbs": carbs_gained
        }
        
        if chicken == 0 and rice == 0 and water == 0 and creatine == 0:
            bot.edit_message_text("🤔 No detecté alimentos claros para guardar. ¡Intenta de nuevo!", chat_id=message.chat.id, message_id=thinking.message_id)
        else:
            update_today_record(payload)  # Pushes all calculations into database safely
            bot.delete_message(chat_id=message.chat.id, message_id=thinking.message_id)
            bot.send_message(message.chat.id, f"✅ **¡Guardado permanente exitoso!**\n🍗 Pollo: +{chicken}g | 🍚 Arroz: +{rice}g\n" + build_status_text(), parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        bot.edit_message_text("❌ Error al conectar con Gemini. Revisa tu conexión.", chat_id=message.chat.id, message_id=thinking.message_id)

# ==========================================
# 6. RUNNING THE BOT
# ==========================================
bot.infinity_polling()