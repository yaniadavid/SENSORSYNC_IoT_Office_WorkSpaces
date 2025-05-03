# 🧠 Smart Support Platform for Office Workspaces

Plataforma inteligente desarrollada para mejorar el rendimiento del equipo de soporte técnico en entornos laborales físicos. El sistema combina el monitoreo ambiental con una gestión eficiente de tickets para garantizar comodidad, productividad y coordinación efectiva.

## 🚀 Funcionalidades Principales

### 👨‍💼 Dashboard Gerencial
- Visualización en tiempo real de la oficina mediante p5.js.
- Acceso a estadísticas inteligentes sobre tickets resueltos, abiertos y promedio de tiempos.
- Métricas ambientales (temperatura, humedad, calidad del aire).

### 👩‍💻 Zona de Empleados
- Visualización de métricas de confort en tiempo real.
- Visualización de agenda del equipo.
- Asignación automática o inteligente de tickets de soporte.

### 🌿 Sensores Ambientales (Integración Física)
- Lectura en tiempo real de sensores DHT11 (temperatura y humedad).
- Monitoreo de calidad del aire.
- Lectura de distancia y proximidad.

> ⚠️ El reconocimiento facial para ingreso con OpenCV es manejado en otro módulo separado.

## 🧱 Stack Tecnológico

- **Frontend**: JavaScript (no TypeScript), Vite, p5.js
- **Backend/API**: Node.js (estructura externa)
- **Base de datos**: MySQL
- **Hardware**: Sensores físicos (DHT11, MQ135, HC-SR04)
