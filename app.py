import os
import sqlite3
import hashlib
import uuid
from datetime import date
from io import BytesIO

from flask import (Flask, render_template, request, redirect,
                   url_for, send_file, flash)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "student-secret-key")

# Password needed to generate certificates (change it on Render -> Environment)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DB_NAME = "certificates.db"


# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            cert_id    TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            course     TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            issuer     TEXT NOT NULL,
            hash       TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ---------- Helpers ----------
def make_hash(cert_id, name, course, issue_date, issuer):
    """SHA-256 fingerprint of the certificate data."""
    text = "|".join([cert_id, name, course, issue_date, issuer])
    return hashlib.sha256(text.encode()).hexdigest()


def get_cert(cert_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM certificates WHERE cert_id = ?",
                       (cert_id,)).fetchone()
    conn.close()
    return row


def build_pdf(cert, verify_url):
    buf = BytesIO()
    w, h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(w, h))

    # border
    c.setStrokeColor(HexColor("#1f3a5f"))
    c.setLineWidth(6)
    c.rect(20, 20, w - 40, h - 40)
    c.setLineWidth(1.5)
    c.rect(32, 32, w - 64, h - 64)

    c.setFillColor(HexColor("#1f3a5f"))
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(w / 2, h - 120, "CERTIFICATE OF COMPLETION")

    c.setFillColor(HexColor("#333333"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(w / 2, h - 175, "This is to certify that")

    c.setFillColor(HexColor("#b8860b"))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(w / 2, h - 235, cert["name"])

    c.setFillColor(HexColor("#333333"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(w / 2, h - 285, "has successfully completed the course")

    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(w / 2, h - 330, cert["course"])

    c.setFont("Helvetica", 14)
    c.drawString(70, 110, "Date: " + cert["issue_date"])
    c.drawRightString(w - 70, 110, "Issued by: " + cert["issuer"])

    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, 75, "Certificate ID: " + cert["cert_id"])
    c.drawCentredString(w / 2, 60, "Verify at: " + verify_url)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["GET", "POST"])
def generate():
    if request.method == "POST":
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        issuer = request.form.get("issuer", "").strip()
        issue_date = request.form.get("issue_date") or str(date.today())

        if password != ADMIN_PASSWORD:
            flash("Wrong admin password.", "error")
            return render_template("generate.html")
        if not name or not course or not issuer:
            flash("Please fill all fields.", "error")
            return render_template("generate.html")

        cert_id = "CERT-" + uuid.uuid4().hex[:8].upper()
        cert_hash = make_hash(cert_id, name, course, issue_date, issuer)

        conn = get_db()
        conn.execute("INSERT INTO certificates VALUES (?,?,?,?,?,?)",
                     (cert_id, name, course, issue_date, issuer, cert_hash))
        conn.commit()
        conn.close()
        return redirect(url_for("success", cert_id=cert_id))

    return render_template("generate.html")


@app.route("/success/<cert_id>")
def success(cert_id):
    cert = get_cert(cert_id)
    if not cert:
        return redirect(url_for("index"))
    return render_template("success.html", cert=cert)


@app.route("/download/<cert_id>")
def download(cert_id):
    cert = get_cert(cert_id)
    if not cert:
        flash("Certificate not found.", "error")
        return redirect(url_for("index"))
    verify_url = url_for("verify", id=cert_id, _external=True)
    pdf = build_pdf(cert, verify_url)
    return send_file(pdf, mimetype="application/pdf",
                     as_attachment=True, download_name=cert_id + ".pdf")


@app.route("/verify")
def verify():
    cert_id = request.args.get("id", "").strip().upper()
    result = None
    cert = None
    if cert_id:
        cert = get_cert(cert_id)
        if cert is None:
            result = "not_found"
        else:
            new_hash = make_hash(cert["cert_id"], cert["name"], cert["course"],
                                 cert["issue_date"], cert["issuer"])
            result = "valid" if new_hash == cert["hash"] else "tampered"
    return render_template("verify.html", cert_id=cert_id,
                           result=result, cert=cert)


if __name__ == "__main__":
    app.run(debug=True)
