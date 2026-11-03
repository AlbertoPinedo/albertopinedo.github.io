#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convierte los .md de las carpetas de año/mes (p.ej. 2025/04, 2024/11) en
paginas HTML con el estilo de 2026/copilot-cowork-creditos-guia.html: cabecera
Microsoft, toggle de tema (claro/oscuro) y barra de idiomas ES/CA/GL/EU con
aviso de traduccion por IA.

Cada HTML es AUTOCONTENIDO: las traducciones CA/GL/EU viven embebidas en el
propio HTML (const I18N = {...}). Al recompilar, el conversor lee esas
traducciones del HTML previo, de modo que el HTML es la unica fuente de verdad
(no hay ficheros JSON externos).

Uso:
    python build_2025.py                 # TODOS los años/meses del repo
    python build_2025.py 2025            # todos los meses de un año
    python build_2025.py 2025/04         # un mes concreto
    python build_2025.py 2024/11 2025/01 # varios meses
"""
import sys, os, re, json, html

ROOT = os.path.dirname(os.path.abspath(__file__))

IMG_EXT = {".jpeg", ".jpg", ".png", ".gif", ".webp"}
VID_EXT = {".mp4", ".webm", ".mov"}
LANGS = ["ca", "gl", "eu"]
# Años reservados que NO se procesan en el descubrimiento automático
# (2026 contiene HTML de referencia hechos a mano).
EXCLUDE_YEARS = {"2026"}

# ---------- Negrita unicode (estilo LinkedIn) -> ASCII ----------
def _build_bold_map():
    m = {}
    ranges = [
        (0x1D400, "A"), (0x1D41A, "a"), (0x1D7CE, "0"),   # serif bold
        (0x1D5D4, "A"), (0x1D5EE, "a"), (0x1D7EC, "0"),   # sans-serif bold
        (0x1D468, "A"), (0x1D482, "a"),                   # bold italic
    ]
    for start, base in ranges:
        n = 26 if base.isalpha() else 10
        for i in range(n):
            m[chr(start + i)] = chr(ord(base) + i)
    return m

BOLD_MAP = _build_bold_map()
NEUTRAL = set(" \u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1\u00c1\u00c9\u00cd\u00d3\u00da\u00dc\u00d1-")

def decode_bold(text):
    """Devuelve lista de segmentos (texto_ascii, es_negrita)."""
    states = []  # (char, 'B'|'N'|'X')  X = neutral
    for ch in text:
        if ch in BOLD_MAP:
            states.append([BOLD_MAP[ch], "B"])
        elif ch in NEUTRAL:
            states.append([ch, "X"])
        else:
            states.append([ch, "N"])
    # Puente: un neutral entre dos BOLD pasa a BOLD
    n = len(states)
    for i, st in enumerate(states):
        if st[1] != "X":
            continue
        # buscar vecino no-neutral a izquierda y derecha
        l = i - 1
        while l >= 0 and states[l][1] == "X":
            l -= 1
        r = i + 1
        while r < n and states[r][1] == "X":
            r += 1
        left_bold = l >= 0 and states[l][1] == "B"
        right_bold = r < n and states[r][1] == "B"
        st[1] = "B" if (left_bold and right_bold) else "N"
    # fusionar
    segs = []
    for ch, s in states:
        bold = (s == "B")
        if segs and segs[-1][1] == bold:
            segs[-1][0] += ch
        else:
            segs.append([ch, bold])
    return [(t, b) for t, b in segs]

URL_RE = re.compile(r"https?://[^\s<]+")

def inline_html(text):
    """Convierte negritas unicode y URLs a HTML (con escape seguro)."""
    out = []
    for t, bold in decode_bold(text):
        esc = html.escape(t)
        out.append(f"<strong>{esc}</strong>" if bold else esc)
    s = "".join(out)
    # negrita Markdown **texto**
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    def _a(m):
        u = m.group(0)
        tail = ""
        while u and u[-1] in ").,;":
            tail = u[-1] + tail
            u = u[:-1]
        return f'<a href="{u}" target="_blank" rel="noopener">{u}</a>{tail}'
    return URL_RE.sub(_a, s)

EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")

def is_hashtag_block(lines):
    toks = " ".join(lines).split()
    return bool(toks) and all(t.startswith("#") for t in toks)

def parse_md(text):
    """Devuelve lista de bloques: dicts con type y datos."""
    raw_blocks = re.split(r"\n\s*\n", text.strip())
    blocks = []
    for rb in raw_blocks:
        lines = [l for l in rb.split("\n") if l.strip() != ""]
        if not lines:
            continue
        # bloque de solo embeds
        embeds = [EMBED_RE.match(l.strip()) for l in lines]
        if all(embeds):
            media = []
            for m in embeds:
                fn = m.group(1).strip()
                ext = os.path.splitext(fn)[1].lower()
                kind = "video" if ext in VID_EXT else "image"
                media.append({"file": fn, "kind": kind})
            blocks.append({"type": "media", "media": media})
            continue
        # hashtags
        if is_hashtag_block(lines):
            tags = [t for t in " ".join(lines).split() if t.startswith("#")]
            blocks.append({"type": "tags", "tags": tags})
            continue
        # lista
        if all(l.lstrip().startswith("- ") for l in lines):
            items = [l.lstrip()[2:].strip() for l in lines]
            blocks.append({"type": "list", "items": items})
            continue
        # parrafo (puede tener embeds intercalados -> separar)
        # si hay embeds dentro mezclados con texto, los tratamos por linea
        if any(EMBED_RE.search(l) for l in lines):
            for l in lines:
                m = EMBED_RE.match(l.strip())
                if m:
                    fn = m.group(1).strip()
                    ext = os.path.splitext(fn)[1].lower()
                    kind = "video" if ext in VID_EXT else "image"
                    blocks.append({"type": "media", "media": [{"file": fn, "kind": kind}]})
                else:
                    blocks.append({"type": "p", "text": l.strip()})
            continue
        blocks.append({"type": "p", "text": " ".join(lines)})
    return blocks

def media_html(media):
    parts = []
    for it in media:
        src = "Media/" + it["file"]
        src_attr = html.escape(src)
        if it["kind"] == "video":
            parts.append(
                f'<video controls preload="metadata"><source src="{src_attr}">'
                f'Tu navegador no soporta el vídeo.</video>')
        else:
            parts.append(f'<img src="{src_attr}" alt="" loading="lazy">')
    cls = "media-grid" if len(parts) > 1 else "media-single"
    return f'<figure class="{cls}">' + "".join(parts) + "</figure>"

# ---------- Plantilla ----------
PAGE = """<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title_esc} | Technologia cum Fide</title>
<meta name="description" content="{desc_esc}"/>
<style>
:root{{
  --ms-blue:#0078D4; --ms-blue-dark:#005A9E; --ms-blue-soft:#eaf3fb;
  --ms-red:#F25022; --ms-green:#7FBA00; --ms-green-dark:#107C10; --ms-yellow:#FFB900; --ms-cyan:#00A4EF;
  --bg:#ffffff; --surface:#f7f9fb; --surface-2:#eef2f6; --text:#1b1a19; --muted:#605e5c;
  --border:#e3e6ea; --border-strong:#c8ccd1; --radius:8px;
  --shadow:0 1px 3px rgba(0,0,0,.07); --shadow-lg:0 6px 22px rgba(0,0,0,.10);
}}
html[data-theme="dark"]{{
  --bg:#1b1a19; --surface:#242322; --surface-2:#2d2c2b; --text:#f3f2f1; --muted:#c8c6c4;
  --border:#3b3a39; --border-strong:#4a4948; --ms-blue-soft:#1d2b38;
  --shadow:0 1px 3px rgba(0,0,0,.4); --shadow-lg:0 6px 22px rgba(0,0,0,.5);
}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.65}}
.wrap{{max-width:820px;margin:0 auto;padding:0 22px}}
a{{color:var(--ms-blue-dark)}}
header.hero{{background:linear-gradient(135deg,#f3f9fd 0%,#eef6fc 60%,#fbf7ef 100%);border-bottom:1px solid var(--border);padding:42px 0 34px;position:relative;overflow:hidden}}
html[data-theme="dark"] header.hero{{background:linear-gradient(135deg,#1f2a33 0%,#1d2630 60%,#26221a 100%)}}
.logo{{display:flex;width:34px;height:34px;flex-wrap:wrap;gap:3px;margin-bottom:18px}}
.logo i{{width:14px;height:14px;display:block;border-radius:2px}}
.logo .r{{background:var(--ms-red)}} .logo .g{{background:var(--ms-green)}} .logo .b{{background:var(--ms-cyan)}} .logo .y{{background:var(--ms-yellow)}}
.hero h1{{font-size:clamp(1.5rem,4vw,2.2rem);margin:0 0 12px;letter-spacing:-.5px;line-height:1.2}}
.hero .meta{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;color:var(--muted);font-size:.9rem}}
.hero .date-chip{{background:var(--ms-blue);color:#fff;padding:4px 12px;border-radius:14px;font-weight:600;font-size:.82rem}}
.topbar{{position:absolute;top:16px;right:22px;display:flex;gap:8px;align-items:center;z-index:5}}
.langbar{{display:flex;gap:3px;background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:3px;box-shadow:var(--shadow)}}
.langbar button{{border:0;background:transparent;color:var(--muted);font-family:inherit;font-size:.8rem;font-weight:600;padding:5px 10px;border-radius:16px;cursor:pointer;transition:all .15s}}
.langbar button:hover{{color:var(--ms-blue-dark)}}
.langbar button.active{{background:var(--ms-blue);color:#fff}}
.theme-toggle{{border:1px solid var(--border);background:var(--surface);border-radius:50%;width:36px;height:36px;cursor:pointer;font-size:1rem;box-shadow:var(--shadow);line-height:1}}
.ai-notice{{display:none;background:#fff8e6;border-bottom:1px solid #f7e3a8;color:#6b5a16;font-size:.86rem;padding:10px 0}}
html[data-theme="dark"] .ai-notice{{background:#2e2913;border-color:#5a4f1e;color:#e6d28a}}
.ai-notice.show{{display:block}}
.ai-notice .wrap{{display:flex;gap:10px;align-items:flex-start}}
.back{{display:inline-flex;align-items:center;gap:6px;font-size:.88rem;font-weight:600;text-decoration:none;margin-bottom:14px}}
article{{padding:40px 0 20px}}
article p{{margin:0 0 18px;font-size:1.05rem}}
article ul{{margin:0 0 18px;padding-left:22px}}
article li{{margin:0 0 8px;font-size:1.05rem}}
article strong{{font-weight:700}}
figure{{margin:24px 0}}
figure img,figure video{{width:100%;border-radius:var(--radius);border:1px solid var(--border);box-shadow:var(--shadow);display:block}}
figure.media-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
@media(max-width:560px){{figure.media-grid{{grid-template-columns:1fr}}}}
.tags{{display:flex;flex-wrap:wrap;gap:8px;margin:26px 0 6px}}
.tag{{background:var(--ms-blue-soft);color:var(--ms-blue-dark);border:1px solid var(--border);border-radius:14px;padding:4px 12px;font-size:.82rem;font-weight:600}}
footer{{border-top:1px solid var(--border);margin-top:30px;padding:26px 0 50px;color:var(--muted);font-size:.86rem}}
footer .wrap p{{margin:.3rem 0}}
</style>
</head>
<body>
<header class="hero">
  <div class="topbar">
    <div class="langbar" id="langbar">
      <button data-lang="es" class="active">ES</button>
      <button data-lang="ca">CA</button>
      <button data-lang="gl">GL</button>
      <button data-lang="eu">EU</button>
    </div>
    <button class="theme-toggle" id="themeToggle" aria-label="Cambiar tema">🌙</button>
  </div>
  <div class="wrap">
    <a href="../../index.html" class="back" data-i18n="back">← Volver al inicio</a>
    <div class="logo"><i class="r"></i><i class="g"></i><i class="b"></i><i class="y"></i></div>
    <h1 data-i18n="title">{title_html}</h1>
    <div class="meta"><span class="date-chip">{date_label}</span></div>
  </div>
</header>
<div class="ai-notice" id="aiNotice">
  <div class="wrap"><span>🌐</span><span data-i18n="ai_notice">Esta traducción ha sido generada con inteligencia artificial. Puede contener errores o matices imprecisos; agradecemos tu comprensión. El contenido de referencia oficial es el español.</span></div>
</div>
<article>
  <div class="wrap">
{body}
  </div>
</article>
<footer>
  <div class="wrap">
    <p data-i18n="foot">Technologia cum Fide · Bitácora de Alberto Pinedo. Publicación original: {date_label}.</p>
  </div>
</footer>
<script>
const I18N = {i18n_json};
const ES_BASE = {{}};
function captureES(){{document.querySelectorAll('[data-i18n]').forEach(el=>{{ES_BASE[el.getAttribute('data-i18n')]=el.innerHTML;}});}}
const LOCALES = {{es:'es',ca:'ca-ES',gl:'gl-ES',eu:'eu-ES'}};
function setLang(lang){{
  const dict = lang==='es' ? null : I18N[lang];
  document.documentElement.lang = LOCALES[lang]||'es';
  document.querySelectorAll('[data-i18n]').forEach(el=>{{
    const k = el.getAttribute('data-i18n');
    if(!dict){{ el.innerHTML = ES_BASE[k]; }}
    else if(dict[k]!==undefined){{ el.innerHTML = dict[k]; }}
    else {{ el.innerHTML = ES_BASE[k]; }}
  }});
  document.getElementById('aiNotice').classList.toggle('show', lang!=='es');
  document.querySelectorAll('#langbar button').forEach(b=>b.classList.toggle('active', b.dataset.lang===lang));
}}
document.querySelectorAll('#langbar button').forEach(b=>b.addEventListener('click',()=>setLang(b.dataset.lang)));
// Tema
const themeToggle = document.getElementById('themeToggle');
function updateThemeButton(){{themeToggle.textContent = document.documentElement.getAttribute('data-theme')==='dark' ? '☀️' : '🌙';}}
(function(){{const saved=localStorage.getItem('theme')||'light';document.documentElement.setAttribute('data-theme',saved);}})();
themeToggle.addEventListener('click',()=>{{
  const cur=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';
  document.documentElement.setAttribute('data-theme',cur);localStorage.setItem('theme',cur);updateThemeButton();
}});
captureES();updateThemeButton();
</script>
</body>
</html>
"""

MONTHS_ES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
             7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}

I18N_RE = re.compile(r"const I18N = (\{.*?\});\nconst ES_BASE", re.DOTALL)

def load_embedded_i18n(html_path):
    """Lee el diccionario I18N ya embebido en un HTML generado (fuente unica
    de traducciones; el HTML es autocontenido)."""
    if not os.path.exists(html_path):
        return {}
    with open(html_path, encoding="utf-8") as f:
        txt = f.read()
    m = I18N_RE.search(txt)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}

def parse_name(fname):
    base = os.path.splitext(fname)[0]
    # AA-MM-DD seguido (opcionalmente) de separador y titulo.
    m = re.match(r"^(\d\d)-(\d\d)-(\d\d)[ \-]*(.*)$", base)
    if not m:
        return None
    yy, mm, dd, title = m.groups()
    year = 2000 + int(yy)
    return year, int(mm), int(dd), title.strip()

def build_page(md_path, out_path):
    fname = os.path.basename(md_path)
    parsed = parse_name(fname)
    if not parsed:
        print("  ! nombre no reconocido:", fname); return
    year, mm, dd, title = parsed
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    blocks = parse_md(text)
    # Las traducciones viven dentro del propio HTML (autocontenido).
    prev_i18n = load_embedded_i18n(out_path)

    # construir cuerpo + recoger textos ES traducibles
    es_texts = {"title": title, "back": "← Volver al inicio",
                "ai_notice": "Esta traducción ha sido generada con inteligencia artificial. Puede contener errores o matices imprecisos; agradecemos tu comprensión. El contenido de referencia oficial es el español.",
                "foot": None}
    html_parts = []
    bi = 0
    for blk in blocks:
        if blk["type"] == "p":
            key = f"b{bi}"; bi += 1
            inner = inline_html(blk["text"])
            es_texts[key] = inner
            html_parts.append(f'    <p data-i18n="{key}">{inner}</p>')
        elif blk["type"] == "list":
            key = f"b{bi}"; bi += 1
            lis = "".join(f"<li>{inline_html(it)}</li>" for it in blk["items"])
            inner = f"<ul>{lis}</ul>"
            # guardamos los items como innerHTML del bloque (el <ul> envuelve)
            es_texts[key] = lis
            html_parts.append(f'    <ul data-i18n="{key}">{lis}</ul>')
        elif blk["type"] == "media":
            html_parts.append("    " + media_html(blk["media"]))
        elif blk["type"] == "tags":
            chips = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in blk["tags"])
            html_parts.append(f'    <div class="tags">{chips}</div>')
    body = "\n".join(html_parts)

    translatable = [k for k, v in es_texts.items() if v is not None]
    # Reconstruir I18N a partir de las traducciones ya embebidas en el HTML
    # previo (unica fuente). Solo se conservan las claves vigentes.
    i18n = {}
    for lg in LANGS:
        prev = prev_i18n.get(lg, {})
        d = {k: prev[k] for k in translatable if prev.get(k)}
        if d:
            i18n[lg] = d
    i18n_json = json.dumps(i18n, ensure_ascii=False)

    date_label = f"{dd} de {MONTHS_ES[mm]} de {year}"
    title_html = inline_html(title)
    desc = re.sub("<[^>]+>", "", (es_texts.get("b0") or title))[:155]
    page = PAGE.format(
        title_esc=html.escape(title),
        desc_esc=html.escape(desc),
        title_html=title_html,
        date_label=date_label,
        body=body,
        i18n_json=i18n_json,
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    n_tr = sum(len(v) for v in i18n.values())
    print(f"  OK {fname}  (bloques traducibles: {len(translatable)}, traducciones: {n_tr})")

def process_folder(rel):
    folder = os.path.join(ROOT, rel)
    if not os.path.isdir(folder):
        print("Carpeta no encontrada:", folder); return
    mds = sorted(f for f in os.listdir(folder) if f.lower().endswith(".md"))
    print(f"[{rel}] {len(mds)} archivos")
    for fn in mds:
        out = os.path.join(folder, os.path.splitext(fn)[0] + ".html")
        build_page(os.path.join(folder, fn), out)

def main(argv):
    targets = argv[1:]
    if not targets:
        # Sin argumentos: descubrir todas las carpetas de a\u00f1o (AAAA) del repo,
        # excepto las reservadas (2026 contiene HTML de referencia hechos a mano).
        targets = sorted(
            d for d in os.listdir(ROOT)
            if re.fullmatch(r"\d{4}", d) and d not in EXCLUDE_YEARS
            and os.path.isdir(os.path.join(ROOT, d))
        )
        if not targets:
            print("No se encontraron carpetas de año (AAAA) en el repo."); return
    expanded = []
    for t in targets:
        t = t.replace("\\", "/").strip("/")
        full = os.path.join(ROOT, t)
        if re.fullmatch(r"\d{4}", t):  # un anio: expandir solo meses (AAAA/MM)
            if not os.path.isdir(full):
                print("Año no encontrado:", full); continue
            for sub in sorted(os.listdir(full)):
                if re.fullmatch(r"\d\d", sub) and os.path.isdir(os.path.join(full, sub)):
                    expanded.append(f"{t}/{sub}")
        else:
            expanded.append(t)
    for rel in expanded:
        process_folder(rel)

if __name__ == "__main__":
    main(sys.argv)
