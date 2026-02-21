class ProductDescriptionService:
    def __init__(self, client):
        self.client = client

    def summarize_markdown(self, source_text: str) -> str:
        if not source_text:
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
{source_text}
"""
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"Błąd generowania streszczenia: {e}")
            return "Błąd podczas generowania streszczenia."