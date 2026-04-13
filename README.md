# Cold Email Bot

A Streamlit app that automates personalized cold email outreach to healthcare startup founders. Upload a CSV of contacts, let Claude draft a tailored email and LinkedIn message for each one, review and edit, then send directly from your Gmail — all in one interface.

## How It Works

1. **Upload** a CSV of founders/contacts (supports Hunter.io export format or any CSV with company, website, and email columns)
2. **Draft** — for each company, the bot scrapes their website (or uses pre-built research notes), then makes two Claude API calls:
   - *First pass:* generate a personalized cold email using a detailed prompt with rules about tone, structure, and what to avoid
   - *Critique pass:* a second Claude call reviews and rewrites the draft to enforce all rules strictly
   - *LinkedIn message:* a short connection note generated in parallel
3. **Review** — edit the subject, body, and LinkedIn message before sending
4. **Send** — dispatches via Gmail API with a clean HTML signature

## Stack

- **Python** + **Streamlit** — UI and app logic
- **Anthropic Claude API** (`claude-opus-4-5` for email, `claude-haiku-4-5` for LinkedIn + name extraction)
- **Gmail API** — OAuth 2.0 authenticated sending
- **BeautifulSoup** + **requests** — live website scraping as fallback context
- **pandas** — CSV ingestion and column normalization

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/alehmann17/cold-email-bot.git
cd cold-email-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → Create a project
2. Enable the **Gmail API**
3. Create **OAuth 2.0 credentials** (Desktop app) → download as `credentials.json`
4. Place `credentials.json` in the project root

### 3. Anthropic API key

Get a key from [console.anthropic.com](https://console.anthropic.com). You'll paste it into the sidebar when the app runs (it's saved locally in `sender_config.json`, which is gitignored).

### 4. Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## CSV Format

The app accepts any CSV with these columns (case-insensitive, spaces OK):

| Column | Required | Notes |
|---|---|---|
| `Company` | ✅ | Company name |
| `Website` | ✅ | Used for scraping if no research file |
| `Email address` | ✅ | Recipient email |
| `LinkedIn URL` | Optional | Shown in UI for reference |
| `First name` | Optional | Used for founder name extraction |

Hunter.io domain search exports work out of the box.

### Optional: Pre-built research

Drop a `company-research.json` file in the root to skip live scraping. Format:

```json
[
  {
    "company": "Acme Health",
    "what_they_do": "...",
    "recent_news": "...",
    "founder_background": "...",
    "andrew_angle": "..."
  }
]
```

## Security Notes

The following files are gitignored and should never be committed:
- `credentials.json` — Google OAuth client secret
- `token.json` — Google OAuth access/refresh token
- `sender_config.json` — stores your CV, API key, and contact info
- `company-research.json` — may contain personal research notes
- All `.csv` and `.xlsx` files

## Project Structure

```
cold-email-bot/
├── app.py              # Streamlit UI + send logic
├── email_drafter.py    # Claude prompts, drafting pipeline, web scraping
├── gmail_auth.py       # Google OAuth flow
├── requirements.txt
└── README.md
```
