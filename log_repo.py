from database_connection import get_db_connection

class LogRepository:
    def __init__(self, cfg):
        self.cfg = cfg

    def add(self, action: str, details: str = ""):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("INSERT INTO logs (action, details) VALUES (%s, %s)", (action, details))
        conn.commit()
        cur.close()
        conn.close()

    def latest(self, limit=500):
        conn = get_db_connection(self.cfg)
        cur = conn.cursor()
        cur.execute("""
            SELECT id,
                   action,
                   details,
                   to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
            FROM logs
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows