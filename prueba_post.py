import requests

# 1. La dirección web del simulador de API (aquí es donde enviamos el paquete)
url = "https://jsonplaceholder.typicode.com/posts"

# 2. Preparamos el "paquete" con los datos que queremos enviar (en formato de diccionario/JSON)
# Imagina que estamos registrando un nuevo artículo en un blog
paquete_de_datos = {
    "title": "Mi primer POST desde Trujillo",
    "body": "Estoy aprendiendo a enviar datos a una API con Python y Gemini.",
    "userId": 1
}

print("✉️ Enviando paquete de datos al servidor remoto...")

# 3. Hacemos la petición usando .post() y pasamos los datos en el parámetro 'json'
respuesta = requests.post(url, json=paquete_de_datos)

# 4. El servidor nos responde con un "recibo" (código de estado) y los datos que guardó
codigo_estado = respuesta.status_code
datos_recibidos = respuesta.json()

print("-----------------------------------------")
print(f"¡Servidor contactado! Código de estado: {codigo_estado} 🚀")
print("Este es el recibo que nos devolvió el servidor:")
print(datos_recibidos)
print("-----------------------------------------")