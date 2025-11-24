from flask import Flask, render_template, request, redirect, jsonify, session
import psycopg2
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import os
import fitz
from bs4 import BeautifulSoup
import requests
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_key"


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
        cur.execute("INSERT INTO logs (action, details) VALUES (%s, %s)", (action, details))
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
Na podstawie poniższego tekstu wygeneruj szczegółowe streszczenie produktu.
Upewnij się, że w streszczeniu znajdują się nazwa produktu, typ oraz marka.
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
        cur.execute("INSERT INTO products (name, description, link, embedding) VALUES (%s,%s,%s,%s)",
                    (name, description, link, embedding))
        conn.commit()
        cur.close()
        conn.close()

        log_event("ADD_PRODUCT", f"Added product '{name}', link: {link}")
        return redirect('/view.html')

    return render_template('add.html')

@app.route('/view.html')
def view_products():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, link FROM products")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('view.html', products=products)

@app.route('/product/<int:product_id>')
def product_page(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, description, link FROM products WHERE id=%s", (product_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return "Produkt nie znaleziony", 404
    name, description, link = row
    return render_template('product.html', name=name, description=description, link=link)


@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db_connection()
    cur = conn.cursor()


    cur.execute("SELECT name FROM products WHERE id = %s", (id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        log_event("DELETE_PRODUCT_FAIL", f"Tried to delete missing product ID {id}")
        return jsonify({"error": "Produkt nie istnieje"}), 404

    product_name = row[0]

    cur.execute("DELETE FROM products WHERE id = %s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    log_event("DELETE_PRODUCT", f"Deleted product '{product_name}' (ID {id})")

    return jsonify({"message": "Produkt usunięty!"}), 200

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    conn = get_db_connection()
    cur = conn.cursor()


    cur.execute("SELECT name, link FROM products WHERE id = %s", (id,))
    product = cur.fetchone()

    if not product:
        cur.close()
        conn.close()

        log_event("EDIT_PRODUCT_FAIL", f"Tried to edit missing product ID {id}")

        return "Produkt nie istnieje", 404

    old_name, old_link = product

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_link = request.form.get('link')

        new_description = generate_summary_from_link(new_link)

        new_embedding = model.encode(new_description).tolist()

        cur.execute("""
            UPDATE products
            SET name = %s,
                link = %s,
                description = %s,
                embedding = %s
            WHERE id = %s
        """, (new_name, new_link, new_description, new_embedding, id))

        conn.commit()
        cur.close()
        conn.close()

        log_event(
            "EDIT_PRODUCT",
            f"Edited product ID {id}. Old name: '{old_name}', New name: '{new_name}', Old link: '{old_link}', New link: '{new_link}'"
        )

        return redirect('/view.html')

    cur.close()
    conn.close()

    return render_template('edit.html', id=id, name=old_name, link=old_link)




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
        return jsonify({"error": "Brak pytania"}), 400

    history = session.get("history", [])


    query_embedding = model.encode(question).tolist()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, description, link
        FROM products
        ORDER BY embedding <#> %s::vector
        LIMIT 5
    """, (query_embedding,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    context = "\n\n".join([f"{name}: {desc[:600]}" for id, name, desc, link in rows])


    prompt = f"""
Użytkownik pyta: {question}

Oto produkty z bazy, które mogą pasować (używaj tylko tych!):
{context}

Zasady odpowiedzi:
- opisuj wyłącznie produkty z listy powyżej
- nie wymyślaj nowych produktów
- jeśli żaden produkt nie pasuje, napisz to
- odpowiedź krótka i konkretna
"""

    messages = [{"role": "system", "content": "Jesteś inteligentnym asystentem produktowym. Odpowiadasz po polsku."}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()


        session["history"].append({"role": "user", "content": question})
        session["history"].append({"role": "assistant", "content": answer})
        session.modified = True


        products_info = []
        answer_lower = answer.lower()
        for pid, name, desc, link in rows:
            if any(word.lower() in answer_lower for word in name.split()):
                products_info.append({
                    "id": pid,
                    "name": name,
                    "link": link or f"/product/{pid}",
                    "capacity": None,
                    "image_url": "/static/no_image.png"
                })

        log_event("ASK_QUERY", f"Question: '{question}', AI answer: '{answer}'")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"answer": answer, "products": products_info})

@app.route('/new_chat')
def new_chat():
    session["history"] = []
    session.modified = True
    return jsonify({"status": "ok"})



@app.route('/logs.html')
def view_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, action, details, created_at FROM logs ORDER BY created_at DESC LIMIT 500")
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('logs.html', logs=logs)



if __name__ == '__main__':
    app.run(debug=True)
