import fitz
import requests
from bs4 import BeautifulSoup
import tempfile
import os

class ContentExtractionService:
    def extract_text_from_link(self, link: str) -> str:
        if not link:
            return ""
        try:
            if link.lower().endswith(".pdf"):
                return self._extract_pdf(link)
            return self._extract_html(link)
        except Exception as e:
            print(f"Błąd pobierania {link}: {e}")
            return ""

    def _extract_pdf(self, link: str) -> str:
        r = requests.get(link, timeout=20)
        r.raise_for_status()

        fd, path = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(r.content)
            doc = fitz.open(path)
            text = "".join(page.get_text() for page in doc)
            doc.close()
            return text.strip()
        finally:
            try:
                os.remove(path)
            except:
                pass

    def _extract_html(self, link: str) -> str:
        r = requests.get(link, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = soup.get_text(separator="\n")
        return " ".join(text.split()).strip()