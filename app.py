from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)
ACCESS_TOKEN = "APP_USR-2710442383202823-060714-af7765619bcfa3f7fb6444bda9638b7f-271027138"
ARCHIVO_PAGOS = "pagos_confirmados.json"
ARCHIVO_PREFS = "preferencias_temp.json"

# Funciones auxiliares para leer/escribir JSON
def cargar_json(nombre):
    if not os.path.exists(nombre):
        return {}
    with open(nombre, "r") as f:
        return json.load(f)

def guardar_json(nombre, data):
    with open(nombre, "w") as f:
        json.dump(data, f, indent=2)

# Guardar pago (DNI y lista de Nro_Comprobante)
def guardar_pago(dni, comprobantes):
    pagos = cargar_json(ARCHIVO_PAGOS)
    if dni not in pagos:
        pagos[dni] = []
    pagos[dni].extend([c for c in comprobantes if c not in pagos[dni]])
    guardar_json(ARCHIVO_PAGOS, pagos)

# Crear QR
@app.route('/crear_qr')
def crear_qr():
    dni = request.args.get('dni')
    total = request.args.get('total')
    comprobantes = request.args.get('comprobantes')

    metadata = {"dni": dni}
    if comprobantes:
        metadata["comprobantes"] = json.loads(comprobantes)

    preference_data = {
        "items": [{
            "title": f"Pago Socio DNI {dni}",
            "quantity": 1,
            "currency_id": "ARS",
            "unit_price": float(total)
        }],
        "metadata": metadata,
        "notification_url": "https://backend-mercadopago-ulig.onrender.com/webhook"
    }

    print("\n\U0001F9FE Enviando preferencia:", json.dumps(preference_data, indent=2))

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
        prefs = cargar_json(ARCHIVO_PREFS)
        prefs[resp_json["id"]] = dni
        guardar_json(ARCHIVO_PREFS, prefs)
        print(f"\U0001F4E6 Guardado preference {resp_json['id']} para DNI {dni}")
        return jsonify({"link": resp_json["init_point"], "id": resp_json["id"]})
    else:
        return jsonify({"error": "No se pudo generar el link"}), 500

# Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.args or request.json or {}

    topic = data.get("topic")
    if topic == "merchant_order":
        print("\U0001F50E Webhook ignorado (tipo merchant_order)")
        return "", 200

    payment_id = data.get("id") or data.get("data", {}).get("id")
    print(f"\U0001F514 Webhook recibido con ID de pago: {payment_id}")

    if not payment_id:
        print("\u26A0\uFE0F Webhook recibido sin ID de pago")
        return "", 200

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
                dni = recuperar_preference(info.get("preference_id"))
                print(f"\U0001F501 Recuperado DNI desde preferencias: {dni}")

            if dni:
                guardar_pago(dni, comprobantes)
                print(f"\u2705 Pago aprobado para DNI {dni} - Comprobantes: {comprobantes}")
            else:
                print(f"\u26A0\uFE0F Pago aprobado pero sin DNI (ID {payment_id})")
    else:
        print(f"\u274C Error al consultar pago (ID {payment_id}): {mp_response.status_code}")

    return "", 200

# Recuperar DNI desde preference
def recuperar_preference(pref_id):
    prefs = cargar_json(ARCHIVO_PREFS)
    return prefs.get(str(pref_id))

# Ver estado de pagos
@app.route('/estado_pago')
def estado_pago():
    dni = request.args.get('dni')
    pagos = cargar_json(ARCHIVO_PAGOS)
    comprobantes_pagados = pagos.get(dni, [])
    return jsonify({"pagado": len(comprobantes_pagados) > 0, "comprobantes": comprobantes_pagados})

# DEBUG opcional para revisar prefs
@app.route('/ver_preferencias')
def ver_prefs():
    return jsonify(cargar_json(ARCHIVO_PREFS))