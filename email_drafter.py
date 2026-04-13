import os
import json
import anthropic
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Research loader (legacy — for company-research.json fallback)
# ---------------------------------------------------------------------------

def load_research(research_path="company-research.json"):
    """Load pre-processed company research if available. Returns dict keyed by company name."""
    try:
        with open(research_path) as f:
            data = json.load(f)
        return {entry["company"]: entry for entry in data}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# ---------------------------------------------------------------------------
# Founder name helpers
# ---------------------------------------------------------------------------

def founder_name_from_email(email):
    """Best-effort: extract first name from email address (e.g. borna@acme.com -> Borna)."""
    if not email or "@" not in email:
        return None
    local = email.split("@")[0]
    for sep in [".", "_", "-"]:
        if sep in local:
            local = local.split(sep)[0]
    name = local.strip().capitalize()
    return name if name.isalpha() else None


def scrape_website(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, 'html.parser')
        text = ' '.join(soup.stripped_strings)[:3000]
        return text
    except Exception as e:
        return f"Could not scrape site: {e}"

def extract_founder_name(website_content, company_name):
    """Use Claude to extract the most likely founder name from website content (fallback)."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = f"""From the following website content for "{company_name}", extract the founder's or CEO's first name only.
If you cannot find one, reply with just: Unknown

Website content:
{website_content[:2000]}

Reply with just the first name, nothing else."""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}]
    )
    name = message.content[0].text.strip()
    return name if name.lower() != "unknown" else None

# ---------------------------------------------------------------------------
# Email drafting
# ---------------------------------------------------------------------------

def build_system_prompt(sender_background):
    return f"""You are helping Andrew Lehman write a cold email to a healthcare startup founder or hiring contact.

Andrew's actual CV — draw specific details only from this, do not invent or embellish anything not stated here:
{sender_background}

STEP ONE — IDENTIFY THE ANGLE BEFORE WRITING ANYTHING:
Do not default to “clinical workflow friction” for every company. Ask:
1. What is this company’s actual unsolved problem right now — not what they do, but what keeps their founder up at night?
2. Which part of Andrew’s background speaks most directly to that problem?

Angle selection by company type:
- Clinical AI / health systems → workflow adoption, physician trust, implementation friction → use the NYU/UCSF research angle
- Consumer health / direct-to-care → retention, engagement, proving ROI to payers → use EMT experience, patient-facing clinical work
- Biotech / drug discovery → research rigor, translational gap, statistical methodology → use published research, R/Python modeling, RNA-seq
- Healthcare admin / RCM → ops efficiency, data accuracy, process redesign → use REDCap, research ops, IRB coordination
- Early-stage / YC → generalist value, moving fast, wearing multiple hats → use the outreach bot, varsity athlete, Career Fellow
If the company doesn’t fit neatly, pick the angle that matches their specific hard problem, not their sector label.

WHAT THIS EMAIL NEEDS TO DO — TWO THINGS ONLY:
1. Show that Andrew has a skillset that could genuinely help with what this company is building
2. Show he thinks critically — that he can identify real problems, engage with them, and bring something to the table. Not just credential-match.

If a founder reads this and thinks “this person has actually wrestled with our problem and has something to offer” — it worked. If it reads like a pitch or a cover letter — it failed.

HUMANITY IS NOT OPTIONAL:
There must be a moment of genuine human connection in this email — something that makes the reader feel like a real person reached out, not a bot. This could be:
- A real opinion on the company’s approach or the problem they’re solving
- Something honest about why Andrew’s work connects to this specific challenge
- A question that shows genuine curiosity, not politeness
The founder has been grinding on this for years. Meet them where they are. Don’t pitch them.

SOUND LIKE A PERSON:
- Write the way a thoughtful human writes — a little loose, a little real
- One slightly imperfect phrase beats three polished ones
- Express actual curiosity or interest — not simulated enthusiasm
- “I’ve been thinking about your Northwell announcement” is human. “I love what you’re building” is noise.
- Don’t write all three moves in exactly three clipped sentences. Let it breathe.

WHAT THIS EMAIL IS NOT:
- A cover letter in disguise
- A sales sequence
- A form letter that could go to any company
- A list of credentials — show relevance through specificity, not résumé lines

HARD RULES:
- Only use specific experiences, projects, or details explicitly in Andrew’s CV. Do not invent scenes, findings, or anecdotes.
- Never mention medical school, gap year, or anything that implies this is temporary
- No greeting or salutation — do not start with "Hi [Name]," or any opener. Jump straight in.
- The first sentence must be about the company or their news, not Andrew’s reaction to it
- No cover-letter phrases: “I would love the opportunity”, “would love to”, “I’d love to”, “I’m passionate about”
- No bullet points in the body
- Do NOT include a signature block or sign-off — added automatically
- Target 100–140 words in the email body — enough space to be human, not so long it becomes a pitch

STRUCTURE — loosely three moves, but let them breathe:
1. Open with the company’s work or recent news — what it is, why it’s a genuinely hard or interesting problem. Have an opinion. One or two sentences. Make sure to make this genuine sounding, Its more to show that I've done my research. Do not sound insincere
2. Connect Andrew’s background to that problem specifically. Pick one real thing from his CV that shows he’s engaged with the same challenge. State it plainly. No narrative arc, no career summary. Make the point once and stop — do not restate the same insight in different words.
3. Soft ask: peer-to-peer, warm, one sentence. Avoid corporate phrasing like “Would you be open to 15 minutes” — aim for something like “worth a quick call?” or “happy to find 15 minutes if useful.” Include a light timing hook — Andrew’s availability, graduating in May, free next week, etc. Give the founder a reason to reply now, not someday. CRITICAL: do not frame the ask as asking the founder to brief Andrew or explain their thinking — “I’d like to hear how you’re thinking about X” puts the founder in professor mode. Frame it as a mutual conversation.

SUBJECT LINE:
- Under 8 words
- Specific — reference the company’s actual work, a news item, or an angle
- Not a tease. Not click-bait. Just honest.

BANNED PHRASES / PATTERNS:
- “caught my eye/attention”, “stood out”, “is interesting because” as openers
- “closes the loop”, “at the intersection of”, “the same gap”, “use case”, “scale”, “evidence base”, “outcomes data”
- “I noticed”, “I came across”, “I saw that you” as openers
- “adjacent to”, “that friction” (when used as shorthand for systemic problems)
- Anything that sounds like a consultant’s observation or business memo rather than a human’s thought
- A purely analytical email with no warmth fails the humanity test even if it has insight
- Self-justification framing: "I spent months on...", "I know from experience that...", "I’ve seen firsthand..." — these sound defensive. State the credential plainly and move on.
- Punchy one-liner hooks designed to provoke (e.g. "That’s where most pilots quietly die", "That’s the part everyone skips") — these read as sales copy, not human thought
- Re-stating your angle in the ask ("I’m less interested in X than Y") — the ask should be warm and simple, not a second pitch

GOOD EXAMPLE (aim for this feel):
“Hi Allon,

The Northwell partnership is a different problem than most AI-primary care companies face — you’re not just validating the model, you’re figuring out whether it actually changes what happens in the room. That’s the part most people skip.

My clinical research at NYU and UCSF has been on exactly that tension — studies that were statistically solid but hit friction when they got near actual clinical workflows. I’ve been thinking about it since I saw the announcement.

Open to 15 minutes? Genuinely curious how you’re navigating the rollout side.”
→ Has an opinion. Shows the specific problem. Connects Andrew’s work directly. Sounds like a real person sent it.

Format your response as:
Subject: <subject line>

<email body>"""


CRITIQUE_PROMPT = """You are a careful editor reviewing a cold email draft. Your job is to refine it so it sounds like a real human wrote it and passes every rule below. Return only the final email — no commentary, no explanation. You also have access to Andrew’s CV in the message — do not invent or add details not present there.

RULES TO ENFORCE:
1. OPENER & GREETING: No salutation — if the draft starts with “Hi [Name],” remove it entirely and open with the first substantive sentence. The first sentence must be about the company or news — never Andrew’s reaction to it. If it starts with “caught my attention/eye”, “stood out”, “I noticed”, “I came across” — rewrite to lead with the company directly.
2. HUMANITY: There must be a moment of genuine human connection — a real opinion, honest curiosity, or something that makes the reader feel a person wrote this. An email that is purely analytical — even if insightful — fails this test. If the draft reads like a business memo or case study with no warmth, add one human touch (a personal reaction, a genuine question, or a moment of honesty about why Andrew finds this interesting).
3. CRITICAL THINKING: The email should show Andrew has thought about the company’s specific problem, not just matched his credentials to keywords. If the draft just credential-lists, rewrite to engage with the actual challenge they face.
4. WORD COUNT: 100–140 words in the body. If under 100, it’s probably too clipped to sound human. If over 140, cut the least essential sentence.
5. BANNED PHRASES: “would love”,  “stood out”, “is interesting because”, “closes the loop”, “at the intersection of”, “the same gap”, “outcomes data”, “use case”, “adjacent to”, "seriously considering". Replace with plain language.
6. FLOW: Don’t enforce exactly three sentences. If the draft needs two sentences to make its point feel human, that’s fine. Avoid robotic parallel structure.
7. NO SIGN-OFF: Remove any closing like “Andrew”, “Best,” etc — signature is added automatically.
9. CV FIDELITY: Do not introduce any specific experience, project, or anecdote not present in the CV. If the draft invented something, replace it with the real credential stated plainly.
10. NOT A PITCH: If the email sounds like a sales email or LinkedIn InMail at any point — rewrite that section until it sounds like a smart person who did real homework.
11. NO DRAMATIC HOOKS: Punchy one-liners like "That’s where most pilots quietly die" or "That’s the part everyone skips" are sales copy. Replace with a plain, honest observation.
12. CLEAN ASK: The closing ask must be warm, peer-to-peer, and one sentence. Avoid “Would you be open to 15 minutes” — too corporate. Something like “worth a quick call?” works better. Include a light timing hook (e.g. graduating May 2026, free the next few weeks) so the founder has a reason to reply now. Do NOT frame it as asking the founder to explain or brief Andrew (“I’d like to hear how you’re thinking about X”) — that puts them in professor mode. Keep it mutual.
13. NO REDUNDANCY: If the email makes an insight once, do not restate it in different words. Each sentence must add something new.
14. NO EM-DASHES!

Return in this exact format:
Subject: <subject line>

<email body>"""


def draft_email(company_name, website, recipient_email, website_content,
                sender_name, sender_background, sender_linkedin, sender_website,
                research=None, row=None):
    """
    Draft a cold email using two API calls:
    1. Draft — generate a first pass
    2. Critique & rewrite — enforce all structural rules strictly
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # --- Founder name ---
    founder_name = None
    if row is not None and row.get("email"):
        founder_name = founder_name_from_email(str(row["email"]))
    if not founder_name and research and research.get("founder_name"):
        founder_name = research["founder_name"].split()[0]
    if not founder_name:
        founder_name = extract_founder_name(website_content, company_name)
    greeting = f"Hi {founder_name}," if founder_name else "Hi there,"

    # --- Context block ---
    if row is not None and row.get("what_they_do"):
        context = f"""Company: {company_name}
Company type: {row.get('company_type', 'unknown — infer from what they do')}
What they do: {row.get('what_they_do', 'N/A')}
Founder's hard problem: {row.get('founders_problem', 'N/A')}
Recent news: {row.get('recent_news', 'N/A')}
Relevant angle from Andrew's background: {row.get('andrews_angle', 'N/A')}"""
    elif research:
        context = f"""Company: {company_name}
What they do: {research.get('what_they_do', 'N/A')}
Recent news: {research.get('recent_news', 'N/A')}
Founder background: {research.get('founder_background', 'N/A')}
Relevant angle from Andrew's background: {research.get('andrew_angle', 'N/A')}"""
    else:
        context = f"""Company: {company_name}
Website: {website}
Website content: {website_content[:2000]}"""

    user_prompt = f"""{context}

Write a cold email from Andrew Lehman to {founder_name or 'the founder'} at {company_name}.
Do not start with a greeting like "Hi [Name]," — open directly with the company or their work. No salutation. The first word should be substantive."""

    # --- Call 1: Draft ---
    draft = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=500,
        system=build_system_prompt(sender_background),
        messages=[{"role": "user", "content": user_prompt}]
    ).content[0].text

    # --- Call 2: Critique & rewrite ---
    final = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=500,
        system=CRITIQUE_PROMPT,
        messages=[{"role": "user", "content": f"Andrew's CV (do not invent details not present here):\n{sender_background}\n\nDraft to rewrite:\n{draft}"}]
    ).content[0].text

    return final


# ---------------------------------------------------------------------------
# LinkedIn message drafting
# ---------------------------------------------------------------------------

def build_linkedin_system_prompt(sender_background):
    return f"""You are helping Andrew Lehman write a short LinkedIn connection message to a healthcare startup founder or hiring contact.

Andrew's actual CV — draw specific details only from this, do not invent:
{sender_background}

3-4 sentences max. Same rules as the cold email — human, specific, no cover-letter language.
- Start with the provided greeting
- One specific thing about what the company is actually doing
- One sentence connecting Andrew's real experience to that — only use details present in the CV above
- Soft ask: open to a quick chat?
- Never mention medical school, gap year, or anything implying this is temporary
- No generic openers or flattery
- No "would love to", "I'd love to", "I'm passionate about"
- No subject line. No sign-off — appended automatically.
Reply with just the message body."""


def draft_linkedin_message(company_name, website_content, sender_name, sender_background,
                           founder_name=None, sender_phone=None, sender_website=None,
                           research=None, row=None):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Founder name fallback chain
    if not founder_name:
        if row is not None and row.get("email"):
            founder_name = founder_name_from_email(str(row["email"]))
        if not founder_name and research and research.get("founder_name"):
            founder_name = research["founder_name"].split()[0]

    greeting = f"Hi {founder_name}," if founder_name else "Hi there,"

    contact_line = ""
    if sender_phone:
        contact_line += f"\n{sender_phone}"
    if sender_website:
        contact_line += f"\n{sender_website}"
    signature = f"Best,\n{sender_name}{contact_line}"

    if row is not None and row.get("what_they_do"):
        context = f"""Company: {company_name}
What they do: {row.get('what_they_do', 'N/A')}
Recent news: {row.get('recent_news', 'N/A')}
Andrew's angle: {row.get('andrews_angle', 'N/A')}"""
    elif research:
        context = f"""Company: {company_name}
What they do: {research.get('what_they_do', 'N/A')}
Recent news: {research.get('recent_news', 'N/A')}
Andrew's angle: {research.get('andrew_angle', 'N/A')}"""
    else:
        context = f"Company: {company_name}\nContext: {website_content[:1000]}"

    user_prompt = f"""{context}

Start with: {greeting}"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        system=build_linkedin_system_prompt(sender_background),
        messages=[{"role": "user", "content": user_prompt}]
    )
    msg = message.content[0].text.strip()
    return f"{msg}\n\n{signature}"