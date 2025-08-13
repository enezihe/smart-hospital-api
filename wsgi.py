# wsgi.py  (WSGI entrypoint)
from app import app  # expose the Flask application as "app"

# Do NOT call app.run() when imported by a WSGI server.
# Optionally allow direct run for quick local checks:
if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
