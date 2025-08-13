# app.py
# Smart Hospital API - Minimal Flask Application
# This file contains the entry point for the API and basic route definitions.

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables from .env file (if available)
load_dotenv()

# Create Flask application instance
app = Flask(__name__)

# Enable Cross-Origin Resource Sharing (CORS) for API calls from different domains
CORS(app)

@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
    Returns a JSON object with the API status.
    This is useful for monitoring and verifying that the API is running.
    """
    return {"status": "OK"}, 200

@app.route("/patients", methods=["GET"])
def get_patients():
    """
    Example endpoint to retrieve patient list.
    In a real application, this data would come from a database.
    For now, returning a static example list for demonstration purposes.
    """
    patients = [
        {"id": 1, "name": "John Doe", "room": 101},
        {"id": 2, "name": "Jane Smith", "room": 102}
    ]
    return {"patients": patients}, 200

if __name__ == "__main__":
    # Read the port from environment variables or use default 5000
    port = int(os.getenv("PORT", 5000))

    # Start the Flask development server
    # debug=True is for development only; disable in production
    app.run(host="0.0.0.0", port=port, debug=True)
