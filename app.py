import streamlit as st
import pandas as pd
import base64
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from gmail_auth import get_gmail_service
from email_drafter import draft_email, scrape_website, draft_linkedin_message, extract_founder_name, founder_name_from_email, load_research

CONFIG_FILE = "sender_config.json"
RESEARCH_FILE = "company-research.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f)

def build_html_email(body_text, sender_name, sender_linkedin, sender_website, sender_phone):
    paragraphs = "".join(f"<p>{line}</p>" if line.strip() else "<br>" for line in body_text.split('\n'))
    links = []
    if sender_linkedin:
        links.append(f'<a href="{sender_linkedin}" style="color:#0077B5;text-decoration:none;">LinkedIn</a>')
    if sender_website:
        links.append(f'<a href="{sender_website}" style="color:#333;text-decoration:none;">Website</a>')
    links_html = " &nbsp;|&nbsp; ".join(links)
    phone_html = f'<p style="margin:2px 0 0 0;font-size:13px;">{sender_phone}</p>' if sender_phone else ""
    return f"""
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:600px;">
{paragraphs}
<br>
<p style="margin:0;">Best,<br><strong>{sender_name}</strong></p>
{"<p style='margin:4px 0 0 0;font-size:13px;'>" + links_html + "</p>" if links_html else ""}{phone_html}
</body></html>
"""

st.set_page_config(page_title="Cold Email Bot", page_icon="📧")
st.title("📧 Cold Email Bot")

# Load research file if present
if "research" not in st.session_state:
    st.session_state.research = load_research(RESEARCH_FILE)

cfg = load_config()

with st.sidebar:
    st.header("Your Info")
    sender_name = st.text_input("Your name", value=cfg.get("sender_name", "Andrew"))
    sender_background = st.text_area(
        "Your CV",
        value=cfg.get("sender_background", ""),
        placeholder=(
            "Paste your full CV or detailed bio here.\n\n"
            "The more specific the better — real project names, what you actually did, "
            "findings, tools used, institutions. This is what the email will draw from. "
            "Vague summaries produce vague emails."
        ),
        height=300,
    )
    sender_linkedin = st.text_input("LinkedIn URL", value=cfg.get("sender_linkedin", ""))
    sender_website = st.text_input("Personal website", value=cfg.get("sender_website", ""))
    sender_phone = st.text_input("Phone number", value=cfg.get("sender_phone", ""))
    anthropic_key = st.text_input("Anthropic API Key", value=cfg.get("anthropic_key", ""), type="password")

    if st.button("💾 Save Info"):
        save_config({
            "sender_name": sender_name,
            "sender_background": sender_background,
            "sender_linkedin": sender_linkedin,
            "sender_website": sender_website,
            "sender_phone": sender_phone,
            "anthropic_key": anthropic_key,
        })
        st.success("Saved!")
    st.markdown("---")
    st.caption("credentials.json must be in the project folder.")
    research_count = len(st.session_state.get("research", {}))
    if research_count:
        st.success(f"📊 Research loaded: {research_count} companies")
    else:
        st.info("No company-research.json found — will scrape websites instead")

st.header("1. Upload your company list")
uploaded_file = st.file_uploader("Upload CSV (columns: company, website, email)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = [c.lower().strip().replace("'", "").replace(" ", "_") for c in df.columns]
    # Normalize common column name variants
    col_map = {}
    for c in df.columns:
        if c in ('email_address',): col_map[c] = 'email'
        elif c in ('full_name',): col_map[c] = 'name'
        elif c in ('linkedin_url',): col_map[c] = 'linkedin'
    df.rename(columns=col_map, inplace=True)
    st.dataframe(df)

    st.header("2. Review & Send")

    # Reset index when a new file is uploaded
    if "last_uploaded_file" not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
        st.session_state.current_index = 0
        st.session_state.last_uploaded_file = uploaded_file.name
        st.session_state.pop("draft", None)
        st.session_state.pop("linkedin_draft", None)

    if "current_index" not in st.session_state:
        st.session_state.current_index = 0
    if "gmail_service" not in st.session_state:
        st.session_state.gmail_service = None

    if st.session_state.gmail_service is None:
        if st.button("🔐 Connect Gmail"):
            with st.spinner("Opening browser for Gmail auth..."):
                st.session_state.gmail_service = get_gmail_service()
            st.success("Gmail connected!")

    if st.session_state.gmail_service:
        idx = st.session_state.current_index
        if idx < len(df):
            row = df.iloc[idx]
            company = row['company']
            website = row['website']
            email = row.get('email')

            if pd.isna(email) or str(email).strip() == '':
                st.warning(f"**{company}** has no email — skipping.")
                st.session_state.current_index += 1
                st.rerun()

            st.subheader(f"Company {idx+1} of {len(df)}: {company}")
            linkedin_url = row.get('linkedin', '') if hasattr(row, 'get') else ''
            if pd.isna(linkedin_url): linkedin_url = ''
            info_parts = [f"**Email:** {email}", f"**Website:** {website}"]
            if linkedin_url:
                info_parts.append(f"[LinkedIn]({linkedin_url})")
            st.write(" | ".join(info_parts))

            if st.button("✍️ Draft Messages"):
                if not anthropic_key:
                    st.error("Enter your Anthropic API key in the sidebar.")
                elif not sender_background:
                    st.error("Paste your CV in the sidebar — the email needs real details to draw from.")
                else:
                    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
                    with st.spinner("Drafting messages..."):
                        research_entry = st.session_state.research.get(company)
                        row_dict = row.to_dict()
                        for k in list(row_dict.keys()):
                            norm = k.lower().replace("'", "").replace(" ", "_")
                            row_dict[norm] = row_dict[k]
                        content = scrape_website(website) if not research_entry and not row_dict.get("what_they_do") else ""
                        draft = draft_email(company, website, email, content,
                                            sender_name, sender_background,
                                            sender_linkedin, sender_website,
                                            research=research_entry, row=row_dict)
                        linkedin_msg = draft_linkedin_message(company, content,
                                            sender_name, sender_background,
                                            sender_phone=sender_phone, sender_website=sender_website,
                                            research=research_entry, row=row_dict)
                    st.session_state.draft = draft
                    st.session_state.linkedin_draft = linkedin_msg

            if "draft" in st.session_state:
                st.markdown("### 📧 Email")
                lines = st.session_state.draft.strip().split('\n', 2)
                subject_line = lines[0].replace("Subject:", "").strip() if lines else ""
                body = '\n'.join(lines[2:]).strip() if len(lines) > 2 else st.session_state.draft

                subject = st.text_input("Subject", value=subject_line)
                body_edited = st.text_area("Email body", value=body, height=250)
                if "[FOUNDER NAME NEEDED]" in body_edited or "[FOUNDER NAME NEEDED]" in subject:
                    st.warning("⚠️ Founder name not found — fill it in before sending.")

                st.caption("Signature preview:")
                sig_links = []
                if sender_linkedin:
                    sig_links.append(f"[LinkedIn]({sender_linkedin})")
                if sender_website:
                    sig_links.append(f"[Website]({sender_website})")
                st.markdown(f"Best,  \n**{sender_name}**  \n{' | '.join(sig_links)}")

                st.markdown("### 💼 LinkedIn Message")
                st.caption("Copy and paste this into LinkedIn (300 char limit)")
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
                        msg['to'] = email
                        msg['subject'] = subject
                        html_content = build_html_email(body_edited, sender_name, sender_linkedin, sender_website, sender_phone)
                        msg.attach(MIMEText(body_edited, "plain"))
                        msg.attach(MIMEText(html_content, "html"))
                        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                        st.session_state.gmail_service.users().messages().send(
                            userId='me', body={'raw': raw}
                        ).execute()
                        st.success(f"Sent to {email}!")
                        del st.session_state.draft
                        st.session_state.pop("linkedin_draft", None)
                        st.session_state.current_index += 1
                        st.rerun()
                with col2:
                    if st.button("⏭️ Skip"):
                        del st.session_state.draft
                        st.session_state.pop("linkedin_draft", None)
                        st.session_state.current_index += 1
                        st.rerun()
        else:
            st.success("🎉 All companies processed!")