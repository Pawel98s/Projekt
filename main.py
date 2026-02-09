from flask import Flask, render_template, request, redirect, jsonify, session
import psycopg2
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import os
import fitz
from bs4 import BeautifulSoup
import requests
import uuid
import math

app = Flask(__name__)
app.secret_key = "cookie"


model = SentenceTransformer('all-MiniLM-L6-v2')
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_db_connection():
    return psycopg2.connect(
        dbname="testowa",
        user="postgres",
        password="lahata",
        host="localhost",
        port="5432"
    )


conn = get_db_connection()
cur = conn.cursor()
cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT,
        description TEXT,
        link TEXT,
        embedding vector(384)
    );
""")
cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY,
        action TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
""")
conn.commit()
cur.close()
conn.close()


@app.before_request
def make_session_permanent():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    if "history" not in session:
        session["history"] = []


def log_event(action: str, details: str = ""):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO logs (action, details) VALUES (%s, %s)",
            (action, details)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Log Error: {e}")


def extract_text_from_link(link: str) -> str:
    if not link:
        return ""
    try:
        if link.lower().endswith(".pdf"):
            response = requests.get(link)
            response.raise_for_status()
            with open("temp.pdf", "wb") as f:
                f.write(response.content)
            doc = fitz.open("temp.pdf")
            text = "".join([page.get_text() for page in doc])
            doc.close()
            return text.strip()
        else:
            response = requests.get(link)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for script in soup(["script", "style", "noscript"]):
                script.extract()
            text = soup.get_text(separator="\n")
            return " ".join(text.split()).strip()
    except Exception as e:
        print(f"Błąd pobierania {link}: {e}")
        return ""


def generate_summary_from_link(link: str) -> str:
    text = extract_text_from_link(link)
    if not text:
        return "Brak dostępnej treści do streszczenia."
    prompt = f"""
Na podstawie poniższego tekstu wygeneruj opis produktu w formacie MARKDOWN.

WYMAGANIA:
- Użyj nagłówków sekcji w formacie: ## Nazwa sekcji
- Sekcje MUSZĄ występować w tej kolejności:
  1. ## Podstawowe informacje
  2. ## Parametry techniczne
  3. ## Ergonomia i bezpieczeństwo
  4. ## Zastosowanie
  5. ## Podsumowanie
- W sekcji "Podstawowe informacje" MUSZĄ znaleźć się:
  - Nazwa produktu
  - Typ
  - Marka
- Stosuj listy punktowane tam, gdzie to możliwe
- Nie dodawaj nic poza treścią opisu

TEKST ŹRÓDŁOWY:
{text}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Błąd generowania streszczenia: {e}")
        return "Błąd podczas generowania streszczenia."


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/add.html', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        link = request.form.get('link')

        description = generate_summary_from_link(link)
        embedding = model.encode(description).tolist()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO products (name, description, link, embedding) VALUES (%s,%s,%s,%s)",
            (name, description, link, embedding)
        )
        conn.commit()
        cur.close()
        conn.close()

        log_event("ADD_PRODUCT", f"Added product '{name}'")

        return redirect('/view.html?page=1')

    return render_template('add.html')


@app.route('/view.html')
def view_products():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "", type=str)
    per_page = request.args.get("per_page", 5, type=int)  # <- tu pobieramy ilość produktów
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cur = conn.cursor()

    where_clause = ""
    params = []

    if q:
        where_clause = "WHERE p.name ILIKE %s OR p.description ILIKE %s"
        params.extend([f"%{q}%", f"%{q}%"])

    cur.execute(f"SELECT COUNT(*) FROM products p {where_clause}", params)
    total_products = cur.fetchone()[0]
    total_pages = max(1, math.ceil(total_products / per_page))

    cur.execute(f"""
        SELECT p.id, p.name, p.description, p.link,
               json_agg(
                   json_build_object(
                       'id', r.id,
                       'text', r.review_text
                   )
               ) FILTER (WHERE r.id IS NOT NULL) AS reviews
        FROM products p
        LEFT JOIN reviews r ON r.product_id = p.id
        {where_clause}
        GROUP BY p.id
        ORDER BY p.id
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    products = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        'view.html',
        products=products,
        page=page,
        total_pages=total_pages,
        q=q,
        per_page=per_page
    )

@app.route('/delete_review/<int:id>', methods=['DELETE'])
def delete_review(id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT review_text FROM reviews WHERE id=%s", (id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "Opinia nie istnieje"}), 404

    cur.execute("DELETE FROM reviews WHERE id=%s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    log_event("DELETE_REVIEW", f"Deleted review ID {id}")
    return jsonify({"status": "ok"})


@app.route('/edit_review/<int:id>', methods=['POST'])
def edit_review(id):
    data = request.json
    new_text = data.get("review_text")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE reviews
        SET review_text = %s
        WHERE id = %s
    """, (new_text, id))

    conn.commit()
    cur.close()
    conn.close()

    log_event("EDIT_REVIEW", f"Edited review ID {id}")
    return jsonify({"status": "ok"})


@app.route('/product/<int:product_id>')
def product_page(product_id):
    conn = get_db_connection()
    cur = conn.cursor()


    cur.execute(
        "SELECT name, description, link FROM products WHERE id = %s",
        (product_id,)
    )
    product = cur.fetchone()

    if not product:
        cur.close()
        conn.close()
        return "Produkt nie znaleziony", 404

    name, description, link = product


    cur.execute(
        """
        SELECT id, review_text
        FROM reviews
        WHERE product_id = %s
        ORDER BY id DESC
        """,
        (product_id,)
    )

    reviews = [
        {"id": r[0], "text": r[1]}
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return render_template(
        'product.html',
        product_id=product_id,
        name=name,
        description=description,
        link=link,
        reviews=reviews
    )


@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_product(id):
    page = request.args.get("page", 1)
    q = request.args.get("q", "")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM products WHERE id = %s", (id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        log_event("DELETE_PRODUCT_FAIL", f"Missing product {id}")
        return jsonify({"error": "Produkt nie istnieje"}), 404

    cur.execute("DELETE FROM products WHERE id = %s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    log_event("DELETE_PRODUCT", f"Deleted product {id}")

    return jsonify({
        "redirect": f"/view.html?page={page}&q={q}"
    })


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    page = request.args.get("page", 1)
    q = request.args.get("q", "")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT name, link FROM products WHERE id = %s", (id,))
    product = cur.fetchone()

    if not product:
        cur.close()
        conn.close()
        return "Produkt nie istnieje", 404

    old_name, old_link = product

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_link = request.form.get('link')

        new_description = generate_summary_from_link(new_link)
        new_embedding = model.encode(new_description).tolist()

        cur.execute("""
            UPDATE products
            SET name=%s, link=%s, description=%s, embedding=%s
            WHERE id=%s
        """, (new_name, new_link, new_description, new_embedding, id))

        conn.commit()
        cur.close()
        conn.close()

        log_event("EDIT_PRODUCT", f"{old_name} -> {new_name}")

        return redirect(f"/view.html?page={page}&q={q}")

    cur.close()
    conn.close()
    return render_template('edit.html', id=id, name=old_name, link=old_link, page=page, q=q)



@app.route('/ask.html')
def ask_page():
    return render_template('ask.html')

@app.route('/get_history')
def get_history():
    history = session.get("history", [])
    return jsonify(history)

@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get("question")
    if not question:
        return jsonify({"answer": "", "products": [], "error": "Brak pytania"}), 400

    history = session.get("history", [])


    history.append({"role": "user", "content": question})
    session["history"] = history
    session.modified = True

    query_embedding = model.encode(question).tolist()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.name, p.description, p.link,
       COALESCE(string_agg(r.review_text, '\n'), '') as reviews
FROM products p
LEFT JOIN reviews r ON r.product_id = p.id
GROUP BY p.id, p.name, p.description, p.link
ORDER BY p.embedding <#> %s::vector
LIMIT 5

        """, (query_embedding,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        context = "\n\n".join([
            f"{name}: {desc[:600]}\nOpinie użytkowników: {reviews or 'Brak opinii'}"
            for id, name, desc, link, reviews in rows
        ])

        prompt = f"""
Użytkownik pyta: {question}

Oto produkty z bazy, które mogą pasować (używaj tylko tych!):
{context}

Zasady odpowiedzi:
- opisuj wyłącznie produkty z listy powyżej
- uwzględniaj opinie użytkowników w rekomendacjach
- nie wymyślaj nowych produktów
- jeśli żaden produkt nie pasuje, napisz to
- odpowiedź krótka i konkretna
"""

        messages = [{"role": "system", "content": "Jesteś inteligentnym asystentem produktowym. Odpowiadasz po polsku."}]
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()


        session["history"].append({"role": "assistant", "content": answer})
        session.modified = True

        products_info = []
        answer_lower = answer.lower()
        for pid, name, desc, link, reviews in rows:
            if any(word.lower() in answer_lower for word in name.split()):
                products_info.append({
                    "id": pid,
                    "name": name,
                    "link": link or f"/product/{pid}",
                    "capacity": None,
                    "image_url": "/static/no_image.png"
                })

        log_event("ASK_QUERY", f"Question: '{question}', AI answer: '{answer}'")

        return jsonify({"answer": answer, "products": products_info})

    except Exception as e:
        return jsonify({"answer": f"Błąd: {str(e)}", "products": []})


@app.route('/new_chat')
def new_chat():
    session["history"] = []
    session.modified = True
    return jsonify({"status": "ok"})



@app.route('/logs')
def view_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, action, details, created_at FROM logs ORDER BY created_at DESC LIMIT 500")
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('logs.html', logs=logs)

@app.route('/addReview', methods=['POST'])
def add_review():
    data = request.get_json()
    product_id = data.get('product_id')
    review_text = data.get('review_text')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reviews (product_id, review_text) VALUES (%s, %s) RETURNING id",
        (product_id, review_text)
    )
    review_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    log_event("ADD_REVIEW", f"Review for product_id {product_id}: {review_text}")


    return jsonify({'id': review_id, 'text': review_text})



if __name__ == '__main__':
    app.run(debug=True)