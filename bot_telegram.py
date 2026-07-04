import os
import threading
import sqlite3
import json
from datetime import datetime
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai

# ==========================================
# CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ==========================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
DB_NAME = "nutricion.db"

# Inicializar Bot y cliente de Gemini
bot = telebot.TeleBot(TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

# Inicializar Flask para engañar a Render con el puerto
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de Nutrición de Luis está vivito y coleando!"

# ==========================================
# BASE DE DATOS (The Shield)
# ==========================================
def init_db():
    """Crea la base de datos local y las tablas si no existen."""
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
    """Busca el registro de hoy o crea uno nuevo a cero."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT chicken, rice, water, creatine, protein, carbs FROM registros WHERE fecha = ?', (today,))
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute('INSERT INTO registros (fecha) VALUES (?)', (today,))
        conn.commit()
        row = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        
    conn.close()
    
    return {
        "chicken": row[0],
        "rice": row[1],
        "water": row[2],
        "creatine": row[3],
        "protein": row[4],
        "carbs": row[5]
    }

def update_today_record(data):
    """Actualiza los valores del día de hoy en la base de datos."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE registros 
        SET chicken = ?, rice = ?, water = ?, creatine = ?, protein = ?, carbs = ?
        WHERE fecha = ?
    ''', (data["chicken"], data["rice"], data["water"], data["creatine"], data["protein"], data["carbs"], today))
    conn.commit()
    conn.close()

# ==========================================
# LÓGICA DEL BOT DE TELEGRAM
# ==========================================

# Comando /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    init_db()  # Asegura que la tabla exista al iniciar
    username = message.from_user.first_name
    texto_bienvenida = (
        f"¡Hola {username}! Bienvenido a tu Inteligencia Artificial de Nutrición de confianza.\n\n"
        "Escríbeme libremente lo que comiste (ejemplo: 'Me comí 200g de pollo y 250g de arroz') y yo me "
        "encargaré de calcular los macronutrientes y guardarlos en tu registro diario. 🥦🍗"
    )
    bot.reply_to(message, texto_bienvenida)

# Escuchar TODOS los mensajes de texto (Comidas del usuario)
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_text = message.text
    chat_id = message.chat.id
    
    # Enviar un mensaje de "escribiendo..." para que el usuario sepa que la IA está pensando
    bot.send_chat_action(chat_id, 'typing')
    
    # Buscar el registro de hoy antes de actualizarlo
    current_totals = get_or_create_today_record()
    
    # Crear un prompt claro para Gemini exigiendo una respuesta en formato JSON estricto
    prompt = f"""
    Eres un experto en nutrición y un bot de backend estructurado. El usuario te dirá lo que comió en texto libre.
    Tu trabajo es analizar el texto y extraer las cantidades aproximadas de los siguientes elementos en gramos o mililitros:
    - chicken (pollo)
    - rice (arroz)
    - water (agua)
    - creatine (creatina)
    - protein (proteína total estimada de toda la comida)
    - carbs (carbohidratos totales estimados de toda la comida)

    Texto del usuario: "{user_text}"

    Debes responder ÚNICAMENTE con un objeto JSON válido, sin bloques de código markdown, sin texto extra. Si un elemento no se menciona, ponlo en 0.0.
    Ejemplo de respuesta exacta:
    {{"chicken": 200.0, "rice": 150.0, "water": 0.0, "creatine": 0.0, "protein": 60.0, "carbs": 42.0}}
    """
    
    try:
        # Llamada a la API de Gemini usando la nueva librería genai
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        # Limpiar la respuesta por si acaso la IA metió comillas extras o saltos de línea
        json_text = response.text.strip().replace("```json", "").replace("```", "")
        extracted_data = json.loads(json_text)
        
        # Sumar lo que calculó Gemini a los totales que el usuario ya llevaba en el día
        current_totals["chicken"] += float(extracted_data.get("chicken", 0.0))
        current_totals["rice"] += float(extracted_data.get("rice", 0.0))
        current_totals["water"] += float(extracted_data.get("water", 0.0))
        current_totals["creatine"] += float(extracted_data.get("creatine", 0.0))
        current_totals["protein"] += float(extracted_data.get("protein", 0.0))
        current_totals["carbs"] += float(extracted_data.get("carbs", 0.0))
        
        # Guardar los nuevos totales en "The Shield"
        update_today_record(current_totals)
        
        # Responder de forma bonita al usuario
        respuesta_usuario = (
            "✅ ¡Comida registrada con éxito!\n\n"
            f"📊 **Añadido en esta comida:**\n"
            f"🍗 Pollo: {extracted_data.get('chicken', 0)}g\n"
            f"🍚 Arroz: {extracted_data.get('rice', 0)}g\n"
            f"🥩 Proteína Est.: {extracted_data.get('protein', 0)}g\n"
            f"🍞 Carbohidratos Est.: {extracted_data.get('carbs', 0)}g\n\n"
            f"📈 **Totales acumulados hoy:**\n"
            f"🍗 Pollo total: {current_totals['chicken']}g\n"
            f"🍚 Arroz total: {current_totals['rice']}g\n"
            f"🥩 Proteínas totales: {current_totals['protein']}g\n"
            f"🍞 Carbohidratos totales: {current_totals['carbs']}g"
        )
        bot.reply_to(message, respuesta_usuario)
        
    except Exception as e:
        # Control de errores por si falla el JSON o la API
        print(f"Error procesando el mensaje: {e}")
        bot.reply_to(message, "Ups, lo siento Luis. Tuve un pequeño problema analizando esa comida. ¿Podrías volver a intentarlo de otra forma?")

# ==========================================
# EJECUCIÓN DEL SERVIDOR
# ==========================================
def run_telebot():
    print("Iniciando hilos de Telegram...")
    bot.infinity_polling()

if __name__ == '__main__':
    # Asegurar que la base de datos esté lista
    init_db()
    
    # Lanzar Telegram en un hilo separado para que no tranque a Flask
    t = threading.Thread(target=run_telebot)
    t.start()
    
    # Lanzar Flask en el puerto que Render requiere por defecto
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
