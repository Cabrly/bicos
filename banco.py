"""SQLite local: um projeto por (fonte, id_externo) — coletar de novo não duplica."""
import json
import sqlite3
from pathlib import Path

ARQUIVO = Path(__file__).with_name("bicos.db")


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(ARQUIVO, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS projeto (
        id INTEGER PRIMARY KEY,
        fonte TEXT NOT NULL, id_externo TEXT NOT NULL, link TEXT,
        titulo TEXT, categoria TEXT, nivel TEXT, propostas INTEGER,
        publicado_em TEXT, descricao TEXT,
        orcamento TEXT, moeda TEXT, valor_min REAL, valor_max REAL,
        resumo_json TEXT, horas_min REAL, horas_max REAL, tecnologias TEXT,
        status TEXT DEFAULT 'NOVO',            -- NOVO / INTERESSA / CANDIDATEI / DESCARTADO
        coletado_em TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(fonte, id_externo))""")
    try:
        con.execute("ALTER TABLE projeto ADD COLUMN moeda TEXT")
    except sqlite3.OperationalError:
        pass                                   # já existe
    return con


def gravar(con, p: dict) -> bool:
    """Insere ou atualiza (mantém o status que a pessoa marcou). True = novo."""
    novo = con.execute("SELECT 1 FROM projeto WHERE fonte=? AND id_externo=?",
                       (p["fonte"], p["id_externo"])).fetchone() is None
    campos = ["fonte", "id_externo", "link", "titulo", "categoria", "nivel", "propostas",
              "publicado_em", "descricao", "orcamento", "moeda", "valor_min", "valor_max",
              "horas_min", "horas_max", "tecnologias"]
    valores = [p.get(c) for c in campos] + [json.dumps(p.get("resumo") or [], ensure_ascii=False)]
    con.execute(f"""INSERT INTO projeto ({','.join(campos)}, resumo_json)
        VALUES ({','.join('?' * (len(campos) + 1))})
        ON CONFLICT(fonte, id_externo) DO UPDATE SET
        {', '.join(f'{c}=excluded.{c}' for c in campos[2:])}, resumo_json=excluded.resumo_json""",
                valores)
    con.commit()
    return novo


def listar(con) -> list[dict]:
    out = []
    for r in con.execute("SELECT * FROM projeto ORDER BY publicado_em DESC, id DESC"):
        d = dict(r)
        d["resumo"] = json.loads(d.pop("resumo_json") or "[]")
        out.append(d)
    return out


def marcar(con, pid: int, status: str) -> None:
    con.execute("UPDATE projeto SET status=? WHERE id=?", (status, pid))
    con.commit()
