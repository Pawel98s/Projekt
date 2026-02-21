from database_connection import get_db_connection

class ReviewRepository:
    def __init__(self, cfg):
        self.cfg = cfg

    def add(self, product_id, review_text):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reviews (product_id, review_text) VALUES (%s, %s) RETURNING id",
            (product_id, review_text)
        )
        review_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return review_id

    def delete(self, review_id):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("DELETE FROM reviews WHERE id=%s", (review_id,))
        conn.commit()
        cur.close()
        conn.close()

    def update(self, review_id, review_text):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("UPDATE reviews SET review_text=%s WHERE id=%s", (review_text, review_id))
        conn.commit()
        cur.close()
        conn.close()

    def list_for_product(self, product_id):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, review_text
            FROM reviews
            WHERE product_id=%s
            ORDER BY id DESC
        """, (product_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "text": r[1]} for r in rows]

    def get_text(self, review_id):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("SELECT review_text FROM reviews WHERE id=%s", (review_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None