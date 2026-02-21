import math
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