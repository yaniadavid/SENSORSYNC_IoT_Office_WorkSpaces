import cv2
import serial
import time
import paho.mqtt.client as mqtt
import json
from datetime import datetime

# Crear conexión serial con el Arduino
arduino = serial.Serial('COM5', 9600, timeout=1)  # Ajusta el puerto según tu sistema
time.sleep(2)  # Esperar que Arduino reinicie

# Configuración MQTT
mqtt_broker = "broker.hivemq.com"  # Broker público de HiveMQ
mqtt_port = 1883
mqtt_topic_temperatura = "temperatura"
mqtt_topic_calidad_aire = "calidad_aire"
mqtt_topic_personas = "Personas"
mqtt_topic_ingreso = "Persona_ingreso"

# Variables globales
contador = 0
rostro_detectado = False
ultima_deteccion = 0  # Tiempo de la última detección
intervalo_deteccion = 5.0  # Intervalo en segundos entre detecciones
led_encendido = False  # Estado del LED
ultimo_contador = -1  # Para detectar cambios en el contador

# Configuración del cliente MQTT
mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print(f"Conectado al broker MQTT con código resultado: {rc}")
    # Suscribirse a los topics
    client.subscribe(mqtt_topic_temperatura)
    client.subscribe(mqtt_topic_calidad_aire)
    client.subscribe(mqtt_topic_personas)
    print(f"Suscrito a {mqtt_topic_temperatura}, {mqtt_topic_calidad_aire}, {mqtt_topic_personas}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        print(f"Mensaje recibido en {msg.topic}: {payload}")
        
        # Procesar mensajes según el topic
        if msg.topic == mqtt_topic_temperatura:
            try:
                data = json.loads(payload)
                print(f"Temperatura recibida: {data}")
            except json.JSONDecodeError:
                print(f"Error al decodificar mensaje de temperatura: {payload}")
        
        elif msg.topic == mqtt_topic_calidad_aire:
            try:
                data = json.loads(payload)
                print(f"Calidad del aire recibida: {data}")
            except json.JSONDecodeError:
                print(f"Error al decodificar mensaje de calidad del aire: {payload}")
        
        elif msg.topic == mqtt_topic_personas:
            try:
                data = json.loads(payload)
                print(f"Datos de personas recibidos: {data}")
            except json.JSONDecodeError:
                print(f"Error al decodificar mensaje de personas: {payload}")
                
    except Exception as e:
        print(f"Error al procesar mensaje MQTT: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(mqtt_broker, mqtt_port, 60)
mqtt_client.loop_start()

# Cargar el clasificador Haar Cascade para detección de rostros
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Verificar si el clasificador se cargó correctamente
if face_cascade.empty():
    print("Error: No se pudo cargar el archivo haarcascade_frontalface_default.xml")
    exit()

# Abrir la cámara
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: No se pudo abrir la cámara.")
    exit()

# Nombre de la ventana
window_name = 'Deteccion de Rostros'

def leer_serial():
    """Leer y mostrar datos del puerto serial"""
    global contador, led_encendido, ultimo_contador
    try:
        if arduino.in_waiting > 0:  # Verificar si hay datos disponibles
            mensaje = arduino.readline().decode('utf-8').strip()
            if mensaje:  # Si se recibe un mensaje válido
                print(mensaje)
                # Si el sensor ultrasónico detecta un objeto a 5 cm
                if mensaje == "OBJETO_CERCA":
                    contador = max(0, contador - 1)  # Decrementar contador, no menor que 0
                    print(f"Objeto detectado a 5 cm. Contador: {contador}")
                    # Actualizar estado del LED
                    if contador == 0 and led_encendido:
                        arduino.write(b'APAGAR_LED\n')
                        led_encendido = False
                        print("LED apagado")
                    elif contador >= 1 and not led_encendido:
                        arduino.write(b'ENCENDER_LED\n')
                        led_encendido = True
                        print("LED encendido")
                # Procesar lecturas de temperatura del DHT11
                elif "Temperatura:" in mensaje:
                    try:
                        parts = mensaje.split(", ")
                        temp = float(parts[0].split(": ")[1].split(" °C")[0])
                        humedad = float(parts[1].split(": ")[1].split(" %")[0])
                        # Publicar temperatura en MQTT
                        mqtt_client.publish(mqtt_topic_temperatura, json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "temperatura": temp,
                            "humedad": humedad
                        }))
                        print(f"Publicado temperatura en {mqtt_topic_temperatura}: {temp} °C, {humedad} %")
                    except (IndexError, ValueError) as e:
                        print(f"Error al procesar lectura de DHT11: {mensaje} - {e}")
                # Publicar el contador si cambió
                if contador != ultimo_contador:
                    mqtt_client.publish(mqtt_topic_ingreso, json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "personas": contador
                    }))
                    print(f"Publicado contador en {mqtt_topic_ingreso}: {contador}")
                    ultimo_contador = contador
    except Exception as e:
        print(f"Error al leer serial: {e}")

while True:
    # Capturar frame por frame
    ret, frame = cap.read()
    
    if not ret:
        print("Error: No se pudo recibir el frame.")
        break
    
    # Convertir el frame a escala de grises
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    tiempo_actual = time.time()
    faces = []
    if tiempo_actual - ultima_deteccion >= intervalo_deteccion:
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        ultima_deteccion = tiempo_actual
    
    # Procesar detección de rostros
    if len(faces) > 0:
        if not rostro_detectado:
            # Enviar señal una vez al detectar un rostro
            arduino.write(b'ROSTRO\n')
            print("Rostro detectado: Señal enviada al Arduino.")
            contador += 1
            rostro_detectado = True
            print(f"Contador: {contador}")
            # Encender LED si contador >= 1
            if contador >= 1 and not led_encendido:
                arduino.write(b'ENCENDER_LED\n')
                led_encendido = True
                print("LED encendido")
    else:
        rostro_detectado = False
    
    # Dibujar rectángulos alrededor de los rostros
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, 'Rostro', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    
    # Mostrar el contador en la ventana
    cv2.putText(frame, f'Contador: {contador}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    # Leer datos del Arduino
    leer_serial()
    
    # Mostrar el frame
    cv2.imshow(window_name, frame)
    
    # Capturar tecla presionada
    key = cv2.waitKey(1) & 0xFF
    
    # Salir con la tecla 'x'
    if key == ord('x'):
        break
    
    # Detectar si la ventana fue cerrada manualmente
    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break

# Liberar la cámara y cerrar todas las ventanas
cap.release()
cv2.destroyAllWindows()

# Cerrar la conexión serial y MQTT
arduino.close()
mqtt_client.loop_stop()
mqtt_client.disconnect()