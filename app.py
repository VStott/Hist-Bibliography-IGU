import os
from flask import Flask, jsonify, render_template, request

from engine import generate_gost_bibliography_items, render_single_citation
from normalizer import parser

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024  # 512 KB
app.config["JSON_AS_ASCII"] = False

MAX_BATCH_ITEMS = 200


@app.errorhandler(413)
def payload_too_large(_err):
    return jsonify({"error": "Слишком большой размер запроса"}), 413


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/generate", methods=["POST"])
def generate():
    raw_data = request.get_json(silent=True)
    if not isinstance(raw_data, dict):
        return jsonify({"error": "Ожидается JSON-объект с данными источника"}), 400

    try:
        csl_json = parser(raw_data)
        citation = render_single_citation(csl_json)
        return jsonify({"citation": citation})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        app.logger.exception("Ошибка при генерации библиографической ссылки")
        return jsonify({"error": "Внутренняя ошибка сервера при генерации ссылки"}), 500


@app.route("/generate/batch", methods=["POST"])
def generate_batch():
    payload = request.get_json(silent=True)
    if isinstance(payload, list):
        raw_items = payload
        sort_russian_first = True
        numbered = True
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        raw_items = payload["items"]
        sort_russian_first = bool(payload.get("sort_russian_first", True))
        numbered = bool(payload.get("numbered", True))
    else:
        return jsonify({
            "error": "Ожидается JSON-массив источников или объект вида {'items': [...]}."
        }), 400

    if not raw_items:
        return jsonify({"items": [], "citations": []})

    if len(raw_items) > MAX_BATCH_ITEMS:
        return jsonify({
            "error": f"Слишком много источников в одном запросе (максимум ограничен: {MAX_BATCH_ITEMS})."
        }), 400

    try:
        csl_items = []
        for idx, item in enumerate(raw_items, start=1):
            csl_item = parser(item)
            if not item.get("id"):
                csl_item["id"] = f"item_{idx}"
            csl_items.append(csl_item)

        items = generate_gost_bibliography_items(
            csl_items,
            sort_russian_first=sort_russian_first,
        )
        citations = [
            f"{entry['number']}. {entry['citation']}" if numbered else entry["citation"]
            for entry in items
        ]
        return jsonify({"items": items, "citations": citations})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        app.logger.exception("Ошибка при пакетной генерации библиографии")
        return jsonify({"error": "Внутренняя ошибка сервера при генерации списка"}), 500


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)