import os
import threading
from flask import Flask
import telebot

# 1. Creamos un servidor web falso para engañar a Render
app = Flask('')

@app.route('/')
def home():
    return "Bot de Nutrición de Luis está en línea y funcionando!"

def run_flask():
    # Render nos da el puerto automáticamente en la variable de entorno PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# 2. Configuración de tu Bot de Telegram
# (Asegúrate de que la variable TOKEN esté bien configurada en Render o ponla aquí)
TOKEN = os.environ.get("TELEGRAM_TOKEN") 
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "¡Hola, Luis! El bot de nutrición inteligente está activo y listo.")

# Puedes dejar aquí abajo el resto de tus funciones y lógica de Gemini...

# 3. Arrancar ambos sistemas a la vez
if __name__ == "__main__":
    # Arrancamos el servidor web en un hilo separado para que Render no se queje
    t = threading.Thread(target=run_flask)
    t.start()
    
    print("Arrancando el bot de Telegram...")
    # Arrancamos el bot para que escuche los mensajes
    bot.infinity_polling()
