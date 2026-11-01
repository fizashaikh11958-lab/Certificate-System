import os
import sqlite3
import hashlib
import uuid
from datetime import date
from io import BytesIO

import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

st.set_page_config(page_title="Digital Certificate System", page_icon="🎓")

DB_NAME = "certificates.db"

# Admin password: set ADMIN_PASSWORD in Streamlit Cloud -> Settings -> Secrets
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


# ---------- Database ----------
def get_db():
    return sqlite3.connect(DB_NAME)


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
    row = conn.execute(
        "SELECT cert_id, name, course, issue_date, issuer, hash "
        "FROM certificates WHERE cert_id = ?", (cert_id,)).fetchone()
    conn.close()
    return row


def build_pdf(cert_id, name, course, issue_date, issuer):
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
    c.drawCentredString(w / 2, h - 235, name)

    c.setFillColor(HexColor("#333333"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(w / 2, h - 285, "has successfully completed the course")

    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(w / 2, h - 330, course)

    c.setFont("Helvetica", 14)
    c.drawString(70, 110, "Date: " + issue_date)
    c.drawRightString(w - 70, 110, "Issued by: " + issuer)

    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, 75, "Certificate ID: " + cert_id)
    c.drawCentredString(w / 2, 60,
                        "Verify this certificate using its ID on the Digital Certificate System")

    c.showPage()
    c.save()
    return buf.getvalue()


# ---------- UI ----------
st.title("🎓 Digital Certificate System")
st.write("Generate certificates as PDF and verify them using a unique Certificate ID.")

tab1, tab2 = st.tabs(["Generate Certificate", "Verify Certificate"])

# ----- Generate tab -----
with tab1:
    with st.form("generate_form"):
        password = st.text_input("Admin Password", type="password")
        name = st.text_input("Student Name")
        course = st.text_input("Course Name")
        issuer = st.text_input("Issued By (Organization)")
        issue_date = st.date_input("Issue Date", value=date.today())
        submitted = st.form_submit_button("Generate")

    if submitted:
        if password != ADMIN_PASSWORD:
            st.error("Wrong admin password.")
        elif not name.strip() or not course.strip() or not issuer.strip():
            st.error("Please fill all fields.")
        else:
            cert_id = "CERT-" + uuid.uuid4().hex[:8].upper()
            date_text = str(issue_date)
            cert_hash = make_hash(cert_id, name.strip(), course.strip(),
                                  date_text, issuer.strip())
            conn = get_db()
            conn.execute("INSERT INTO certificates VALUES (?,?,?,?,?,?)",
                         (cert_id, name.strip(), course.strip(),
                          date_text, issuer.strip(), cert_hash))
            conn.commit()
            conn.close()
            st.session_state["last_cert"] = cert_id

    # show the last generated certificate (stays visible after download click)
    last_id = st.session_state.get("last_cert")
    if last_id:
        row = get_cert(last_id)
        if row:
            st.success("Certificate generated!")
            st.markdown("**Certificate ID:** `" + row[0] + "`")
            st.write("Name:", row[1])
            st.write("Course:", row[2])
            st.write("Date:", row[3])
            st.write("Issued By:", row[4])
            pdf_bytes = build_pdf(row[0], row[1], row[2], row[3], row[4])
            st.download_button("Download PDF", data=pdf_bytes,
                               file_name=row[0] + ".pdf",
                               mime="application/pdf")

# ----- Verify tab -----
with tab2:
    default_id = st.query_params.get("id", "")
    check_id = st.text_input("Certificate ID", value=default_id,
                             placeholder="CERT-XXXXXXXX")
    if st.button("Verify"):
        check_id = check_id.strip().upper()
        if not check_id:
            st.warning("Please enter a Certificate ID.")
        else:
            row = get_cert(check_id)
            if row is None:
                st.error("❌ Certificate not found.")
            else:
                new_hash = make_hash(row[0], row[1], row[2], row[3], row[4])
                if new_hash == row[5]:
                    st.success("✅ Certificate is VALID")
                    st.write("Name:", row[1])
                    st.write("Course:", row[2])
                    st.write("Date:", row[3])
                    st.write("Issued By:", row[4])
                else:
                    st.error("❌ Record has been modified. Certificate is NOT valid.")
