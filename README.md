# People Finder

A local Flask web app that crawls company websites and surfaces publicly listed People & HR leaders, complete with role titles, email discovery, and LinkedIn search links.

---

## What it does

- Accepts any company website URL (bare domain, www, full URL, or deep link)
- Automatically discovers team/leadership/about pages via scored link crawling
- Identifies People & HR leaders using three layered strategies:
  - **Structured**: JSON-LD Person objects, semantic profile card patterns
  - **Heuristic**: regex title matching with nearby name detection
  - **AI (optional)**: Claude Sonnet analysis of page text (requires Anthropic API key)
- Discovers emails via:
  - Site crawl (visible and mailto: addresses)
  - Hunter.io lookup (optional, requires API key)
  - Pattern inference from observed personal emails (if guessing enabled)
- Exports results to a two-sheet Excel file (Results + Audit Log)
- All crawling respects robots.txt and rate limits

---

## What it cannot do

- **No LinkedIn scraping**: LinkedIn search links open a Google search — they do not scrape LinkedIn profiles or extract contact info from LinkedIn.
- **Guessed emails are not verified**: Pattern-inferred emails are clearly marked "(guess)" and have not been confirmed deliverable. They are derived from observed patterns only.
- **No login-walled content**: Pages requiring authentication are not crawled.
- **No JavaScript rendering**: The crawler fetches raw HTML only; React/Vue/Angular single-page apps that load content dynamically may yield fewer results.

---

## Setup (Windows)

1. **Create a virtual environment:**
   ```
   py -3.11 -m venv .venv
   ```

2. **Activate it:**
   ```
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```
   copy .env.example .env
   ```
   Open `.env` and add your keys:
   - `ANTHROPIC_API_KEY` — enables AI-powered extraction (claude-sonnet-4-6). Get one at https://console.anthropic.com/
   - `HUNTER_API_KEY` — enables email verification via Hunter.io (optional). Get one at https://hunter.io/

---

## Running

```
py app.py
```

Then open your browser at: **http://localhost:5000**

Exported Excel files are saved automatically to the `exports/` directory.

---

## Legal warning

**Guessed email addresses have not been verified.** Using unverified email addresses may violate:
- Anti-spam laws (CAN-SPAM Act, GDPR, CASL, etc.)
- The terms of service of email providers
- Data protection regulations in your jurisdiction

You are solely responsible for how you use contact information discovered by this tool.

**Do not use this tool for spam, unsolicited bulk email, or any unlawful outreach.**

This tool is intended for legitimate professional research only — for example, identifying the right person to contact at a company before reaching out through appropriate channels.