import os
from urllib.parse import quote
import httpx
from telegram.ext import (Application, CommandHandler,
                          MessageHandler, filters)

TOKEN = os.environ["BOT_TOKEN"]
URL = os.environ["RENDER_EXTERNAL_URL"]
PORT = int(os.environ.get("PORT", 10000))

LANGS = {
    "tr": ["Turkish", "tur", "tr"],
    "en": ["English", "eng", "en"],
    "de": ["German", "ger", "deu", "de"],
    "fr": ["French", "fre", "fra", "fr"],
    "es": ["Spanish", "spa", "es"],
    "ru": ["Russian", "rus", "ru"],
    "it": ["Italian", "ita", "it"],
}
FORMATS = {"pdf", "epub", "txt"}


def parse(text):
    parts = [p.strip() for p in text.split(",")]
    lang = fmt = None
    for p in parts[1:]:
        p = p.lower()
        if p in LANGS:
            lang = p
        elif p in FORMATS:
            fmt = p
    return parts[0], lang, fmt


async def gutenberg(c, name, lang, fmt):
    params = {"search": name}
    if lang:
        params["languages"] = lang
    r = await c.get("https://gutendex.com/books/", params=params)
    out = []
    for b in r.json().get("results", [])[:5]:
        link = None
        for mime, url in b["formats"].items():
            if fmt == "pdf" and mime == "application/pdf":
                link = url
            elif fmt == "txt" and mime.startswith("text/plain"):
                link = url
            elif fmt in (None, "epub") and mime.startswith(
                    "application/epub"):
                link = url
        if link:
            a = b["authors"][0]["name"] if b["authors"] else "?"
            out.append(f"{b['title']} - {a}\n{link}")
    return out


async def archive(c, name, lang, fmt):
    q = f"title:({name}) AND mediatype:texts"
    q += " AND NOT access-restricted-item:true"
    if lang:
        q += " AND language:(" + " OR ".join(LANGS[lang]) + ")"
    r = await c.get(
        "https://archive.org/advancedsearch.php",
        params={"q": q, "fl[]": ["identifier", "title", "creator"],
                "rows": 5, "output": "json"})
    out = []
    for d in r.json()["response"]["docs"]:
        i = d["identifier"]
        link = f"https://archive.org/details/{i}"
        if fmt:
            m = (await c.get(f"https://archive.org/metadata/{i}")).json()
            files = [f["name"] for f in m.get("files", [])
                     if f["name"].lower().endswith("." + fmt)]
            if not files:
                continue
            link = f"https://archive.org/download/{i}/{quote(files[0])}"
        out.append(f"{d.get('title')} - {d.get('creator', '?')}\n{link}")
    return out


async def start(update, ctx):
    await update.message.reply_text(
        "Kitap adını yaz, istersen dil ve format ekle.\n"
        "Örnek: Dava, tr, epub\n"
        "Diller: tr en de fr es ru it\n"
        "Formatlar: pdf epub txt")


async def search(update, ctx):
    name, lang, fmt = parse(update.message.text)
    await update.message.reply_text("Aranıyor...")
    res = []
    async with httpx.AsyncClient(timeout=25,
                                 follow_redirects=True) as c:
        for fn in (gutenberg, archive):
            try:
                res += await fn(c, name, lang, fmt)
            except Exception:
                pass
    await update.message.reply_text(
        "\n\n".join(res[:8]) if res
        else "Bulunamadı. Yazımı veya formatı değiştirip dene.")


app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN,
                webhook_url=f"{URL}/{TOKEN}")
