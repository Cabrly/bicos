"""Coletores. Só páginas públicas, com calma (pausa entre requisições) e sem
contornar proteção: se o site bloquear robô (Cloudflare do Workana), o painel
pede o texto colado."""
import html
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

UA = "Mozilla/5.0 (bicos-mvp; leitura pessoal de projetos)"
PAUSA_S = 1.5
BASE_99 = "https://www.99freelas.com.br"
CATEGORIA_99 = "web-mobile-e-software"


class Bloqueado(Exception):
    """O site pediu verificação humana — não insistimos."""


def baixar(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            corpo = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace") if e.code in (403, 503) else ""
        if "Just a moment" in corpo or "challenge" in corpo:
            raise Bloqueado("o site pediu verificação anti-robô") from e
        raise
    if "<title>Just a moment" in corpo:
        raise Bloqueado("o site pediu verificação anti-robô")
    return corpo


def _txt(fragmento: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


# ---------------------------------------------------------------- 99Freelas
def listar_99(paginas: int = 3) -> list[dict]:
    out = []
    for n in range(1, paginas + 1):
        pagina = baixar(f"{BASE_99}/projects?categoria={CATEGORIA_99}&page={n}")
        itens = re.split(r'<li class="[^"]*result-item', pagina)[1:]
        for bloco in itens:
            pid = re.search(r'data-id="(\d+)"', bloco)
            link = re.search(r'<h1 class="title">.*?<a href="([^"]+)">(.*?)</a>', bloco, re.S)
            if not pid or not link:
                continue
            info = re.search(r'<p class="item-text information">(.*?)</p>', bloco, re.S)
            info_txt = _txt(info.group(1)) if info else ""
            partes = [x.strip() for x in info_txt.split("|")]
            quando = re.search(r'class="datetime" cp-datetime="(\d+)"', bloco)
            propostas = re.search(r"Propostas:\s*<b>(\d+)</b>", bloco)
            desc = re.search(r'data-content="(.*?)"\s*>', bloco, re.S)
            out.append({
                "fonte": "99Freelas", "id_externo": pid.group(1),
                "link": BASE_99 + link.group(1).split("?")[0],
                "titulo": _txt(link.group(2)),
                "categoria": partes[0] if partes else None,
                "nivel": partes[1] if len(partes) > 1 else None,
                "propostas": int(propostas.group(1)) if propostas else None,
                "publicado_em": datetime.fromtimestamp(int(quando.group(1)) / 1000).isoformat(
                    timespec="minutes") if quando else None,
                "descricao": html.unescape(desc.group(1)) if desc else "",
            })
        time.sleep(PAUSA_S)
    return out


def detalhes_99(p: dict) -> dict:
    """Orçamento e valor mínimo só aparecem na página do projeto."""
    pagina = baixar(p["link"])
    for rotulo, chave in (("Orçamento", "orcamento"), ("Valor Mínimo", "valor_minimo_txt")):
        m = re.search(rf"<th>{rotulo}:</th>\s*<td[^>]*>(.*?)</td>", pagina, re.S)
        if m:
            p[chave] = _txt(m.group(1))
    if p.get("valor_minimo_txt") and (p.get("orcamento") or "").lower() == "aberto":
        p["orcamento"] = f"A combinar (mín. da plataforma {p['valor_minimo_txt']})"
    time.sleep(PAUSA_S)
    return p


# ---------------------------------------------------------------- Workana
BASE_WK = "https://www.workana.com"


def _quando_relativo(txt: str) -> str:
    """'há 17 horas' / 'há 5 minutos' / 'Ontem' / 'há 3 dias' → ISO aproximado."""
    from datetime import timedelta
    t = (txt or "").lower()
    n = re.search(r"(\d+)", t)
    n = int(n.group(1)) if n else 1
    delta = (timedelta(minutes=n) if "minuto" in t else timedelta(hours=n) if "hora" in t
             else timedelta(days=1) if "ontem" in t else timedelta(days=n) if "dia" in t
             else timedelta(weeks=n) if "semana" in t else timedelta(0))
    return (datetime.now() - delta).isoformat(timespec="minutes")


def valores_moeda(txt: str | None) -> tuple[str | None, float | None, float | None]:
    """'USD 50 - 100' → ('USD', 50, 100); 'Menos de USD 50' → ('USD', 0, 50)."""
    t = txt or ""
    moeda = "USD" if "USD" in t else "BRL" if "R$" in t else None
    nums = [float(x.replace(".", "").replace(",", ".")) for x in re.findall(r"\d[\d.]*(?:,\d+)?", t)]
    if not moeda or not nums:
        return moeda, None, None
    if t.lower().startswith("menos de"):
        return moeda, 0.0, nums[0]
    return moeda, min(nums), max(nums)


def listar_workana(paginas: int = 2) -> list[dict]:
    """A página pública /jobs já traz os projetos num atributo JSON (:results-initials)."""
    import json
    out = []
    for n in range(1, paginas + 1):
        pagina = baixar(f"{BASE_WK}/jobs?category=it-programming&language=pt&page={n}")
        m = re.search(r":results-initials='(.*?)'", pagina, re.S)
        if not m:
            break
        for r in json.loads(html.unescape(m.group(1))).get("results", []):
            moeda, vmin, vmax = valores_moeda(r.get("budget"))
            desc = r.get("description") or ""
            cat = re.search(r"Subcategoria:\s*<strong>(.*?)</strong>", desc)
            bids = re.search(r"(\d+)", r.get("totalBids") or "")
            out.append({
                "fonte": "Workana", "id_externo": r["slug"], "link": f"{BASE_WK}/job/{r['slug']}",
                "titulo": _txt(r.get("title") or r["slug"]), "categoria": cat.group(1) if cat else None,
                "nivel": "Por hora" if r.get("isHourly") else None,
                "propostas": int(bids.group(1)) if bids else None,
                "publicado_em": _quando_relativo(r.get("postedDate")), "descricao": desc,
                "orcamento": r.get("budget"), "moeda": moeda, "valor_min": vmin, "valor_max": vmax,
            })
        time.sleep(PAUSA_S)
    return out


# ---------------------------------------------------------------- link avulso
def por_link(url: str) -> dict:
    """Workana (ou qualquer site): tenta a página pública. Bloqueado = Bloqueado."""
    if "99freelas.com.br/project/" in url:
        pid = re.search(r"-(\d+)(?:\?|$)", url)
        p = {"fonte": "99Freelas", "id_externo": pid.group(1) if pid else url, "link": url.split("?")[0]}
        pagina = baixar(p["link"])
        t = re.search(r"<title>(.*?)</title>", pagina, re.S)
        p["titulo"] = _txt(t.group(1)).split(" | ")[0] if t else url
        d = re.search(r'class="[^"]*project-description[^"]*"[^>]*>(.*?)</div>', pagina, re.S)
        p["descricao"] = d.group(1) if d else ""
        return detalhes_99(p)
    pagina = baixar(url)

    def meta(nome):
        m = re.search(rf'<meta[^>]+(?:property|name)="{nome}"[^>]+content="([^"]*)"', pagina)
        return html.unescape(m.group(1)) if m else ""
    corpo = _txt(re.sub(r"<(script|style).*?</\1>", " ", pagina, flags=re.S))
    orc = re.search(r"((?:R\$|USD|US\$)\s*[\d.,]+(?:\s*-\s*(?:R\$|USD|US\$)?\s*[\d.,]+)?)", corpo)
    return {"fonte": "Workana" if "workana" in url else "Link", "id_externo": url, "link": url,
            "titulo": meta("og:title") or url, "descricao": meta("og:description") or corpo[:4000],
            "orcamento": orc.group(1) if orc else None}


def por_texto(titulo: str, texto: str, link: str = "", orcamento: str = "") -> dict:
    """Quando o site bloqueia: a pessoa cola o texto do projeto."""
    fonte = "Workana" if "workana" in link else "Colado"
    return {"fonte": fonte, "id_externo": link or f"colado-{int(time.time())}", "link": link or None,
            "titulo": titulo or texto.strip().splitlines()[0][:120], "descricao": texto,
            "orcamento": orcamento or None, "publicado_em": datetime.now().isoformat(timespec="minutes")}
