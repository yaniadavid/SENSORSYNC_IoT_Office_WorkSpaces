import cv2
import serial
import time
import json
import paho.mqtt.client as mqtt
import mysql.connector
from datetime import datetime
import random

# === Conexión a la base de datos ===
db = mysql.connector.connect(
    host="ace2proyecto2.c9qccsmcc9db.us-east-2.rds.amazonaws.com",
    user="admin",
    password="ACE2_Proyecto2",
    database="ACE2_Proyecto2",
    port=3306
)
cursor = db.cursor()

# === Variables globales ===
mqtt_broker = "broker.hivemq.com"
mqtt_port = 1883
mqtt_topic_temperatura = "temperatura"
mqtt_topic_calidad_aire = "calidad_aire"
mqtt_topic_personas = "Personas"
mqtt_topic_opencv = "entra"
mqtt_topic_ultrasonico = "sale"

temperatura_actual = None
humedad_actual = None
calidad_actual = None
distancia_actual = None
contador_actual = None
usuario_id_counter = 1

# === MQTT ===
def on_message(client, userdata, msg):
    global temperatura_actual, humedad_actual, calidad_actual, distancia_actual, contador_actual, usuario_id_counter
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
        print(f"[{topic}] {payload}")

        if topic == mqtt_topic_temperatura:
            temperatura_actual = float(payload['temperatura'])
            humedad_actual = float(payload['humedad'])
            cursor.execute("INSERT INTO DHT11 (temperatura, humedad) VALUES (%s, %s)",
                           (temperatura_actual, humedad_actual))
            db.commit()

        elif topic == mqtt_topic_calidad_aire:
            calidad_actual = float(payload['calidad_aire_ppm'])
            cursor.execute("INSERT INTO CALIDAD_AIRE (calidad) VALUES (%s)", (calidad_actual,))
            db.commit()

        elif topic == mqtt_topic_personas:
            contador_actual = int(payload['personas'])
            distancia_actual = 5.0
            cursor.execute("INSERT INTO OBJETOS_CERCA (distancia, contador) VALUES (%s, %s)",
                           (distancia_actual, contador_actual))
            db.commit()

        elif topic == mqtt_topic_opencv:
            nombre = f"Persona{usuario_id_counter}"
            apellido = "Detectada"
            cursor.execute("INSERT INTO USUARIOS (nombres, apellidos, id_rol, onSite) VALUES (%s, %s, %s, %s)",
                           (nombre, apellido, 3, True))
            db.commit()
            print(f"Nuevo usuario agregado: {nombre} {apellido} (onSite = TRUE)")
            usuario_id_counter += 1

        elif topic == mqtt_topic_ultrasonico:
            cursor.execute("SELECT id_usuario FROM USUARIOS WHERE onSite = TRUE ORDER BY id_usuario DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE USUARIOS SET onSite = FALSE WHERE id_usuario = %s", (row[0],))
                db.commit()
                print(f"Usuario con ID {row[0]} marcado como ausente (onSite = FALSE)")

        # Insertar en tabla histórica si hay todos los datos
        if all(val is not None for val in [temperatura_actual, humedad_actual, calidad_actual, distancia_actual, contador_actual]):
            cursor.execute("""
                INSERT INTO HISTORICO_AMBIENTE (temperatura, humedad, calidad_aire, distancia_objeto, contador_objetos)
                VALUES (%s, %s, %s, %s, %s)
            """, (temperatura_actual, humedad_actual, calidad_actual, distancia_actual, contador_actual))
            db.commit()
            print("[Histórico] Registro consolidado guardado")
            temperatura_actual = humedad_actual = calidad_actual = distancia_actual = contador_actual = None

    except Exception as e:
        print(f"Error al procesar mensaje: {e}")

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect(mqtt_broker, mqtt_port, 60)
mqtt_client.subscribe(mqtt_topic_temperatura)
mqtt_client.subscribe(mqtt_topic_calidad_aire)
mqtt_client.subscribe(mqtt_topic_personas)
mqtt_client.subscribe(mqtt_topic_opencv)
mqtt_client.subscribe(mqtt_topic_ultrasonico)
mqtt_client.loop_start()

# === MODO SIMULACIÓN DE DATOS ===
modo_simulacion = True  # Cambiar a False para usar Arduino y cámara

if modo_simulacion:
    print("\n[SIMULACIÓN ACTIVADA] Enviando datos de prueba a MQTT y base de datos...\n")
    while True:
        temp = round(random.uniform(20.0, 30.0), 2)
        humedad = round(random.uniform(40.0, 60.0), 2)
        calidad = round(random.uniform(300.0, 600.0), 2)
        contador = random.randint(0, 5)

        mqtt_client.publish(mqtt_topic_temperatura, json.dumps({
            "timestamp": datetime.now().isoformat(),
            "temperatura": temp,
            "humedad": humedad
        }))

        mqtt_client.publish(mqtt_topic_calidad_aire, json.dumps({
            "timestamp": datetime.now().isoformat(),
            "calidad_aire_ppm": calidad
        }))

        mqtt_client.publish(mqtt_topic_personas, json.dumps({
            "timestamp": datetime.now().isoformat(),
            "personas": contador
        }))

        # Opcional: simular entrada y salida
        if random.choice([True, False]):
            mqtt_client.publish(mqtt_topic_opencv, json.dumps({
                "timestamp": datetime.now().isoformat(),
                "evento": "Persona detectada por OpenCV"
            }))
        else:
            mqtt_client.publish(mqtt_topic_ultrasonico, json.dumps({
                "timestamp": datetime.now().isoformat(),
                "evento": "Persona detectada por ultrasonico (posible salida)"
            }))

        time.sleep(5)
else:
    # === Arduino y OpenCV ===
    arduino = serial.Serial('COM5', 9600, timeout=1)
    time.sleep(2)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0)

    contador = 0
    rostro_detectado = False
    ultima_deteccion = 0
    intervalo_deteccion = 5.0
    led_encendido = False
    ultimo_contador = -1
    ultima_publicacion_calidad = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tiempo_actual = time.time()
        if tiempo_actual - ultima_deteccion >= intervalo_deteccion:
            faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            ultima_deteccion = tiempo_actual
            if len(faces) > 0 and not rostro_detectado:
                arduino.write(b'ROSTRO\n')
                contador += 1
                rostro_detectado = True
                mqtt_client.publish(mqtt_topic_opencv, json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "evento": "Persona detectada por OpenCV"
                }))
                if contador >= 1 and not led_encendido:
                    arduino.write(b'ENCENDER_LED\n')
                    led_encendido = True
            elif len(faces) == 0:
                rostro_detectado = False

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, 'Rostro', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.putText(frame, f'Contador: {contador}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        if arduino.in_waiting > 0:
            mensaje = arduino.readline().decode('utf-8').strip()
            if mensaje == "OBJETO_CERCA":
                contador = max(0, contador - 1)
                mqtt_client.publish(mqtt_topic_ultrasonico, json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "evento": "Persona detectada por ultrasonico (posible salida)"
                }))
                if contador == 0 and led_encendido:
                    arduino.write(b'APAGAR_LED\n')
                    led_encendido = False
                elif contador >= 1 and not led_encendido:
                    arduino.write(b'ENCENDER_LED\n')
                    led_encendido = True

            elif "Temperatura:" in mensaje:
                try:
                    parts = mensaje.split(", ")
                    temp = float(parts[0].split(": ")[1].split(" °C")[0])
                    humedad = float(parts[1].split(": ")[1].split(" %")[0])
                    mqtt_client.publish(mqtt_topic_temperatura, json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "temperatura": temp,
                        "humedad": humedad
                    }))
                except Exception as e:
                    print("Error al procesar lectura de temperatura:", e)

            if contador != ultimo_contador:
                mqtt_client.publish(mqtt_topic_personas, json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "personas": contador
                }))
                ultimo_contador = contador

        cv2.imshow('Detección de Rostros', frame)
        if cv2.waitKey(1) & 0xFF == ord('x'):
            break

    cap.release()
    cv2.destroyAllWindows()
    arduino.close()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    cursor.close()
    db.close()
