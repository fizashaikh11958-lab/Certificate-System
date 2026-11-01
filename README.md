# Digital Certificate Generation and Verification System

Flask + SQLite + ReportLab. Generates PDF certificates with a unique ID and a SHA-256 hash, and verifies them by ID.

## Run locally
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000

## Deploy on Render
1. Push this folder to a GitHub repo.
2. Render -> New -> Web Service -> connect the repo.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. Environment variable: `ADMIN_PASSWORD` = your own password.
