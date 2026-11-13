"""Metas e ganhos de freela por mês, sites (quais buscar) e cadastros. Usa o mesmo bicos.db."""
import json
import time
from pathlib import Path

SITES = json.loads(Path(__file__).with_name("sites.json").read_text(encoding="utf-8"))


def preparar(con):
    con.executescript("""
      CREATE TABLE IF NOT EXISTS ganhos(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, valor REAL,
        plataforma TEXT, descricao TEXT);
      CREATE TABLE IF NOT EXISTS metas(mes TEXT PRIMARY KEY, valor REAL);
      CREATE TABLE IF NOT EXISTS sites_estado(nome TEXT PRIMARY KEY, ativa INT, cadastrado INT DEFAULT 0);
    """)
    try:
        con.execute("ALTER TABLE sites_estado ADD COLUMN limite INT")
    except Exception:
        pass                                   # já existe
    con.commit()


def sites(con):
    est = {r["nome"]: r for r in con.execute("SELECT * FROM sites_estado")}
    mes = time.strftime("%Y-%m")
    usadas = {r[0]: r[1] for r in con.execute(
        "SELECT fonte, COUNT(*) FROM projeto WHERE status='CANDIDATEI' AND substr(candidatei_em,1,7)=? GROUP BY fonte", (mes,))}
    out = []
    for s in SITES:
        e = est.get(s["nome"])
        limite = e["limite"] if e and e["limite"] is not None else s.get("limite_gratis")
        out.append({**s, "ativa": bool(e["ativa"]) if e and e["ativa"] is not None else s["auto"],
                    "cadastrado": bool(e["cadastrado"]) if e else False,
                    "limite": limite, "usadas": usadas.get(s["nome"], 0)})
    return out


def sites_ativos(con):
    return {s["nome"] for s in sites(con) if s["ativa"]}


def _upsert(con, nome, campo, valor):
    con.execute("INSERT OR IGNORE INTO sites_estado(nome, ativa, cadastrado) VALUES(?,?,0)",
                (nome, next((1 if s["auto"] else 0) for s in SITES if s["nome"] == nome)))
    con.execute(f"UPDATE sites_estado SET {campo}=? WHERE nome=?", (None if valor is None else int(valor), nome))
    con.commit()


def definir_limite(con, nome, limite):
    _upsert(con, nome, "limite", limite if limite not in (None, "") else None)


def definir_ativa(con, nome, ativa):
    _upsert(con, nome, "ativa", ativa)


def definir_cadastrado(con, nome, feito):
    _upsert(con, nome, "cadastrado", feito)


def resumo_mes(con, mes):
    meta = con.execute("SELECT valor FROM metas WHERE mes=?", (mes,)).fetchone()
    if meta is None:  # herda a meta do último mês definido
        meta = con.execute("SELECT valor FROM metas WHERE mes<? ORDER BY mes DESC LIMIT 1", (mes,)).fetchone()
    itens = [dict(r) for r in con.execute(
        "SELECT * FROM ganhos WHERE substr(data,1,7)=? ORDER BY data DESC, id DESC", (mes,))]
    hist = [dict(r) for r in con.execute(
        "SELECT substr(data,1,7) mes, SUM(valor) total FROM ganhos GROUP BY 1 ORDER BY 1 DESC LIMIT 12")]
    metas = sorted(((r["mes"], r["valor"]) for r in con.execute("SELECT * FROM metas")), reverse=True)
    for h in hist:
        h["meta"] = next((v for k, v in metas if k <= h["mes"]), 0)
    return {"mes": mes, "meta": meta["valor"] if meta else 0, "total": sum(i["valor"] for i in itens),
            "itens": itens, "historico": hist[::-1]}


def add_ganho(con, d):
    con.execute("INSERT INTO ganhos(data,valor,plataforma,descricao) VALUES(?,?,?,?)",
                (d["data"], float(d["valor"]), d.get("plataforma", ""), d.get("descricao", "")))
    con.commit()


def apagar_ganho(con, gid):
    con.execute("DELETE FROM ganhos WHERE id=?", (gid,))
    con.commit()


def definir_meta(con, mes, valor):
    con.execute("INSERT OR REPLACE INTO metas VALUES(?,?)", (mes, float(valor)))
    con.commit()
