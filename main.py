from flask import Flask
from config import Config

from database_connection import init_db
from llm import create_openai_client
from embedding import create_embedding_model

from product_repo import ProductRepository
from review_repo import ReviewRepository
from log_repo import LogRepository

from content_extraction_service import ContentExtractionService
from product_description_service import ProductDescriptionService
from event_logger import EventLogger
from chat_service import ChatService

from pages import pages_bp, register_pages
from api import api_bp, register_api

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = app.config["SECRET_KEY"]

    cfg = Config

    init_db(cfg)

    client = create_openai_client(cfg)
    embedder = create_embedding_model(cfg)

    product_repo = ProductRepository(cfg)
    review_repo = ReviewRepository(cfg)
    log_repo = LogRepository(cfg)

    logger = EventLogger(log_repo)
    extractor = ContentExtractionService()
    summarizer = ProductDescriptionService(client)
    chat_service = ChatService(client, embedder, product_repo, logger)

    deps = {
        "product_repo": product_repo,
        "review_repo": review_repo,
        "log_repo": log_repo,
        "logger": logger,
        "extractor": extractor,
        "summarizer": summarizer,
        "embedder": embedder,
        "chat_service": chat_service,
    }

    register_pages(pages_bp, deps)
    register_api(api_bp, deps)

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)