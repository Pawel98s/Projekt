from openai import OpenAI

def create_openai_client(cfg):
    return OpenAI(api_key=cfg.OPENAI_API_KEY)