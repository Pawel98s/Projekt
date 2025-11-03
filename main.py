from flask import Flask, render_template, request, redirect, jsonify
import psycopg2
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import os
import fitz
from bs4 import BeautifulSoup
import requests
import re

app = Flask(__name__)
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
    )
""")
conn.commit()
cur.close()
conn.close()


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
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text.strip()

        else:
            response = requests.get(link)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for script in soup(["script", "style", "noscript"]):
                script.extract()
            text = soup.get_text(separator="\n")
            text = " ".join(text.split())
            return text.strip()
    except Exception as e:
        print(f"Błąd pobierania {link}: {e}")
        return ""


def generate_summary_from_link(link: str) -> str:
    text = extract_text_from_link(link)
    if not text:
        return "Brak dostępnej treści do streszczenia."

    prompt = f"""
    Na podstawie poniższego tekstu wygeneruj szczegółowe streszczenie produktu.
    Upewnij się, że w streszczeniu znajdują się nazwa produktu, typ (np. wózek widłowy) oraz marka.
    Zwróć uwagę, aby cechy techniczne i zalety były jasno opisane.

    {text}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
        return summary
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
        cur.execute("""
            INSERT INTO products (name, description, link, embedding)
            VALUES (%s, %s, %s, %s)
        """, (name, description, link, embedding))
        conn.commit()
        cur.close()
        conn.close()
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

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, link FROM products WHERE id = %s", (id,))
    product = cur.fetchone()
    if not product:
        cur.close()
        conn.close()
        return "Produkt nie istnieje", 404

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_link = request.form.get('link')


        new_description = generate_summary_from_link(new_link)
        new_embedding = model.encode(new_description).tolist()

        cur.execute("""
            UPDATE products
            SET name = %s, link = %s, description = %s, embedding = %s
            WHERE id = %s
        """, (new_name, new_link, new_description, new_embedding, id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/view.html')

    cur.close()
    conn.close()
    return render_template('edit.html', id=id, name=product[0], link=product[1])

@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM products WHERE id = %s", (id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Produkt nie istnieje"}), 404

    cur.execute("DELETE FROM products WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Produkt usunięty!"}), 200


def strip_think_tags(response: str) -> str:
    return re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get("question")
    if not question:
        return jsonify({"error": "Brak pytania"}), 400

    query_embedding = model.encode(question).tolist()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, description, link
        FROM products
        ORDER BY embedding <#> %s::vector
        LIMIT 5
    """, (query_embedding,))
    rows = cur.fetchall()
    cur.close()
    conn.close()


    context = "\n\n".join([f"{name}: {desc[:1000]}" for name, desc, link in rows])

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Jesteś inteligentnym asystentem produktowym. Odpowiadaj po polsku na podstawie kontekstu."},
                {"role": "user", "content": f"Produkty:\n{context}\n\nPytanie: {question}"}
            ],
            temperature=0.4,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"answer": answer, "used_context": context})

@app.route('/ask.html')
def ask_page():
    return render_template('ask.html')


if __name__ == '__main__':
    app.run(debug=True)
