from sentence_transformers import SentenceTransformer

def create_embedding_model(cfg):
    return SentenceTransformer(cfg.EMBEDDING_MODEL)

def embed_text(embedder, text: str):
    return embedder.encode(text).tolist()