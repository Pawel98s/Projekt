from flask import Blueprint, render_template, request, redirect, jsonify

pages_bp = Blueprint("pages", __name__)

def register_pages(pages_bp, deps):
    product_repo = deps["product_repo"]
    review_repo = deps["review_repo"]
    extractor = deps["extractor"]
    summarizer = deps["summarizer"]
    embedder = deps["embedder"]
    logger = deps["logger"]

    @pages_bp.get("/")
    def home():
        return render_template("index.html")

    @pages_bp.route("/add.html", methods=["GET", "POST"])
    def add_product():
        if request.method == "POST":
            name = request.form.get("name")
            link = request.form.get("link")

            text = extractor.extract_text_from_link(link)
            description = summarizer.summarize_markdown(text)
            embedding = embedder.encode(description).tolist()

            product_repo.insert(name, description, link, embedding)
            logger.log("ADD_PRODUCT", f"Added product '{name}'")
            return redirect("/view.html?page=1")

        return render_template("add.html")

    @pages_bp.get("/view.html")
    def view_products():
        page = request.args.get("page", 1, type=int)
        q = request.args.get("q", "", type=str)
        per_page = request.args.get("per_page", 5, type=int)

        products, total_pages = product_repo.list_paginated_with_reviews(page, per_page, q)

        return render_template(
            "view.html",
            products=products,
            page=page,
            total_pages=total_pages,
            q=q,
            per_page=per_page
        )

    @pages_bp.route("/edit/<int:id>", methods=["GET", "POST"])
    def edit_product(id):
        page = request.args.get("page", 1)
        q = request.args.get("q", "")

        product = product_repo.get(id)
        if not product:
            return "Produkt nie istnieje", 404

        _, old_name, _, old_link = product

        if request.method == "POST":
            new_name = request.form.get("name")
            new_link = request.form.get("link")

            text = extractor.extract_text_from_link(new_link)
            new_description = summarizer.summarize_markdown(text)
            new_embedding = embedder.encode(new_description).tolist()

            product_repo.update(id, new_name, new_link, new_description, new_embedding)
            logger.log("EDIT_PRODUCT", f"{old_name} -> {new_name}")
            return redirect(f"/view.html?page={page}&q={q}")

        return render_template("edit.html", id=id, name=old_name, link=old_link, page=page, q=q)

    @pages_bp.get("/product/<int:product_id>")
    def product_page(product_id):
        product = product_repo.get(product_id)
        if not product:
            return "Produkt nie znaleziony", 404
        _, name, description, link = product
        reviews = review_repo.list_for_product(product_id)

        return render_template(
            "product.html",
            product_id=product_id,
            name=name,
            description=description,
            link=link,
            reviews=reviews
        )

    @pages_bp.get("/ask.html")
    def ask_page():
        return render_template("ask.html")

    @pages_bp.get("/logs")
    def view_logs():
        logs = deps["log_repo"].latest(limit=500)
        return render_template("logs.html", logs=logs)