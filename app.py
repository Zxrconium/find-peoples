import os
import re
import json
import time
import socket
import logging
import ipaddress
import urllib.parse
from datetime import datetime, timezone
from io import BytesIO

import requests
import tldextract
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

USER_AGENT = "people-finder-local-research-tool/1.0"
REQUEST_TIMEOUT = 10
MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PAGES = 12
MAX_DEPTH = 2
CRAWL_DELAY = 1.0

HR_KEYWORDS = [
    "people", "human resources", "hr", "talent", "talent acquisition",
    "recruiting", "recruitment", "people operations", "people ops",
    "people & culture", "people and culture", "culture", "employee experience",
    "workforce", "learning and development", "l&d", "organizational development",
    "organization development", "dei", "diversity", "inclusion", "belonging",
    "chro", "chief human resources officer", "chief people officer", "cpo",
    "vp people", "vp hr", "head of people", "head of talent",
    "director of people", "director of hr", "people partner", "hr business partner",
    "safety and culture", "people, safety", "people and safety",
]

TEAM_PAGE_KEYWORDS = [
    "team", "leadership", "people", "about", "culture", "executive", "management",
    "staff", "founders", "board", "our-people", "meet-the-team", "who-we-are",
    "meet-us", "our-team", "the-team", "hr", "talent",
]

LOWER_SCORE_KEYWORDS = ["careers", "jobs", "life-at", "life_at", "work-with-us", "join-us"]

SKIP_EXTENSIONS = re.compile(
    r"\.(pdf|jpg|jpeg|png|gif|svg|mp4|mp3|zip|gz|tar|woff|woff2|ttf|ico|xml|json|css|js)$",
    re.I,
)
SKIP_PATH_PATTERNS = re.compile(
    r"/(login|signin|signup|register|cart|checkout|privacy|terms|cookie|gdpr|"
    r"sitemap|feed|rss|wp-admin|wp-json|api/)",
    re.I,
)

NAME_PATTERN_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")

# ── Name validation ────────────────────────────────────────────────────────────
_NAME_REJECT_WORDS = frozenset({
    # function words
    "our", "their", "the", "a", "an", "and", "or", "in", "of", "for",
    "with", "at", "by", "from", "to", "is", "are", "was", "has", "have",
    "will", "can", "may", "about", "all", "some", "more", "every", "each",
    "this", "that", "these", "those", "what", "when", "where", "how", "why",
    "who", "which", "we", "us", "you", "your", "my", "me", "its",
    # action verbs and gerunds
    "explore", "exploring", "learn", "learning", "discover", "discovering",
    "create", "creating", "invest", "investing", "partner", "partnering",
    "support", "supporting", "contact", "contacting", "meet", "meeting",
    "join", "joining", "find", "finding", "see", "read", "view", "click",
    "believe", "believing", "build", "building", "drive", "driving",
    "enable", "enabling", "transform", "transforming", "deliver", "delivering",
    "connect", "connecting", "help", "helping", "serve", "serving", "get",
    "download", "access", "grow", "growing",
    # page / navigation / section nouns
    "expertise", "excellence", "progress", "pillars", "innovation",
    "solutions", "services", "development", "leadership", "team", "teams",
    "culture", "careers", "board", "executive", "executives", "community",
    "communities", "values", "vision", "mission", "strategy", "approach",
    "people", "talent", "hr", "resources", "organization", "organisation",
    "department", "network", "home", "news", "blog", "press", "media",
    "events", "products", "industry", "industries", "sector",
    "contact", "about", "overview", "highlights", "insights",
    # common non-name nouns
    "australia", "australian", "trusted", "pharmacy", "hospital", "group",
    "brand", "company", "business", "businesses", "customers", "clients",
    "partners", "employees", "staff", "stories", "story",
})

_NAME_MARKETING_RE = re.compile(
    r"\b(see\s+some|amazing|discover|explore|join\s+us|click|read\s+more|"
    r"learn\s+more|view\s+all|find\s+out|welcome|proud|passionate|committed|"
    r"around\s+australia|around\s+the|our\s+people|meet\s+the\s+team|"
    r"about\s+us|contact\s+us|six\s+pillars|investing\s+in|partnering\s+to)\b",
    re.I,
)

# ── Role-title validation ──────────────────────────────────────────────────────
_TITLE_SENTENCE_RE = re.compile(
    r"\b(see\s+some|some\s+of\s+the|stories?\s+of|communities?\s+around|"
    r"around\s+(australia|the\s+world)|our\s+people\s+and|and\s+communities|"
    r"amazing\s+stories|trusted\s+pharmacy|discover|learn\s+more|"
    r"read\s+more|click\s+here|find\s+out|investing\s+in|partnering\s+to|"
    r"we\s+believe|six\s+pillars|pillars\s+of|through\s+\w+\s+pillars|"
    r"create\s+progress|delivering\s+excellence)\b",
    re.I,
)

# Role title MUST contain at least one of these seniority/function words.
_TITLE_REQUIRED_WORDS = re.compile(
    r"\b("
    r"chief|officer|head\s+of|director|general\s+manager|group\s+(executive|manager)|"
    r"\bvp\b|vice\s+president|"
    r"manager|lead\b|partner\b|specialist|coordinator|recruiter|advisor|consultant|"
    r"\bhr\b|human\s+resources|"
    r"talent|chro|cpo|hrbp|"
    r"people\s+(operations|ops|partner|manager|lead|director|coordinator|"
    r"business\s+partner|engagement|services|development|"
    r"&\s*culture|and\s+culture|experience|analytics)|"
    r"chief\s+people|head\s+of\s+people|director\s+of\s+people|"
    r"vp\s+(of\s+)?people|"
    r"l\s*&\s*d\b|learning\s+and\s+development|"
    r"\bdei\b|diversity\b|inclusion\b|belonging\b|"
    r"workforce|employee\s+experience|"
    r"organisational\s+development|organizational\s+development|"
    r"people\s+&\s*culture|people\s+and\s+culture"
    r")\b",
    re.I,
)

CONFIDENCE_THRESHOLD = 0.40

COMPANY_STRIP_SUFFIXES = re.compile(
    r",?\s*(Inc\.?|LLC\.?|Ltd\.?|Limited|GmbH|Corp\.?|Corporation|Co\.|Company|S\.A\.|AG|BV|NV|PLC|LLP|LP)\s*$",
    re.I,
)


def is_valid_person_name(name: str) -> bool:
    """Return True only if name looks like a real human full name."""
    if not name:
        return False
    name = name.strip()
    if "," in name:
        return False
    tokens = name.split()
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    for token in tokens:
        if not re.match(r"^[A-Za-z'\-]+$", token):
            return False
        if len(token) < 2:
            return False
    for token in tokens:
        clean = re.sub(r"['\-]", "", token)
        if not clean or not clean[0].isupper():
            return False
    for token in tokens:
        if token.lower() in _NAME_REJECT_WORDS:
            return False
    if _NAME_MARKETING_RE.search(name):
        return False
    return True


def is_valid_people_role_title(title: str) -> bool:
    """
    Return True only if title looks like a real job title AND contains
    at least one seniority or HR/People function word.
    """
    if not title:
        return False
    title = title.strip()
    if title.endswith(".") or title.endswith("?") or title.endswith("!"):
        return False
    if len(title.split()) > 12:
        return False
    if _TITLE_SENTENCE_RE.search(title):
        return False
    if re.search(r"^our\s+people$", title, re.I):
        return False
    if re.match(r"^our\s+", title, re.I):
        return False
    if re.match(r"^we\s+", title, re.I):
        return False
    if not _TITLE_REQUIRED_WORDS.search(title):
        return False
    return True


# Alias kept for layer extractors
def is_valid_job_title(title: str) -> bool:
    return is_valid_people_role_title(title)


def source_quote_supports_person_and_role(quote: str, name: str, role_title: str) -> bool:
    """Lenient check: only rejects when a non-trivial quote contains neither name nor role."""
    if not quote:
        return True
    q = quote.lower()
    last = name.strip().split()[-1].lower()
    name_found = last in q
    role_words = [w.lower() for w in role_title.split() if len(w) > 3]
    role_found = any(w in q for w in role_words)
    if len(quote) > 30 and not name_found and not role_found:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# URL validation & normalization
# ─────────────────────────────────────────────────────────────────────────────

PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("169.254.0.0/16"),
]


def is_private_ip(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            for net in PRIVATE_NETS:
                if ip in net:
                    return True
        return False
    except Exception:
        return True


def normalize_url(raw: str):
    raw = raw.strip()
    if not raw:
        raise ValueError("URL is empty.")
    if re.match(r"^(file|ftp)://", raw, re.I):
        raise ValueError("file:// and ftp:// URLs are not allowed.")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw

    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Could not determine hostname.")

    if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Private/loopback addresses are not allowed.")
    if is_private_ip(hostname):
        raise ValueError(f"Resolved IP for {hostname} is in a private range.")

    ext = tldextract.extract(hostname)
    domain = ext.registered_domain or hostname
    base_url = f"{parsed.scheme}://{hostname}"
    company_name_candidate = ext.domain.capitalize() if ext.domain else hostname

    return {
        "scheme": parsed.scheme,
        "hostname": hostname,
        "domain": domain,
        "base_url": base_url,
        "start_url": raw,
        "company_name_candidate": company_name_candidate,
    }


# ─────────────────────────────────────────────────────────────────────────────
# robots.txt
# ─────────────────────────────────────────────────────────────────────────────

def fetch_robots(base_url, session):
    robots_url = base_url.rstrip("/") + "/robots.txt"
    disallowed = []
    try:
        r = session.get(robots_url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            ua_section = False
            star_section = False
            for line in r.text.splitlines():
                line = line.strip()
                if line.lower().startswith("user-agent:"):
                    ua_val = line.split(":", 1)[1].strip()
                    ua_section = ua_val == USER_AGENT or ua_val.startswith("people-finder")
                    star_section = ua_val == "*"
                elif line.lower().startswith("disallow:") and (ua_section or star_section):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallowed.append(path)
            log.info(f"robots.txt: {len(disallowed)} disallow rules")
        else:
            log.info(f"robots.txt returned {r.status_code} — no restrictions")
    except Exception as e:
        log.info(f"robots.txt unavailable: {e} — proceeding cautiously")

    def is_allowed(url):
        path = urllib.parse.urlparse(url).path or "/"
        for rule in disallowed:
            if path.startswith(rule):
                return False
        return True

    return is_allowed


# ─────────────────────────────────────────────────────────────────────────────
# HTTP session
# ─────────────────────────────────────────────────────────────────────────────

def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    s.max_redirects = MAX_REDIRECTS
    return s


def safe_get(session, url, timeout=REQUEST_TIMEOUT):
    try:
        r = session.get(url, timeout=timeout, stream=True)
        content = b""
        for chunk in r.iter_content(chunk_size=65536):
            content += chunk
            if len(content) > MAX_RESPONSE_BYTES:
                log.warning(f"Response too large, truncating: {url}")
                break
        r._content = content
        return r
    except requests.exceptions.SSLError as e:
        raise ValueError(f"SSL error: {e}")
    except requests.exceptions.ConnectionError as e:
        raise ValueError(f"Connection error: {e}")
    except requests.exceptions.Timeout:
        raise ValueError("Request timed out.")
    except requests.exceptions.TooManyRedirects:
        raise ValueError("Too many redirects.")


# ─────────────────────────────────────────────────────────────────────────────
# Link discovery & scoring
# ─────────────────────────────────────────────────────────────────────────────

def score_link(url, text=""):
    combined = (url + " " + text).lower()
    score = 0
    for kw in TEAM_PAGE_KEYWORDS:
        if kw in combined:
            score += 10
    for kw in LOWER_SCORE_KEYWORDS:
        if kw in combined:
            score += 3
    return score


def extract_links(html, base_url, current_url, domain):
    soup = BeautifulSoup(html, "lxml")
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        abs_url = urllib.parse.urljoin(current_url, href)
        parsed = urllib.parse.urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue
        clean = parsed._replace(fragment="", query="").geturl()
        if clean in seen:
            continue
        seen.add(clean)
        ext = tldextract.extract(parsed.netloc)
        if ext.registered_domain != domain:
            continue
        if SKIP_EXTENSIONS.search(parsed.path):
            continue
        if SKIP_PATH_PATTERNS.search(parsed.path):
            continue
        text = a.get_text(strip=True)
        s = score_link(clean, text)
        links.append((clean, s, text))
    return links


# ─────────────────────────────────────────────────────────────────────────────
# Content extraction
# ─────────────────────────────────────────────────────────────────────────────

def clean_html(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["nav", "footer", "script", "style", "form",
                               "header", "aside", "noscript", "iframe"]):
        tag.decompose()
    for div in soup.find_all(True, attrs={"class": re.compile(r"cookie|consent|gdpr|banner", re.I)}):
        div.decompose()
    return soup


def extract_jsonld_people(soup):
    people = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    _collect_jsonld_persons(item, people)
        except Exception:
            pass
    return people


def _collect_jsonld_persons(obj, results):
    if not isinstance(obj, dict):
        return
    t = obj.get("@type", "")
    types = t if isinstance(t, list) else [t]
    if "Person" in types:
        name = obj.get("name", "")
        title = obj.get("jobTitle", "")
        if name:
            results.append({
                "name": name,
                "role_title": title,
                "source_quote": f"{name} — {title}",
            })
    for v in obj.values():
        if isinstance(v, dict):
            _collect_jsonld_persons(v, results)
        elif isinstance(v, list):
            for item in v:
                _collect_jsonld_persons(item, results)


def extract_company_name(soup, domain_candidate):
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content"):
        return COMPANY_STRIP_SUFFIXES.sub("", og["content"]).strip()
    title = soup.find("title")
    if title and title.string:
        parts = re.split(r"[|\-–—]", title.string)
        candidate = parts[-1].strip() if len(parts) > 1 else parts[0].strip()
        candidate = COMPANY_STRIP_SUFFIXES.sub("", candidate).strip()
        if 2 < len(candidate) < 60:
            return candidate
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        text = COMPANY_STRIP_SUFFIXES.sub("", text).strip()
        if 2 < len(text) < 60:
            return text
    footer = soup.find("footer")
    if footer:
        text = footer.get_text(" ")
        m = re.search(r"©\s*\d{4}\s+([A-Za-z0-9 ,\.]+)", text)
        if m:
            name = COMPANY_STRIP_SUFFIXES.sub("", m.group(1)).strip()
            if 2 < len(name) < 60:
                return name
    return domain_candidate


# ─────────────────────────────────────────────────────────────────────────────
# People identification — three layers
# ─────────────────────────────────────────────────────────────────────────────

def layer_a_structured(soup, page_url):
    """JSON-LD schema.org Person data and strong profile-card patterns."""
    people = []

    # JSON-LD
    for p in extract_jsonld_people(soup):
        p["extraction_method"] = "jsonld"
        p["source_urls"] = [page_url]
        p["confidence"] = 0.9
        people.append(p)

    # Profile cards: repeated child elements where first text = name, second = title
    for container in soup.find_all(["ul", "ol", "div", "section"]):
        children = [c for c in container.children if hasattr(c, "find_all")]
        if len(children) < 2:
            continue
        hits = []
        for child in children[:20]:
            texts = [t.strip() for t in child.stripped_strings]
            if len(texts) < 2:
                continue
            name_candidate = texts[0]
            role_candidate = texts[1]
            if is_valid_person_name(name_candidate) and is_valid_people_role_title(role_candidate):
                hits.append({
                    "name": name_candidate,
                    "role_title": role_candidate,
                    "source_quote": f"{name_candidate} — {role_candidate}",
                    "extraction_method": "heuristic",
                    "source_urls": [page_url],
                    "confidence": 0.75,
                })
        people.extend(hits)

    # h3/h4 headings followed immediately by a title element
    for heading in soup.find_all(["h3", "h4"]):
        name_text = heading.get_text(strip=True)
        if not is_valid_person_name(name_text):
            continue
        next_el = heading.find_next_sibling()
        if next_el and next_el.name in ("p", "span", "div"):
            role_text = next_el.get_text(strip=True)
            if is_valid_people_role_title(role_text):
                people.append({
                    "name": name_text,
                    "role_title": role_text,
                    "source_quote": f"{name_text} — {role_text}",
                    "extraction_method": "heuristic",
                    "source_urls": [page_url],
                    "confidence": 0.7,
                })

    return people


def layer_b_heuristic(soup, page_url):
    """Regex proximity search for HR title keywords near name patterns.
    Only active when ANTHROPIC_API_KEY is set — too noisy to trust alone."""
    people = []
    text = soup.get_text(" ")
    title_pattern = re.compile(
        r"(Chief\s+(?:Human\s+Resources|People)\s+Officer|"
        r"(?:VP|Vice\s+President)\s+(?:of\s+)?(?:People|HR|Human\s+Resources|Talent)|"
        r"(?:Head|Director|Manager)\s+of\s+(?:People|HR|Human\s+Resources|Talent|Recruiting|Culture|DEI|Diversity)|"
        r"(?:People|HR|Talent|Culture|DEI|Diversity|Recruiting|Recruitment)\s+(?:Director|Manager|Lead|Partner|Business\s+Partner|Operations|Ops)|"
        r"CHRO|CPO(?:\s|,)|"
        r"(?:Learning\s+and\s+Development|L&D|Organisational\s+Development|Organizational\s+Development)\s+(?:Director|Manager|Lead))",
        re.I,
    )
    for m in title_pattern.finditer(text):
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 120)
        window = text[start:end]
        for nm in NAME_PATTERN_RE.finditer(window):
            candidate = nm.group(0)
            if not is_valid_person_name(candidate):
                continue
            role = m.group(0).strip()
            snippet = window.strip().replace("\n", " ")[:200]
            people.append({
                "name": candidate,
                "role_title": role,
                "source_quote": snippet,
                "extraction_method": "heuristic",
                "source_urls": [page_url],
                "confidence": 0.6,
            })
    return people


def layer_c_claude(page_text, page_url):
    """Send cleaned page text to Claude for structured extraction."""
    if not ANTHROPIC_API_KEY:
        return []
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        truncated = page_text[:12000]
        system_msg = (
            "Extract People/HR/Talent/Culture leaders and senior executives from this company page. "
            "Return ONLY a JSON array — no markdown, no explanation. "
            'Each object: {"name": "Full Name", "role_title": "Exact role title as it appears", '
            '"source_quote": "Short verbatim text fragment proving name and role", "confidence": 0.0-1.0}. '
            "Rules: Only real individual people. Do not invent names or titles. "
            "Do not infer titles not present on the page. "
            "Exclude customers, testimonial authors, blog authors, investors, advisors "
            "unless they are clearly listed as company leadership. "
            "Lower confidence if uncertain."
        )
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_msg,
            messages=[{"role": "user", "content": truncated}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
        results = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            conf = float(item.get("confidence", 0))
            if conf < CONFIDENCE_THRESHOLD:
                continue
            name = item.get("name", "").strip()
            role = item.get("role_title", "").strip()
            if not is_valid_person_name(name):
                log.info(f"Claude: rejecting invalid name {name!r}")
                continue
            if not is_valid_people_role_title(role):
                log.info(f"Claude: rejecting invalid title {role!r}")
                continue
            results.append({
                "name": name,
                "role_title": role,
                "source_quote": item.get("source_quote", "").strip(),
                "extraction_method": "claude",
                "source_urls": [page_url],
                "confidence": conf,
            })
        log.info(f"Claude layer: {len(results)} valid candidates from {page_url}")
        return results
    except json.JSONDecodeError as e:
        log.warning(f"Claude returned malformed JSON: {e}")
        return []
    except Exception as e:
        log.warning(f"Claude layer error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Role classification
# ─────────────────────────────────────────────────────────────────────────────

def is_hr_role(role_title: str) -> bool:
    """Return True if role is a valid People/HR/Talent/Culture/DEI title."""
    if not role_title:
        return False
    if not is_valid_people_role_title(role_title):
        return False
    role_lower = role_title.lower()
    for kw in HR_KEYWORDS:
        if kw in role_lower:
            return True
    return False


_EXEC_FALLBACK_PATTERNS = re.compile(
    r"^("
    r"ceo|"
    r"chief\s+executive\s+officer(\s+and\s+managing\s+director)?|"
    r"managing\s+director|"
    r"founder(\s*/\s*ceo|\s+and\s+ceo|\s+&\s+ceo)?|"
    r"owner\s+and\s+director|"
    r"executive\s+director"
    r")$",
    re.I,
)


def is_exec_fallback_role(role_title: str) -> bool:
    """Return True only if role is on the approved executive fallback list."""
    if not role_title:
        return False
    stripped = role_title.strip()
    if stripped.endswith(".") or stripped.endswith("?") or stripped.endswith("!"):
        return False
    if len(stripped.split()) > 12:
        return False
    if _TITLE_SENTENCE_RE.search(stripped):
        return False
    return bool(_EXEC_FALLBACK_PATTERNS.match(stripped))


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def deduplicate(people):
    groups = {}
    for p in people:
        key = normalize_name(p["name"])
        if key not in groups:
            groups[key] = p
        else:
            existing = groups[key]
            if p["confidence"] > existing["confidence"]:
                existing["confidence"] = p["confidence"]
            if p.get("source_quote") and not existing.get("source_quote"):
                existing["source_quote"] = p["source_quote"]
            if p.get("role_title") and not existing.get("role_title"):
                existing["role_title"] = p["role_title"]
            existing_urls = set(existing.get("source_urls", []))
            for u in p.get("source_urls", []):
                existing_urls.add(u)
            existing["source_urls"] = list(existing_urls)
            priority = {"claude": 3, "jsonld": 2, "heuristic": 1}
            if priority.get(p["extraction_method"], 0) > priority.get(existing["extraction_method"], 0):
                existing["extraction_method"] = p["extraction_method"]
    return list(groups.values())


# ─────────────────────────────────────────────────────────────────────────────
# LinkedIn search URL
# ─────────────────────────────────────────────────────────────────────────────

def linkedin_search_url(name, company):
    q = f'"{name}" "{company}" site:linkedin.com/in'
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)


# ─────────────────────────────────────────────────────────────────────────────
# Main crawl pipeline
# ─────────────────────────────────────────────────────────────────────────────

def crawl_and_extract(url_info):
    session = make_session()
    base_url = url_info["base_url"]
    domain = url_info["domain"]
    start_url = url_info["start_url"]

    is_allowed = fetch_robots(base_url, session)

    pages_checked = []
    pages_skipped = []
    all_candidates = []
    company_name = url_info["company_name_candidate"]

    queue = [(start_url, 0, 20)]
    if start_url != base_url + "/":
        queue.append((base_url + "/", 0, 15))
    visited = set()

    def skip(url, reason):
        pages_skipped.append({"url": url, "reason": reason})
        log.info(f"SKIP {url} — {reason}")

    while queue and len(pages_checked) < MAX_PAGES:
        queue.sort(key=lambda x: -x[2])
        url, depth, score = queue.pop(0)

        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(url):
            skip(url, "robots.txt disallow")
            continue

        log.info(f"CRAWL [{depth}] score={score} {url}")

        try:
            time.sleep(CRAWL_DELAY if pages_checked else 0)
            resp = safe_get(session, url)
        except ValueError as e:
            skip(url, str(e))
            continue

        if resp.status_code != 200:
            skip(url, f"HTTP {resp.status_code}")
            continue

        ct = resp.headers.get("Content-Type", "")
        if "html" not in ct:
            skip(url, f"Non-HTML content-type: {ct}")
            continue

        html = resp.content.decode("utf-8", errors="replace")
        pages_checked.append(url)

        soup = clean_html(html)

        if len(pages_checked) == 1:
            company_name = extract_company_name(soup, url_info["company_name_candidate"])
            log.info(f"Company name: {company_name}")

        # Layer A — always active
        candidates_a = layer_a_structured(soup, url)
        log.info(f"Layer A: {len(candidates_a)} from {url}")
        all_candidates.extend(candidates_a)

        if ANTHROPIC_API_KEY:
            # Layer B — active only with API key (too noisy otherwise)
            candidates_b = layer_b_heuristic(soup, url)
            log.info(f"Layer B: {len(candidates_b)} from {url}")
            all_candidates.extend(candidates_b)
        else:
            log.info("Layer B disabled (no ANTHROPIC_API_KEY — conservative mode)")

        # Layer C — Claude
        page_text = soup.get_text(" ")
        candidates_c = layer_c_claude(page_text, url)
        all_candidates.extend(candidates_c)

        if depth < MAX_DEPTH:
            new_links = extract_links(html, base_url, url, domain)
            for link_url, link_score, link_text in new_links:
                if link_url not in visited:
                    log.info(f"  LINK score={link_score}: {link_url}")
                    queue.append((link_url, depth + 1, link_score))

    log.info(f"Raw candidates: {len(all_candidates)}")

    people = deduplicate(all_candidates)
    log.info(f"After dedup: {len(people)}")

    # Final validation gate — all checks must pass
    def _is_valid(p):
        name = p.get("name", "")
        role = p.get("role_title", "")
        quote = p.get("source_quote", "")
        conf = p.get("confidence", 0)
        source_urls = p.get("source_urls", [])

        if not is_valid_person_name(name):
            log.info(f"GATE DROP — invalid name: {name!r}  role={role!r}")
            return False, "invalid name"
        if not is_valid_people_role_title(role):
            log.info(f"GATE DROP — invalid title: {role!r}  name={name!r}")
            return False, "invalid role title"
        if not source_urls:
            log.info(f"GATE DROP — no source URL: name={name!r}")
            return False, "no source URL"
        if not source_quote_supports_person_and_role(quote, name, role):
            log.info(f"GATE DROP — quote mismatch: name={name!r} role={role!r}")
            return False, "quote does not support person+role"
        if conf < CONFIDENCE_THRESHOLD:
            log.info(f"GATE DROP — low confidence {conf}: name={name!r}")
            return False, f"confidence {conf} below threshold"
        return True, ""

    validated = []
    for p in people:
        ok, reason = _is_valid(p)
        if ok:
            validated.append(p)
        else:
            p["_drop_reason"] = reason
    people = validated
    log.info(f"After validation gate: {len(people)}")

    # Primary: People/HR/Talent/Culture roles
    hr_people = [p for p in people if is_hr_role(p.get("role_title", ""))]
    log.info(f"After HR filter: {len(hr_people)}")

    exec_fallback = False
    if hr_people:
        final_people = hr_people
        for p in final_people:
            p["result_type"] = "Primary People/HR"
        log.info("Result: primary People/HR")
    else:
        exec_people = [p for p in people if is_exec_fallback_role(p.get("role_title", ""))]
        log.info(f"No HR roles found. Exec fallback candidates: {len(exec_people)}")
        final_people = exec_people
        for p in final_people:
            p["result_type"] = "Executive Fallback"
        exec_fallback = bool(exec_people)

    # Add LinkedIn search URL + company name
    for p in final_people:
        p["linkedin_url"] = linkedin_search_url(p["name"], company_name)
        p["company"] = company_name
        # Validation note for audit log
        p.setdefault("_validation_notes", "passed all gates")

    return {
        "success": True,
        "company": company_name,
        "people": final_people,
        "exec_fallback": exec_fallback,
        "pages_checked": pages_checked,
        "pages_skipped": pages_skipped,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

def build_excel(result_data):
    people = result_data.get("people", [])
    crawled_at = result_data.get("crawled_at", "")

    rows_results = []
    rows_audit = []

    for p in people:
        source_url = (p.get("source_urls") or [""])[0]
        rows_results.append({
            "Name": p.get("name", ""),
            "Company": p.get("company", ""),
            "Role Title": p.get("role_title", ""),
            "Result Type": p.get("result_type", "Primary People/HR"),
            "LinkedIn Search": p.get("linkedin_url", ""),
            "Source URL": source_url,
        })
        rows_audit.append({
            "Name": p.get("name", ""),
            "Company": p.get("company", ""),
            "Role Title": p.get("role_title", ""),
            "Result Type": p.get("result_type", "Primary People/HR"),
            "Source URL": "; ".join(p.get("source_urls", [])),
            "Source Quote": p.get("source_quote", ""),
            "Extraction Method": p.get("extraction_method", ""),
            "Confidence": p.get("confidence", ""),
            "Crawled At": crawled_at,
            "Validation Notes": p.get("_validation_notes", ""),
        })

    df_results = pd.DataFrame(rows_results)
    df_audit = pd.DataFrame(rows_audit)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_results.to_excel(writer, sheet_name="Results", index=False)
        df_audit.to_excel(writer, sheet_name="Audit Log", index=False)
    buf.seek(0)

    os.makedirs("exports", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_slug = re.sub(r"[^a-z0-9]", "_", (result_data.get("company") or "unknown").lower())
    filepath = os.path.join("exports", f"{company_slug}_{ts}.xlsx")
    with open(filepath, "wb") as f:
        f.write(buf.getvalue())
    log.info(f"Exported to {filepath}")
    buf.seek(0)
    return buf, filepath


# ─────────────────────────────────────────────────────────────────────────────
# Flask routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/find", methods=["POST"])
def find_people():
    try:
        body = request.get_json(force=True) or {}
        raw_url = (body.get("url") or "").strip()

        if not raw_url:
            return jsonify({"success": False, "error": "No URL provided."}), 400

        log.info(f"=== /find request: url={raw_url}")

        try:
            url_info = normalize_url(raw_url)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        log.info(f"Normalized: {url_info['base_url']}  domain={url_info['domain']}")

        result = crawl_and_extract(url_info)

        if not result["people"]:
            result["success"] = False
            result["error"] = "No People/HR leaders found on the crawled pages."

        return jsonify(result)

    except Exception as e:
        log.exception("Unhandled error in /find")
        return jsonify({"success": False, "error": "An unexpected error occurred. Check server logs."}), 500


@app.route("/export", methods=["POST"])
def export_excel():
    try:
        body = request.get_json(force=True) or {}
        if not body.get("people"):
            return jsonify({"success": False, "error": "No data to export."}), 400

        buf, filepath = build_excel(body)
        filename = os.path.basename(filepath)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        log.exception("Unhandled error in /export")
        return jsonify({"success": False, "error": "Export failed. Check server logs."}), 500


@app.route("/export/audit", methods=["GET"])
def export_audit():
    try:
        exports_dir = "exports"
        if not os.path.isdir(exports_dir):
            return jsonify({"success": False, "error": "No exports found."}), 404
        files = sorted(
            [f for f in os.listdir(exports_dir) if f.endswith(".xlsx")],
            reverse=True,
        )
        if not files:
            return jsonify({"success": False, "error": "No exports found."}), 404
        filepath = os.path.join(exports_dir, files[0])
        return send_file(
            filepath,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=files[0],
        )
    except Exception as e:
        log.exception("Unhandled error in /export/audit")
        return jsonify({"success": False, "error": "Export failed."}), 500


if __name__ == "__main__":
    os.makedirs("exports", exist_ok=True)
    os.makedirs("cache", exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
