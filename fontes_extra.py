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
