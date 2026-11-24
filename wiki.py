"""Wikipedia client: article cache + search. Free, no API key."""
import html
import re
import requests
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "WikiAlibiProject/1.0 (student project)"}
CACHE = Path(__file__).parent / "data" / "articles"


class WikiError(Exception):
    pass


def _slug(title: str) -> str:
    return re.sub(r"\W+", "_", title.lower()).strip("_")


def get_article(title: str, max_chars: int = 6000, use_cache: bool = True) -> str | None:
    f = CACHE / f"{_slug(title)}.txt"
    if use_cache and f.exists():
        return f.read_text("utf-8")[:max_chars]
    params = {"action": "query", "format": "json", "prop": "extracts", "explaintext": 1,
              "redirects": 1, "titles": title}
    try:
        r = requests.get(API, params=params, headers=HEADERS, timeout=5)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
    except (requests.RequestException, ValueError) as e:
        raise WikiError(f"Wikipedia is not available: {e}")
    text = next(iter(pages.values()), {}).get("extract", "")
    if not text:
        return None
    text = text[:6000]
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(text, "utf-8")
    return text[:max_chars]


def search_wiki(query: str) -> list[dict]:
    """Top 5 results: [{title, snippet}]. Raises WikiError after 3 seconds."""
    params = {"action": "query", "format": "json", "list": "search",
              "srsearch": query, "srlimit": 5}
    try:
        r = requests.get(API, params=params, headers=HEADERS, timeout=3)
        r.raise_for_status()
        items = r.json().get("query", {}).get("search", [])
    except (requests.RequestException, ValueError) as e:
        raise WikiError(f"Wikipedia did not answer in time: {e}")
    return [{"title": i["title"],
             "snippet": html.unescape(re.sub(r"<[^>]+>", "", i["snippet"]))} for i in items]


def wiki_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")


# ---------- Wikipedia-like page view ----------
HTML_CACHE = Path(__file__).parent / "data" / "articles_html"

PAGE_CSS = """
body{font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:14.5px;line-height:1.65;
     color:#202122;background:#fff;margin:0;padding:14px 22px 40px}
h1.wa-title{font-family:Georgia,"Linux Libertine",serif;font-weight:400;font-size:1.7em;
     border-bottom:1px solid #a2a9b1;margin:0 0 .6em;padding-bottom:.15em}
h2{font-family:Georgia,"Linux Libertine",serif;font-weight:400;font-size:1.5em;
     border-bottom:1px solid #a2a9b1;margin:1.2em 0 .5em;padding-bottom:.1em}
h3,h4{font-weight:700;margin:1em 0 .3em}
a{color:#0645ad;text-decoration:none} a:hover{text-decoration:underline}
img{max-width:100%;height:auto}
.infobox,.infobox_v2,table.infobox{float:right;clear:right;width:250px;margin:0 0 14px 18px;
     border:1px solid #a2a9b1;background:#f8f9fa;font-size:13px;line-height:1.4;border-spacing:3px}
.infobox th,.infobox td{padding:3px 5px;vertical-align:top;text-align:left}
.infobox .infobox-image,.infobox .infobox-caption{text-align:center}
.thumb.tright,.floatright,figure[typeof~="mw:File/Thumb"]{float:right;clear:right;margin:4px 0 12px 18px;
     max-width:230px;border:1px solid #c8ccd1;background:#f8f9fa;padding:4px;font-size:12px}
.thumb.tleft,.floatleft{float:left;clear:left;margin:4px 18px 12px 0;max-width:230px}
.thumbcaption,figcaption{font-size:12px;color:#54595d;padding:3px}
table.wikitable{border:1px solid #a2a9b1;border-collapse:collapse;background:#f8f9fa;margin:1em 0;font-size:13px}
table.wikitable th,table.wikitable td{border:1px solid #a2a9b1;padding:4px 8px}
table.wikitable th{background:#eaecf0}
.hatnote{font-style:italic;padding-left:1.6em;margin-bottom:.5em;color:#54595d}
blockquote{border-left:3px solid #c8ccd1;margin:1em 0;padding-left:14px;color:#404244}
.mw-editsection,.navbox,.navbox-styles,.vertical-navbox,.sistersitebox,.noprint,.mw-empty-elt,
.mw-references-wrap,ol.references,.reflist,sup.reference,.ambox,.metadata,.portal,.shortdescription,
.mw-authority-control,.printfooter{display:none!important}
@media(max-width:640px){.infobox,table.infobox,.thumb.tright,figure[typeof~="mw:File/Thumb"]
     {float:none;width:100%;max-width:100%;margin:0 0 12px}body{padding:10px 12px}}
"""


def get_article_html(title: str) -> tuple[str, str]:
    """Returns (real_title, html) of the rendered article. Cached on disk."""
    import json
    f = HTML_CACHE / f"{_slug(title)}.json"
    if f.exists():
        d = json.loads(f.read_text("utf-8"))
        return d["title"], d["html"]
    params = {"action": "parse", "format": "json", "formatversion": 2, "page": title,
              "prop": "text", "redirects": 1, "disableeditsection": 1, "disabletoc": 1}
    try:
        r = requests.get(API, params=params, headers=HEADERS, timeout=8)
        r.raise_for_status()
        data = r.json()["parse"]
    except (requests.RequestException, ValueError, KeyError) as e:
        raise WikiError(f"Wikipedia page not available: {e}")
    HTML_CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"title": data["title"], "html": data["text"]}), "utf-8")
    return data["title"], data["text"]


def render_page(title: str, html: str) -> str:
    """Full HTML document, styled like Wikipedia. Links open in a new tab."""
    html = re.sub(r'(["\s,(])//([a-z0-9.-]+\.)', r"\1https://\2", html)   # //upload... -> https://
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)         # safety: no scripts
    html = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", html, flags=re.I)  # no onclick=...
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<base href="https://en.wikipedia.org/" target="_blank"><style>{PAGE_CSS}</style></head>'
            f'<body><h1 class="wa-title">{title}</h1>{html}</body></html>')
