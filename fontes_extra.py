"""Freelancer.com: tem API pública de projetos ativos (sem login), no mesmo formato dos outros coletores."""
import json
import time
import urllib.parse
from datetime import datetime

import fontes

CONSULTAS = ["python", "node.js", "react", "angular", "web developer", "automation", "api integration",
             "web scraping", "chatbot", "customer support"]
MAX_PROPOSTAS = 25       # acima disso é leilão perdido (e gasta bid do plano grátis)


def listar_freelancer(consultas=CONSULTAS) -> list[dict]:
    vistos, out = set(), []
    for q in consultas:
        url = ("https://www.freelancer.com/api/projects/0.1/projects/active/?compact=true&full_description=true"
               "&limit=40&sort_field=submitdate&query=" + urllib.parse.quote(q))
        for x in json.loads(fontes.baixar(url))["result"]["projects"]:
            if x["id"] in vistos:
                continue
            vistos.add(x["id"])
            bids = (x.get("bid_stats") or {}).get("bid_count") or 0
            if bids > MAX_PROPOSTAS:
                continue
            b, cur = x.get("budget") or {}, x.get("currency") or {}
            codigo, taxa = cur.get("code", "USD"), cur.get("exchange_rate") or 1
            horaria = x.get("type") == "hourly"
            lo, hi = b.get("minimum"), b.get("maximum")
            p = {"fonte": "Freelancer.com", "id_externo": str(x["id"]),
                 "link": "https://www.freelancer.com/projects/" + x["seo_url"],
                 "titulo": x["title"], "categoria": None, "nivel": "Por hora" if horaria else None,
                 "propostas": bids, "descricao": x.get("description") or "",
                 "publicado_em": datetime.fromtimestamp(x["time_submitted"]).isoformat(timespec="minutes")
                 if x.get("time_submitted") else None}
            if lo or hi:
                txt = f"{codigo} {lo:,.0f}–{hi:,.0f}" if lo and hi else f"{codigo} {(lo or hi):,.0f}"
                p["orcamento"] = txt + ("/h" if horaria else "")
                if not horaria:      # valor por hora não vira "valor do projeto"
                    p["moeda"] = "USD"
                    p["valor_min"], p["valor_max"] = round((lo or 0) * taxa), round((hi or lo) * taxa)
            h = (x.get("hourly_project_info") or {}).get("commitment") or {}
            if horaria and h.get("hours"):
                p["descricao"] += f"\n\nCompromisso: {h['hours']} horas por {h.get('interval', 'semana')}."
            out.append(p)
        time.sleep(fontes.PAUSA_S)
    return out


# ---------------------------------------------------------------- Reddit r/forhire
def listar_reddit() -> list[dict]:
    """Posts [HIRING] do r/forhire: o cliente fala direto com você (sem cota, sem nota). O Reddit limita a
    taxa de leitura, então é UMA requisição por ciclo e com User-Agent honesto."""
    import html as _html
    import re as _re
    import urllib.error
    import urllib.request
    import xml.etree.ElementTree as ET
    req = urllib.request.Request("https://www.reddit.com/r/forhire/new/.rss?limit=50",
                                 headers={"User-Agent": "bicos-painel/1.0 (leitura pessoal)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raiz = ET.fromstring(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RuntimeError("o Reddit limitou a leitura; tenta no próximo ciclo") from e
        raise
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in raiz.findall("a:entry", ns):
        titulo = _html.unescape(e.findtext("a:title", "", ns)).strip()
        if not _re.match(r"\s*[\[(]?\s*hiring", titulo, _re.I):
            continue                              # [FOR HIRE] são freelancers se oferecendo
        link = (e.find("a:link", ns).get("href") if e.find("a:link", ns) is not None else "")
        corpo = e.findtext("a:content", "", ns) or ""
        bruto = e.findtext("a:updated", "", ns) or ""
        try:      # o Reddit manda UTC; o painel usa hora local
            from datetime import datetime as _dt
            quando = _dt.fromisoformat(bruto).astimezone().replace(tzinfo=None).isoformat(timespec="minutes")
        except ValueError:
            quando = ""
        out.append({"fonte": "Reddit r/forhire", "id_externo": e.findtext("a:id", link, ns), "link": link,
                    "titulo": _re.sub(r"^\s*[\[(]?\s*hiring\s*[\])]?\s*[:\-]?\s*", "", titulo, flags=_re.I) or titulo,
                    "categoria": None, "nivel": None, "propostas": None,
                    "publicado_em": quando or None, "descricao": corpo})
    return out
