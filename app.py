from flask import Flask, request, jsonify
from flask_cors import CORS  # ✅ Habilita CORS
import mercadopago
import os

app = Flask(__name__)
CORS(app)  # ✅ Esto permite que tu frontend desde GitHub Pages se conecte

# Access token de MercadoPago (modo test o real)
ACCESS_TOKEN = "TEST-2710442383202823-060714-a1ca2431f069e5b9555443aaeeddcc8b-271027138"
sdk = mercadopago.SDK(ACCESS_TOKEN)

@app.route('/crear_qr', methods=['GET'])
def crear_qr():
    dni = request.args.get("dni")
    total = request.args.get("total")

    if not dni or not total:
        return jsonify({"error": "Faltan parámetros"}), 400

    try:
        preference_data = {
            "items": [
                {
                    "title": f"Pago de cuotas - DNI {dni}",
                    "quantity": 1,
                    "unit_price": float(total),
                    "currency_id": "ARS"
                }
            ],
            "metadata": {
                "dni": dni
            },
            "external_reference": dni,
            "notification_url": "https://tusitio.com/webhook",
            "back_urls": {
                "success": "https://tusitio.com/pago-exitoso",
                "failure": "https://tusitio.com/pago-fallido",
                "pending": "https://tusitio.com/pago-pendiente"
            },
            "auto_return": "approved"
        }

        preference = sdk.preference().create(preference_data)
        init_point = preference["response"]["init_point"]

        return jsonify({"link": init_point})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
