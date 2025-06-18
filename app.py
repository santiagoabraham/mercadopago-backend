from flask import Flask, request, jsonify
import requests
import json
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://santiagoabraham.github.io"])

ACCESS_TOKEN = "APP_USR-2710442383202823-060714-af7765619bcfa3f7fb6444bda9638b7f-271027138"
ARCHIVO_PAGOS = "pagos_confirmados.json"


# Inicializar archivo si no existe
if not os.path.exists(ARCHIVO_PAGOS):
    with open(ARCHIVO_PAGOS, "w") as f:
        json.dump({}, f)


# ✅ Crear QR y guardar DNI + total en preferencia
@app.route('/crear_qr')
def crear_qr():
    dni = request.args.get('dni')
    total = request.args.get('total')

    preference_data = {
        "items": [{
            "title": f"Pago Socio DNI {dni}",
            "quantity": 1,
            "currency_id": "ARS",
            "unit_price": float(total)
        }],
        "metadata": {
            "dni": dni
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
        return jsonify({
            "link": resp_json["init_point"],
            "id": resp_json["id"]
        })
    else:
        return jsonify({"error": "No se pudo generar el link"}), 500


# ✅ Webhook que recibe las notificaciones de pago
@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Intentar desde el JSON (modo ideal, pero poco usado por MP)
    data = request.json or {}
    payment_id = data.get("data", {}).get("id")

    # 2. Intentar desde query string `data.id` o `id`
    if not payment_id:
        payment_id = request.args.get("data.id") or request.args.get("id")

    # Confirmar que es un webhook de tipo "payment"
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
                if dni:
                    guardar_pago(dni)
                    print(f"✅ Pago aprobado para DNI {dni}")
                else:
                    print(f"⚠️ Pago aprobado sin DNI (ID {payment_id})")
            else:
                print(f"ℹ️ Pago recibido pero NO aprobado: {info.get('status')} (ID {payment_id})")
        else:
            print(f"❌ Error al consultar pago (ID {payment_id}): {mp_response.status_code}")
    else:
        print("⚠️ Webhook recibido sin ID de pago")

    return "", 200



# ✅ Verificar si un DNI ya pagó
@app.route('/estado_pago')
def estado_pago():
    dni = request.args.get('dni')
    pagos = cargar_pagos()
    return jsonify({"pagado": dni in pagos})


# ✅ Funciones auxiliares
def guardar_pago(dni):
    pagos = cargar_pagos()
    pagos[dni] = True
    with open(ARCHIVO_PAGOS, "w") as f:
        json.dump(pagos, f)


def cargar_pagos():
    with open(ARCHIVO_PAGOS, "r") as f:
        return json.load(f)
