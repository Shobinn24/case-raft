import sys

from dotenv import load_dotenv

load_dotenv()

print("[run.py] Starting app factory...", file=sys.stderr, flush=True)
from app import create_app

app = create_app()
print(f"[run.py] Flask app created OK", file=sys.stderr, flush=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
