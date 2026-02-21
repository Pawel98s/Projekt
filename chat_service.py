class ChatService:
    def __init__(self, client, embedder, product_repo, logger):
        self.client = client
        self.embedder = embedder
        self.product_repo = product_repo
        self.logger = logger

    def answer(self, question: str, history: list):
        query_embedding = self.embedder.encode(question).tolist()
        rows = self.product_repo.semantic_search_top5(query_embedding)

        context = "\n\n".join([
            f"{name}: {desc[:600]}\nOpinie użytkowników: {reviews or 'Brak opinii'}"
            for pid, name, desc, link, reviews in rows
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

        resp = self.client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            temperature=0.3,
        )
        answer = resp.choices[0].message.content.strip()

        self.logger.log("ASK_QUERY", f"Question: '{question}', AI answer: '{answer}'")
        return answer, rows