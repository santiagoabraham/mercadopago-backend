from flask import Flask, request, jsonify
import requests
import json
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://santiagoabraham.github.io"])

ACCESS_TOKEN = "APP_USR-2710442383202823-060714-af7765619bcfa3f7fb6444bda9638b7f-271027138"
ARCHIVO_PAGOS = "pagos_confirmados.json"
ARCHIVO_PREFERENCIAS = "preferencias_temp.json"

# Inicializar archivos si no existen
for archivo in [ARCHIVO_PAGOS, ARCHIVO_PREFERENCIAS]:
    if not os.path.exists(archivo):
        with open(archivo, "w") as f:
            json.dump({}, f)

@app.route('/crear_qr')
def crear_qr():
    dni = request.args.get('dni')
    total = request.args.get('total')
    comprobantes = request.args.get('comprobantes', '').split(',')

    preference_data = {
        "items": [{
            "title": f"Pago Socio DNI {dni}",
            "quantity": 1,
            "currency_id": "ARS",
            "unit_price": float(total)
        }],
        "metadata": {
            "dni": dni,
            "comprobantes": comprobantes
        },
        "notification_url": "https://backend-mercadopago-ulig.onrender.com/webhook"
    }

    response = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        json=preference_data,
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
    )

    if response.status_code == 201:
        resp_json = response.json()
        preference_id = resp_json.get("id")
        if preference_id:
            guardar_preference(preference_id, dni, comprobantes)
            print(f"📦 Guardado preference {preference_id} para DNI {dni}")

        return jsonify({
            "link": resp_json["init_point"],
            "id": preference_id
        })
    else:
        return jsonify({"error": "No se pudo generar el link"}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json or {}
    payment_id = data.get("data", {}).get("id")
    if not payment_id:
        payment_id = request.args.get("data.id") or request.args.get("id")

    topic = request.args.get("type") or request.args.get("topic")
    if topic != "payment":
        print(f"🔎 Webhook ignorado (tipo {topic})")
        return "", 200

    if payment_id:
        print(f"🔔 Webhook recibido con ID de pago: {payment_id}")
        mp_response = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}
        )

        if mp_response.status_code == 200:
            info = mp_response.json()
            if info.get("status") == "approved":
                dni = info.get("metadata", {}).get("dni")
                comprobantes = info.get("metadata", {}).get("comprobantes", [])

                if not dni:
                    preference_id = info.get("preference_id")
                    print(f"🔍 preference_id recibido en el webhook: {preference_id}")
                    dni, comprobantes = recuperar_preference(preference_id)
                    print(f"🔁 Recuperado DNI desde preferencias: {dni}")

                if dni:
                    guardar_pago(dni, comprobantes)
                    print(f"✅ Pago aprobado para DNI {dni}")
                else:
                    print(f"⚠️ Pago aprobado pero sin DNI (ID {payment_id})")
            else:
                print(f"ℹ️ Pago recibido pero no aprobado: {info.get('status')} (ID {payment_id})")
        else:
            print(f"❌ Error al consultar pago (ID {payment_id}): {mp_response.status_code}")
    else:
        print("⚠️ Webhook recibido sin ID de pago")

    return "", 200

@app.route('/estado_pago')
def estado_pago():
    dni = request.args.get('dni')
    comprobantes = request.args.get('comprobantes', '').split(',')
    pagos = cargar_json(ARCHIVO_PAGOS)
    pagado = dni in pagos and all(c in pagos[dni] for c in comprobantes)
    return jsonify({"pagado": pagado})

@app.route('/ver_preferencias')
def ver_preferencias():
    preferencias = cargar_json(ARCHIVO_PREFERENCIAS)
    return jsonify(preferencias)

# ======================
# Funciones auxiliares
# ======================

def guardar_pago(dni, comprobantes):
    pagos = cargar_json(ARCHIVO_PAGOS)
    if dni not in pagos:
        pagos[dni] = []
    for comp in comprobantes:
        if comp and comp not in pagos[dni]:
            pagos[dni].append(comp)
    guardar_json(ARCHIVO_PAGOS, pagos)

def guardar_preference(preference_id, dni, comprobantes):
    preferencias = cargar_json(ARCHIVO_PREFERENCIAS)
    preferencias[preference_id] = [dni, comprobantes]
    guardar_json(ARCHIVO_PREFERENCIAS, preferencias)

def recuperar_preference(preference_id):
    preferencias = cargar_json(ARCHIVO_PREFERENCIAS)
    return preferencias.get(preference_id, (None, []))

def cargar_json(path):
    with open(path, "r") as f:
        return json.load(f)

def guardar_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)
