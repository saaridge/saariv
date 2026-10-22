"""Run the native local demo with isolated accounts, stories and simulated coins.

Usage: .venv-rag/bin/python run_mock.py
Requires a running local PostgreSQL server and a role allowed to create the demo DB.
"""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from marketplace.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="postgresql+psycopg://saariv_dev@127.0.0.1:55432/saariv_marketplace_mock")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--init-only", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535.")
    root = Path(__file__).resolve().parent
    os.chdir(root)
    env = os.environ.copy()
    for name in ("OPENAI_API_KEY", "EMBEDDING_API_KEY", "COHERE_API_KEY", "CHAT_API_KEY", "MAIL_USERNAME", "MAIL_PASSWORD",
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET",
            "FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET", "FACEBOOK_GRAPH_VERSION", "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"):
        env.pop(name, None)
    secret_path = root / ".local-dev" / "mock-session.secret"
    secret_path.parent.mkdir(exist_ok=True)
    try:
        fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_hex(32))
    env.update(MARKETPLACE_ENABLED="true", MARKETPLACE_MOCK_MODE="true", MARKETPLACE_ENV="development",
        MARKETPLACE_PUBLIC_BASE_URL=f"http://127.0.0.1:{args.port}", DATABASE_URL=args.database_url,
        FLASK_SECRET_KEY=secret_path.read_text().strip(), FLASK_SKIP_DOTENV="1", EMBEDDING_PROVIDER="none", CHAT_PROVIDER="extractive",
        KNOWLEDGE_DIR=str(root / ".local-dev" / "mock-knowledge"))
    Settings.from_mapping({}, environ=env)  # Validate isolation before any connection.
    os.environ.clear()
    os.environ.update(env)
    url = make_url(args.database_url)
    connection = {"host": url.host, "port": url.port or 5432, "user": url.username,
        "password": url.password, "dbname": "postgres", "connect_timeout": 5}
    with psycopg.connect(**{key: value for key, value in connection.items() if value is not None}, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
    subprocess.run([sys.executable, "-m", "marketplace.mock", "init"], env=env, check=True)
    if not args.init_only:
        print(f"Saariv local demo: http://127.0.0.1:{args.port} — simulated coins only.", flush=True)
        os.execve(sys.executable, [sys.executable, "-m", "flask", "--app", "app", "run", "--host", "127.0.0.1",
            "--port", str(args.port), "--no-debugger", "--no-reload"], env)


if __name__ == "__main__":
    main()
