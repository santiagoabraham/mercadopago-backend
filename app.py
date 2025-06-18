from flask import Flask, request, jsonify
import requests
import json
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://santiagoabraham.github.io"])

ACCESS_TOKEN = "TEST-2710442383202823-060714-a1ca2431f069e5b9555443aaeeddcc8b-271027138"
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
    data = request.json
    payment_id = data.get("data", {}).get("id")

    if payment_id:
        # Consultar estado del pago
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
                    print(f"Pago aprobado para DNI {dni}")
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
