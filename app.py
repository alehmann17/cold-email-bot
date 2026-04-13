import streamlit as st
import pandas as pd
import base64
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from gmail_auth import get_gmail_service
from email_drafter import draft_email, scrape_website, draft_linkedin_message, load_research

CONFIG_FILE = "sender_config.json"
RESEARCH_FILE = "company-research.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + underscore column names, then map common variants to standard names."""
    df.columns = [c.lower().strip().replace("'", "").replace(" ", "_") for c in df.columns]
    renames = {
        "email_address": "email",
        "full_name": "name",
        "linkedin_url": "linkedin",
        "company_name": "company",
    }
    return df.rename(columns={k: v for k, v in renames.items() if k in df.columns})


def build_html_email(body: str, name: str, linkedin: str, website: str, phone: str) -> str:
    paragraphs = "".join(
        f"<p>{line}</p>" if line.strip() else "<br>" for line in body.split("\n")
    )
    links = []
    if linkedin:
        links.append(f'<a href="{linkedin}" style="color:#0077B5;text-decoration:none;">LinkedIn</a>')
    if website:
        links.append(f'<a href="{website}" style="color:#333;text-decoration:none;">Website</a>')
    links_html = " &nbsp;|&nbsp; ".join(links)
    phone_html = f'<p style="margin:2px 0 0 0;font-size:13px;">{phone}</p>' if phone else ""
    sig_links = f"<p style='margin:4px 0 0 0;font-size:13px;'>{links_html}</p>" if links_html else ""
    return f"""<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:600px;">
{paragraphs}
<br>
<p style="margin:0;">Best,<br><strong>{name}</strong></p>
{sig_links}{phone_html}
</body></html>"""


def advance(clear_draft=True):
    if clear_draft:
        st.session_state.pop("draft", None)
        st.session_state.pop("linkedin_draft", None)
    st.session_state.current_index += 1
    st.rerun()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Cold Email Bot", page_icon="📧")
st.title("📧 Cold Email Bot")

# Load pre-built research once per session
if "research" not in st.session_state:
    st.session_state.research = load_research(RESEARCH_FILE)

cfg = load_config()

# --- Sidebar ---
with st.sidebar:
    st.header("Your Info")
    sender_name       = st.text_input("Your name",       value=cfg.get("sender_name", "Andrew"))
    sender_background = st.text_area(
        "Your CV",
        value=cfg.get("sender_background", ""),
        placeholder=(
            "Paste your full CV or detailed bio here.\n\n"
            "The more specific the better — real project names, what you actually did, "
            "findings, tools used, institutions. This is what the email will draw from."
        ),
        height=300,
    )
    sender_linkedin = st.text_input("LinkedIn URL",      value=cfg.get("sender_linkedin", ""))
    sender_website  = st.text_input("Personal website",  value=cfg.get("sender_website", ""))
    sender_phone    = st.text_input("Phone number",      value=cfg.get("sender_phone", ""))
    anthropic_key   = st.text_input("Anthropic API Key", value=cfg.get("anthropic_key", ""), type="password")

    if st.button("💾 Save Info"):
        save_config({
            "sender_name":       sender_name,
            "sender_background": sender_background,
            "sender_linkedin":   sender_linkedin,
            "sender_website":    sender_website,
            "sender_phone":      sender_phone,
            "anthropic_key":     anthropic_key,
        })
        st.success("Saved!")

    st.markdown("---")
    st.caption("credentials.json must be in the project folder.")
    research_count = len(st.session_state.get("research", {}))
    if research_count:
        st.success(f"📊 Research loaded: {research_count} companies")
    else:
        st.info("No company-research.json — will scrape websites live.")

# --- File upload ---
st.header("1. Upload your company list")
uploaded_file = st.file_uploader("Upload CSV (columns: company, website, email)", type="csv")

if not uploaded_file:
    st.stop()

df = normalize_columns(pd.read_csv(uploaded_file))
st.dataframe(df)

# Reset progress when a new file is uploaded
if st.session_state.get("last_uploaded_file") != uploaded_file.name:
    st.session_state.current_index = 0
    st.session_state.last_uploaded_file = uploaded_file.name
    st.session_state.pop("draft", None)
    st.session_state.pop("linkedin_draft", None)

st.session_state.setdefault("current_index", 0)
st.session_state.setdefault("gmail_service", None)

# --- Gmail auth ---
st.header("2. Review & Send")

if st.session_state.gmail_service is None:
    if st.button("🔐 Connect Gmail"):
        with st.spinner("Opening browser for Gmail auth..."):
            st.session_state.gmail_service = get_gmail_service()
        st.success("Gmail connected!")
    st.stop()

# --- Main loop ---
idx = st.session_state.current_index

if idx >= len(df):
    st.success("🎉 All companies processed!")
    st.stop()

row   = df.iloc[idx]
email = row.get("email", "")
company = str(row.get("company", "")).strip()
website = str(row.get("website", "")).strip()

# Auto-skip rows with no email
if pd.isna(email) or str(email).strip() == "":
    st.warning(f"**{company}** has no email — skipping.")
    st.session_state.current_index += 1
    st.rerun()

st.subheader(f"Company {idx + 1} of {len(df)}: {company}")

linkedin_url = str(row.get("linkedin", "")) if not pd.isna(row.get("linkedin", "")) else ""
info_parts = [f"**Email:** {email}", f"**Website:** {website}"]
if linkedin_url:
    info_parts.append(f"[LinkedIn]({linkedin_url})")
st.write(" | ".join(info_parts))

# --- Draft button ---
if st.button("✍️ Draft Messages"):
    if not anthropic_key:
        st.error("Enter your Anthropic API key in the sidebar.")
    elif not sender_background:
        st.error("Paste your CV in the sidebar first.")
    else:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        with st.spinner("Drafting..."):
            row_dict = {k.lower().replace("'", "").replace(" ", "_"): v for k, v in row.to_dict().items()}
            research_entry = st.session_state.research.get(company)
            website_content = (
                "" if (research_entry or row_dict.get("what_they_do"))
                else scrape_website(website)
            )
            st.session_state.draft = draft_email(
                company, website, email, website_content,
                sender_name, sender_background, sender_linkedin, sender_website,
                research=research_entry, row=row_dict,
            )
            st.session_state.linkedin_draft = draft_linkedin_message(
                company, website_content, sender_name, sender_background,
                sender_phone=sender_phone, sender_website=sender_website,
                research=research_entry, row=row_dict,
            )

# --- Draft editor ---
if "draft" in st.session_state:
    st.markdown("### 📧 Email")
    lines = st.session_state.draft.strip().split("\n", 2)
    subject_val = lines[0].replace("Subject:", "").strip() if lines else ""
    body_val    = "\n".join(lines[2:]).strip() if len(lines) > 2 else st.session_state.draft

    subject      = st.text_input("Subject", value=subject_val)
    body_edited  = st.text_area("Email body", value=body_val, height=250)

    if "[FOUNDER NAME NEEDED]" in body_edited or "[FOUNDER NAME NEEDED]" in subject:
        st.warning("⚠️ Fill in the founder name before sending.")

    st.caption("Signature preview:")
    sig_links = " | ".join(
        f"[{label}]({url})"
        for label, url in [("LinkedIn", sender_linkedin), ("Website", sender_website)]
        if url
    )
    st.markdown(f"Best,  \n**{sender_name}**  \n{sig_links}")

    st.markdown("### 💼 LinkedIn Message")
    st.caption("Copy and paste into LinkedIn (300 char limit)")
    linkedin_edited = st.text_area(
        "LinkedIn message",
        value=st.session_state.get("linkedin_draft", ""),
        height=120,
    )
    if st.button("📋 Copy to clipboard"):
        st.code(linkedin_edited)
        st.info("Select all and copy the text above.")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Send Email & Next"):
            msg = MIMEMultipart("alternative")
            msg["to"]      = str(email)
            msg["subject"] = subject
            html_body = build_html_email(body_edited, sender_name, sender_linkedin, sender_website, sender_phone)
            msg.attach(MIMEText(body_edited, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            st.session_state.gmail_service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            st.success(f"Sent to {email}!")
            advance()

    with col2:
        if st.button("⏭️ Skip"):
            advance()
