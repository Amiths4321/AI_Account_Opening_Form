import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = "change-this-secret-key-in-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB max upload size
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    # ---- Ollama / Qwen2.5-VL settings ----
    # Pointing at a self-hosted Qwen2.5-VL instance on a remote GPU server (no OpenAI/Anthropic
    # API keys involved anywhere in this app — this is the only model call the app makes).
    #
    # On the remote server, Ollama must be started bound to 0.0.0.0 (not the default 127.0.0.1)
    # for this app to reach it over the network, e.g.:
    #     OLLAMA_HOST=0.0.0.0 ollama serve
    # and the model must be pulled there:
    #     ollama pull qwen2.5vl:7b
    #
    # Security note: Ollama has no built-in authentication. Don't expose port 11434 to the open
    # internet — restrict it to known IPs via firewall/security group, or tunnel over SSH
    # (ssh -L 11434:localhost:11434 user@remote-server) and keep OLLAMA_HOST below as localhost.
    OLLAMA_HOST = "http://10.22.39.192:11434"   # <-- replace with your server's address
    OLLAMA_MODEL = "qwen2.5vl:latest"
    OLLAMA_TIMEOUT_SECONDS = 60