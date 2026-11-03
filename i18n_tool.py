# -*- coding: utf-8 -*-
"""Herramienta de traducciones para las paginas del blog (autocontenidas).

Flujo:
  1) extract  AAAA/MM   -> genera AAAA/MM/_i18n_work.json con las cadenas ES
                           (clave por fichero -> {b0, b1, ...}) y deja huecos
                           ca/gl/eu vacios (o conserva los ya embebidos).
  2) (el humano/IA rellena las traducciones en el work.json)
  3) inject   AAAA/MM   -> reinyecta el diccionario I18N en cada HTML, anadiendo
                           automaticamente las cadenas fijas back/ai_notice por
                           idioma. Tras inyectar, el HTML es la fuente unica y el
                           work.json puede borrarse.

El work.json tiene la forma:
{
  "<fichero.html>": {
     "es":  {"title": "...", "b0": "...", ...},
     "ca":  {"title": "...", "b0": "...", ...},
     "gl":  {...},
     "eu":  {...}
  },
  ...
}
"""
import os
import re
import json
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LANGS = ["ca", "gl", "eu"]

I18N_RE = re.compile(r"const I18N = (\{.*?\});\nconst ES_BASE", re.DOTALL)
DATA_I18N_RE = re.compile(r'data-i18n="([^"]+)"[^>]*>(.*?)</(?:p|ul|h1|a|div)>', re.DOTALL)

# Cadenas fijas por idioma (se autocompletan en inject; no hace falta traducirlas
# a mano en el work.json).
FIXED = {
    "ca": {
        "back": "← Torna a l'inici",
        "ai_notice": "Aquesta traducció s'ha generat amb intel·ligència artificial. Pot contenir errors o matisos imprecisos; agraïm la teva comprensió. El contingut de referència oficial és el castellà.",
    },
    "gl": {
        "back": "← Volver ao inicio",
        "ai_notice": "Esta tradución foi xerada con intelixencia artificial. Pode conter erros ou matices imprecisos; agradecemos a túa comprensión. O contido de referencia oficial é o castelán.",
    },
    "eu": {
        "back": "← Itzuli hasierara",
        "ai_notice": "Itzulpen hau adimen artifizialaren bidez sortu da. Akatsak edo ñabardura okerrak izan ditzake; eskertzen dizugu zure ulermena. Erreferentziazko eduki ofiziala gaztelaniazkoa da.",
    },
}


def extract_es_from_html(txt):
    """Devuelve dict {key: innerHTML} de los bloques data-i18n del cuerpo."""
    es = {}
    # title del <h1 ...>
    mt = re.search(r'<h1[^>]*data-i18n="title"[^>]*>(.*?)</h1>', txt, re.DOTALL)
    if mt:
        es["title"] = mt.group(1).strip()
    for m in re.finditer(r'data-i18n="(b\d+)"[^>]*>(.*?)</(?:p|ul)>', txt, re.DOTALL):
        es[m.group(1)] = m.group(2).strip()
    return es


def load_embedded(txt):
    m = I18N_RE.search(txt)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def cmd_extract(rel):
    folder = os.path.join(ROOT, rel)
    htmls = sorted(f for f in os.listdir(folder) if f.lower().endswith(".html"))
    work = {}
    for fn in htmls:
        path = os.path.join(folder, fn)
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        es = extract_es_from_html(txt)
        if not es:
            continue
        emb = load_embedded(txt)
        entry = {"es": es}
        for lg in LANGS:
            prev = emb.get(lg, {})
            # conserva traducciones previas de claves vigentes
            entry[lg] = {k: prev[k] for k in es if prev.get(k)}
        work[fn] = entry
    out = os.path.join(folder, "_i18n_work.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(work, f, ensure_ascii=False, indent=2)
    # cuenta de claves a traducir
    pend = sum(
        1
        for fn in work
        for lg in LANGS
        for k in work[fn]["es"]
        if not work[fn][lg].get(k)
    )
    print(f"[extract {rel}] {len(work)} ficheros -> {out}  (claves pendientes: {pend})")


def cmd_inject(rel):
    folder = os.path.join(ROOT, rel)
    work_path = os.path.join(folder, "_i18n_work.json")
    if not os.path.exists(work_path):
        print("No existe work.json en", rel)
        return
    with open(work_path, encoding="utf-8") as f:
        work = json.load(f)
    for fn, entry in work.items():
        path = os.path.join(folder, fn)
        if not os.path.exists(path):
            print("  ! no existe HTML:", fn)
            continue
        es = entry["es"]
        i18n = {}
        for lg in LANGS:
            tr = entry.get(lg, {})
            d = {}
            # title primero si esta traducido
            if tr.get("title"):
                d["title"] = tr["title"]
            # cadenas fijas
            d["back"] = FIXED[lg]["back"]
            d["ai_notice"] = FIXED[lg]["ai_notice"]
            for k in es:
                if k == "title":
                    continue
                if tr.get(k):
                    d[k] = tr[k]
            # solo incluir idioma si tiene al menos un bloque de contenido traducido
            has_content = any(k.startswith("b") and tr.get(k) for k in es) or tr.get("title")
            if has_content:
                i18n[lg] = d
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        new_json = json.dumps(i18n, ensure_ascii=False)
        new_txt, n = I18N_RE.subn(
            "const I18N = " + new_json.replace("\\", "\\\\") + ";\nconst ES_BASE",
            txt,
        )
        if n == 0:
            print("  ! no se encontro bloque I18N en", fn)
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_txt)
        n_tr = sum(len(v) for v in i18n.values())
        print(f"  OK {fn}  (idiomas: {len(i18n)}, claves: {n_tr})")
    print(f"[inject {rel}] hecho")


def main(argv):
    if len(argv) < 3:
        print("Uso: python i18n_tool.py [extract|inject] AAAA/MM [AAAA/MM ...]")
        return
    cmd = argv[1]
    for rel in argv[2:]:
        rel = rel.replace("\\", "/").strip("/")
        if cmd == "extract":
            cmd_extract(rel)
        elif cmd == "inject":
            cmd_inject(rel)
        else:
            print("Comando desconocido:", cmd)


if __name__ == "__main__":
    main(sys.argv)
