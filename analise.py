"""Resumo, valor e tempo estimado SEM IA — regras simples, de propósito trocáveis.

O tempo é GROSSEIRO: tamanho do texto + funcionalidades citadas + nível pedido.
Serve para separar "bico de uma tarde" de "projeto de um mês", não para orçar.
"""
import html
import re

TECNOLOGIAS = ["Python", "Django", "Flask", "FastAPI", "JavaScript", "TypeScript", "React",
               "Next.js", "Vue", "Angular", "Node", "PHP", "Laravel", "WordPress", "Elementor",
               "WooCommerce", "Shopify", "Java", "Spring", "C#", ".NET", "Flutter", "React Native",
               "Kotlin", "Swift", "Android", "iOS", "SQL", "MySQL", "PostgreSQL", "MongoDB",
               "Firebase", "Supabase", "AWS", "Docker", "Excel", "VBA", "Power BI", "n8n",
               "Selenium", "Playwright", "Scraping", "OpenAI", "ChatGPT", "IA", "Bubble",
               "Figma", "HTML", "CSS", "Tailwind", "API", "Go", "Rust", "Bot", "WhatsApp", "Telegram"]

# funcionalidade citada → horas a mais (estimativa de quem faz com ferramenta comum)
FUNCIONALIDADES = {
    r"\blogin|autentica|cadastro de usu": 6,
    r"pagamento|checkout|pix|stripe|mercado ?pago|gateway": 10,
    r"painel|dashboard|relat[oó]rio": 8,
    r"\bapi\b|integra[cç]": 8,
    r"aplicativo|\bapp\b|mobile|android|ios": 25,
    r"e-?commerce|loja virtual": 20,
    r"intelig[eê]ncia artificial|\bia\b|openai|chatgpt|llm|agente": 10,
    r"scraping|raspagem|automa[cç][aã]o de navegador|selenium|playwright": 8,
    r"banco de dados|database|sql": 5,
    r"whatsapp|telegram|chatbot|\bbot\b": 8,
    r"planilha|excel|vba|power bi": 4,
    r"landing ?page|site institucional": 6,
    r"\bsite\b|website|plataforma|sistema web|sistema de": 10,
    r"metatrader|mt5|trading|forex|blockchain|cripto": 10,
    r"deploy|vps|servidor|docker|aws": 4,
}
MULT_NIVEL = {"INICIANTE": 0.8, "INTERMEDIÁRIO": 1.0, "INTERMEDIARIO": 1.0, "ESPECIALISTA": 1.4}


def texto_limpo(bruto: str) -> str:
    t = html.unescape(bruto or "")
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[*_#`]+", "", t)               # markdown
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def resumo(descricao: str, limite: int = 6) -> list[str]:
    """Primeira frase útil + os tópicos (linhas com -, •, 1.) do texto."""
    linhas = [l.strip() for l in descricao.splitlines() if l.strip()]
    topicos = [re.sub(r"^([-•*]|\d+[.)])\s*", "", l) for l in linhas
               if re.match(r"^([-•*]|\d+[.)])\s+", l)]
    corridas = [l for l in linhas if not re.match(r"^([-•*]|\d+[.)])\s+", l) and len(l) > 40]
    out = []
    if corridas:
        frase = re.split(r"(?<=[.!?])\s", corridas[0])[0]
        out.append(frase[:220])
    for t in topicos:
        if len(out) >= limite:
            break
        if len(t) > 3:
            out.append(t[:160])
    if len(out) < 2:                       # texto corrido sem tópicos: mais frases
        for l in corridas[1:]:
            out.append(re.split(r"(?<=[.!?])\s", l)[0][:200])
            if len(out) >= 3:
                break
    return out or [descricao[:220]]


def tecnologias(texto: str) -> list[str]:
    achadas = []
    for t in TECNOLOGIAS:
        if re.search(r"(?<![\w.])" + re.escape(t) + r"(?![\w])", texto, re.I):
            achadas.append(t)
    return achadas


def horas(descricao: str, nivel: str | None) -> tuple[float, float]:
    t = descricao.lower()
    palavras = len(t.split())
    base = 3 + min(palavras, 1200) / 100         # 100 palavras ≈ +1 h
    # texto longo cita de tudo: só as 2 funcionalidades mais pesadas contam cheio
    achadas = sorted((h for padrao, h in FUNCIONALIDADES.items() if re.search(padrao, t)), reverse=True)
    extra = sum(achadas[:2]) + 0.3 * sum(achadas[2:])
    total = (base + extra) * MULT_NIVEL.get((nivel or "").upper(), 1.0)
    alcance = re.search(r"alcance do projeto\?:\s*(.*)", t)      # Workana diz o tamanho
    if alcance:
        a = alcance.group(1)
        total *= 0.4 if "pequen" in a else 0.8 if "m[eé]dio" in a or "médio" in a else 1.3 if "grande" in a else 1
    elif re.search(r"\b(ajuste|corre[cç][aã]o|bug|pequena altera)", t[:300]):
        total *= 0.5
    return round(total * 0.7), round(total * 1.4)


def dinheiro(texto: str | None) -> list[float]:
    """'R$ 1.500,00 - R$ 3.000' → [1500.0, 3000.0]."""
    out = []
    for m in re.findall(r"R\$\s*([\d.]+(?:,\d{1,2})?)", texto or ""):
        try:
            out.append(float(m.replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    return out


def analisar(p: dict) -> dict:
    desc = texto_limpo(p.get("descricao") or "")
    p["descricao"] = desc
    p["resumo"] = resumo(desc)
    p["tecnologias"] = ", ".join(tecnologias(p.get("titulo", "") + "\n" + desc))
    p["horas_min"], p["horas_max"] = horas(desc, p.get("nivel"))
    # "Aberto (mínimo R$ 50)": o mínimo é da plataforma, não do cliente — não vira valor
    if p.get("valor_min") is None and p.get("valor_max") is None:   # Workana já vem pronto
        orc = p.get("orcamento") or ""
        valores = [] if orc.lower().startswith(("aberto", "a combinar")) else dinheiro(orc)
        if not valores and p.get("fonte") != "99Freelas":     # colado/link: valor no próprio texto
            valores = dinheiro(desc)[:2]
        if valores:
            p["valor_min"], p["valor_max"], p["moeda"] = min(valores), max(valores), "BRL"
    return p
