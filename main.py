from flask import Flask, render_template, request, redirect,jsonify
import psycopg2
from sentence_transformers import SentenceTransformer
import re


app = Flask(__name__)
model = SentenceTransformer('all-MiniLM-L6-v2')


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
        embedding vector(384)
    )
""")
conn.commit()
cur.close()
conn.close()

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/add.html', methods=['GET', 'POST'])
def add_products():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        embedding = model.encode(description).tolist()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO products (name, description, embedding) VALUES (%s, %s, %s)",
                    (name, description, embedding))
        conn.commit()
        cur.close()
        conn.close()

        return redirect('/')

    return render_template('add.html')


@app.route('/view.html', methods=['GET', 'POST'])
def view_products():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM products")
    products = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('view.html', products=products)

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
        SELECT name, description
        FROM products
        ORDER BY embedding <#> %s::vector
        LIMIT 5
    """, (query_embedding,))
    rows = cur.fetchall()
    cur.close()
    conn.close()


    context = "\n".join([f"{name}: {desc}" for name, desc in rows])
    prompt = f"""
    Jesteś inteligentnym asystentem produktowym. Odpowiadaj wyłącznie na podstawie podanych produktów.

    Jeśli produkt ma nazwę, użyj jej w odpowiedzi.
    Jeśli nie ma nazwy, możesz odnieść się ogólnie do produktu, np. „drabina o wysokości 4 m”.


Produkty:
{context}

Pytanie użytkownika (po polsku lub w innym języku): {question}

Twoja odpowiedź (tylko po polsku):"""

    #deepseek-r1:1.5b
    import requests
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "deepseek-r1:14b",
        "prompt": prompt,
        "stream": False
    })

    if response.status_code != 200:
        return jsonify({"error": "Błąd komunikacji z deepseek"}), 500

    result = response.json()
    raw_answer = result.get("response", "").strip()
    clean_answer = strip_think_tags(raw_answer)

    return jsonify({
        "answer": clean_answer,
        "used_context": context
    })

@app.route('/ask.html', methods=['GET'])
def ask_page():
    return render_template('ask.html')





#Usuwanie
@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db_connection()
    cur = conn.cursor()


    cur.execute("SELECT id FROM products WHERE id = %s", (id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Produkt nie istnieje"}), 404

    # Usuwanie produktu
    cur.execute("DELETE FROM products WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Produkt usunięty!"}), 200





# Do poprawy
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    conn = get_db_connection()
    cur = conn.cursor()


    cur.execute("SELECT name, description FROM products WHERE id = %s", (id,))
    product = cur.fetchone()

    if not product:
        return "Produkt nie istnieje", 404

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_description = request.form.get('description')


        new_embedding = model.encode(new_description).tolist()


        cur.execute("""
            UPDATE products
            SET name = %s, description = %s, embedding = %s
            WHERE id = %s
        """, (new_name, new_description, new_embedding, id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect('/view.html')  #

    cur.close()
    conn.close()
    return render_template('edit.html', id=id, name=product[0], description=product[1])


if __name__ == '__main__':
    app.run(debug=True)