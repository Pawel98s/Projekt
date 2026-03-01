from flask import Blueprint, request, jsonify, session

api_bp = Blueprint("api", __name__)

def register_api(api_bp, deps):
    product_repo = deps["product_repo"]
    review_repo = deps["review_repo"]
    chat_service = deps["chat_service"]
    logger = deps["logger"]

    @api_bp.before_app_request
    def ensure_session():
        import uuid
        if "session_id" not in session:
            session["session_id"] = str(uuid.uuid4())
        if "history" not in session:
            session["history"] = []
        if "last_product_ids" not in session:
            session["last_product_ids"] = []

    @api_bp.get("/get_history")
    def get_history():
        return jsonify(session.get("history", []))

    @api_bp.post("/ask")
    def ask():
        data = request.json or {}
        question = data.get("question")
        if not question:
            return jsonify({"answer": "", "products": [], "error": "Brak pytania"}), 400

        history = session.get("history", [])
        history.append({"role": "user", "content": question})

        last_ids = session.get("last_product_ids", [])
        answer, rows, new_last_ids = chat_service.answer(question, history, last_ids)
        session["last_product_ids"] = new_last_ids

        history.append({"role": "assistant", "content": answer})
        session["history"] = history
        session.modified = True

        products_info = []
        for pid, name, desc, link, reviews in rows:
            products_info.append({
                "id": pid,
                "name": name,
                "link": link or f"/product/{pid}",
                "capacity": None,
                "image_url": "/static/no_image.png"
            })

        return jsonify({"answer": answer, "products": products_info})

    @api_bp.get("/new_chat")
    def new_chat():
        session["history"] = []
        session.pop("last_product_ids", None)
        session.modified = True
        return jsonify({"status": "ok"})

    @api_bp.delete("/delete/<int:id>")
    def delete_product(id):
        row = product_repo.get(id)
        if not row:
            logger.log("DELETE_PRODUCT_FAIL", f"Missing product {id}")
            return jsonify({"error": "Produkt nie istnieje"}), 404

        product_repo.delete(id)
        logger.log("DELETE_PRODUCT", f"Deleted product {id}")

        page = request.args.get("page", 1)
        q = request.args.get("q", "")
        return jsonify({"redirect": f"/view.html?page={page}&q={q}"})

    @api_bp.delete("/delete_review/<int:id>")
    def delete_review(id):
        txt = review_repo.get_text(id)
        if not txt:
            return jsonify({"error": "Opinia nie istnieje"}), 404
        review_repo.delete(id)
        logger.log("DELETE_REVIEW", f"Deleted review ID {id}")
        return jsonify({"status": "ok"})

    @api_bp.post("/edit_review/<int:id>")
    def edit_review(id):
        data = request.json or {}
        new_text = data.get("review_text", "")
        review_repo.update(id, new_text)
        logger.log("EDIT_REVIEW", f"Edited review ID {id}")
        return jsonify({"status": "ok"})

    @api_bp.post("/addReview")
    def add_review():
        data = request.get_json() or {}
        product_id = data.get("product_id")
        review_text = data.get("review_text", "")

        review_id = review_repo.add(product_id, review_text)
        logger.log("ADD_REVIEW", f"Review for product_id {product_id}: {review_text}")
        return jsonify({"id": review_id, "text": review_text})