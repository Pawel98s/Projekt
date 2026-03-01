import json
import re


class ChatService:
    def __init__(self, client, embedder, product_repo, logger):
        self.client = client
        self.embedder = embedder
        self.product_repo = product_repo
        self.logger = logger

    def answer(self, question: str, history: list, last_product_ids=None):
        question = (question or "").strip()
        last_product_ids = last_product_ids or []

        if self._is_follow_up(question) and last_product_ids:
            rows = self.product_repo.get_by_ids_with_reviews(last_product_ids)
        else:
            rows = self.product_repo.keyword_search_top5_tokens(question)
            if not rows:
                query_embedding = self.embedder.encode(f"Szukam produktu: {question}").tolist()
                rows = self.product_repo.semantic_search_top5(query_embedding)

        context = "\n\n".join([
            f"ID:{pid}\nNazwa:{name}\nOpis:{(desc or '')[:600]}\nOpinie:{reviews or 'Brak opinii'}"
            for pid, name, desc, link, reviews in rows
        ])

        prompt = f"""
Użytkownik pyta: {question}

Oto produkty z bazy (możesz używać WYŁĄCZNIE tych danych):
{context}

Zasady:
- wybierz tylko produkty, które faktycznie pasują do pytania
- uwzględniaj opinie użytkowników w rekomendacjach
- odpowiedz zwięźle i konkretnie (Markdown, wypunktowania)
- nie wymieniaj produktów niepasujących
- nie wymyślaj nowych produktów
- nie pokazuj ID produktu w odpowiedzi
- jeśli nic nie pasuje, napisz że brak dopasowania

Na końcu ZAWSZE zwróć JSON w osobnej linii w formacie:
{{"product_ids":[ID1,ID2,...]}}

Jeśli nic nie pasuje:
{{"product_ids":[]}}
""".strip()

        messages = [{"role": "system", "content": "Jesteś inteligentnym asystentem produktowym. Odpowiadasz po polsku."}]
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        resp = self.client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            temperature=0.3,
        )

        raw_answer = (resp.choices[0].message.content or "").strip()

        match = re.search(r'(\{"product_ids"\s*:\s*\[.*?\]\s*\})\s*$', raw_answer, re.DOTALL)

        product_ids = []
        if match:
            try:
                data = json.loads(match.group(1))
                product_ids = data.get("product_ids", [])
            except Exception:
                product_ids = []

        if product_ids:
            rows = [r for r in rows if r[0] in product_ids]
        else:
            rows = []

        new_last_ids = [r[0] for r in rows]

        answer = re.sub(r'\{"product_ids"\s*:\s*\[.*?\]\s*\}\s*$', '', raw_answer, flags=re.DOTALL).strip()

        self.logger.log("ASK_QUERY", f"Question: '{question}', AI answer: '{answer}'")
        return answer, rows, new_last_ids

    def _is_follow_up(self, question: str) -> bool:
        q = (question or "").lower().strip()
        if len(q) <= 25:
            return True
        phrases = [
            "mam cerę", "mam cere", "moja cera",
            "sucha", "suchą", "tłusta", "tlusta", "mieszana", "wrażliwa",
            "który", "która", "które", "lepszy", "lepsza",
            "będzie dla mnie", "bedzie dla mnie", "dla mnie",
            "ten czy", "ta czy", "to czy",
            "a co", "a coś", "a cos", "a ten", "a ta", "a to",
            "porównaj", "porownaj"
        ]
        return any(p in q for p in phrases)