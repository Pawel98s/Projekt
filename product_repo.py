import math
import re
from database_connection import get_db_connection

class ProductRepository:
    def __init__(self, cfg):
        self.cfg = cfg

    def insert(self, name, description, link, embedding):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO products (name, description, link, embedding) VALUES (%s,%s,%s,%s)",
            (name, description, link, embedding)
        )
        conn.commit()
        cur.close()
        conn.close()

    def update(self, product_id, name, link, description, embedding):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("""
            UPDATE products
            SET name=%s, link=%s, description=%s, embedding=%s
            WHERE id=%s
        """, (name, link, description, embedding, product_id))
        conn.commit()
        cur.close()
        conn.close()

    def delete(self, product_id):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
        conn.commit()
        cur.close()
        conn.close()

    def get(self, product_id):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, link FROM products WHERE id=%s", (product_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    def list_paginated_with_reviews(self, page: int, per_page: int, q: str):
        offset = (page - 1) * per_page
        where_clause = ""
        params = []

        if q:
            where_clause = "WHERE p.name ILIKE %s OR p.description ILIKE %s"
            params.extend([f"%{q}%", f"%{q}%"])

        conn = get_db_connection(self.cfg)
        cur = conn.cursor()

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

        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows, total_pages

    def semantic_search_top5(self, query_embedding):
        conn = get_db_connection(self.cfg)
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
        return rows

    def keyword_search_top5_tokens(self, question: str):
        """
        Lepsze wyszukiwanie keywordowe:
        - bierze max 6 tokenów
        - daje scoring (nazwa ważniejsza niż opis)
        - sortuje po trafności
        - zwraca więcej kandydatów (20), żeby LLM mógł odsiać
        """

        def normalize_pl(word: str) -> str:
            for suf in ["ów", "ami", "ach", "owi", "om", "ie", "a", "u", "y", "i", "ę", "ą"]:
                if word.endswith(suf) and len(word) > len(suf) + 3:
                    return word[:-len(suf)]
            return word

        STOPWORDS = {
            "szukam", "szukać", "szukac", "chcę", "chce", "potrzebuję", "potrzebuje",
            "poproszę", "prosze", "proszę", "jaki", "jakie", "jaka", "jaką",
            "do", "na", "w", "z", "i", "czy", "mi", "dla", "co", "cos", "czego",
            "masz", "macie", "jest", "są", "sa", "możesz", "mozna"
        }

        words = re.findall(r"[a-zA-ZąćęłńóśżźĄĆĘŁŃÓŚŻŹ0-9]+", (question or "").lower())
        words = [w for w in words if w not in STOPWORDS and len(w) >= 3]
        words = [normalize_pl(w) for w in words]
        words = words[:6]  # max 6 tokenów

        if not words:
            return []

        where_clauses = []
        where_params = []
        for w in words:
            where_clauses.append("(p.name ILIKE %s OR p.description ILIKE %s)")
            like = f"%{w}%"
            where_params.extend([like, like])

        where_sql = " OR ".join(where_clauses)

        score_parts = []
        score_params = []
        for w in words:
            like = f"%{w}%"
            score_parts.append("((p.name ILIKE %s)::int * 2 + (p.description ILIKE %s)::int)")
            score_params.extend([like, like])

        score_sql = " + ".join(score_parts)

        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute(f"""
            SELECT p.id, p.name, p.description, p.link,
                   COALESCE(string_agg(r.review_text, E'\n'), '') as reviews,
                   ({score_sql}) as score
            FROM products p
            LEFT JOIN reviews r ON r.product_id = p.id
            WHERE {where_sql}
            GROUP BY p.id, p.name, p.description, p.link
            ORDER BY score DESC, p.id DESC
            LIMIT 20
        """, where_params + score_params)

        rows = cur.fetchall()
        cur.close()
        conn.close()

        rows = [(pid, name, desc, link, reviews) for (pid, name, desc, link, reviews, score) in rows]
        return rows

    #######

    def get_by_ids_with_reviews(self, ids):
        if not ids:
            return []


        try:
            ids = [int(x) for x in ids]
        except Exception:
            return []

        conn = get_db_connection(self.cfg)
        cur = conn.cursor()

        cur.execute("""
            SELECT p.id, p.name, p.description, p.link,
                   COALESCE(string_agg(r.review_text, E'\n'), '') as reviews
            FROM products p
            LEFT JOIN reviews r ON r.product_id = p.id
            WHERE p.id = ANY(%s::int[])
            GROUP BY p.id, p.name, p.description, p.link
        """, (ids,))

        rows = cur.fetchall()
        cur.close()
        conn.close()


        order = {pid: i for i, pid in enumerate(ids)}
        rows.sort(key=lambda r: order.get(r[0], 10_000))
        return rows
