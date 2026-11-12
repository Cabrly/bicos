"""Painel de bicos: http://127.0.0.1:8765 — python3 servidor.py

Coleta 99Freelas e Workana sozinho a cada INTERVALO_MIN (e no botão), e aceita
link ou texto colado de qualquer outro site."""
import json
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import analise
import banco
import fontes

PORTA = 8765
INTERVALO_MIN = 30
PAGINAS = 3
con = banco.conectar()
trava = threading.Lock()
estado = {"rodando": False, "mensagem": "Ainda não coletou.", "ultima": None}


def _coletar_99() -> tuple[int, int]:
    lista = fontes.listar_99(PAGINAS)
    conhecidos = {r[0]: r[1] for r in con.execute(
        "SELECT id_externo, orcamento FROM projeto WHERE fonte='99Freelas' AND orcamento IS NOT NULL")}
    novos = 0
    for i, p in enumerate(lista, 1):
        estado["mensagem"] = f"99Freelas: {i}/{len(lista)}…"
        if p["id_externo"] in conhecidos:
            p["orcamento"] = conhecidos[p["id_externo"]]
        else:
            try:
                fontes.detalhes_99(p)          # orçamento: só na página do projeto
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        novos += banco.gravar(con, analise.analisar(p))
    return len(lista), novos


def _coletar_workana() -> tuple[int, int]:
    estado["mensagem"] = "Workana…"
    lista = fontes.listar_workana(PAGINAS)
    return len(lista), sum(banco.gravar(con, analise.analisar(p)) for p in lista)


def coletar() -> str:
    """As duas fontes, cada uma isolada: uma falhar não derruba a outra."""
    if not trava.acquire(blocking=False):
        return "Já tem uma coleta rodando."
    estado["rodando"] = True
    partes = []
    try:
        for nome, fn in (("99Freelas", _coletar_99), ("Workana", _coletar_workana)):
            try:
                lidos, novos = fn()
                partes.append(f"{nome}: {lidos} lido(s), {novos} novo(s)")
            except fontes.Bloqueado:
                partes.append(f"{nome}: bloqueou a leitura automática")
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                partes.append(f"{nome}: falhou ({e})")
    finally:
        estado.update(rodando=False, mensagem=" · ".join(partes), ultima=time.strftime("%d/%m %H:%M"))
        trava.release()
    return estado["mensagem"]


def laco():
    while True:
        coletar()
        time.sleep(INTERVALO_MIN * 60)


class Painel(BaseHTTPRequestHandler):
    def _json(self, dados, codigo=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/":
            corpo = Path(__file__).with_name("painel.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(corpo)
        elif self.path == "/api/projetos":
            self._json({"projetos": banco.listar(con), "estado": estado})
        else:
            self._json({"erro": "não existe"}, 404)

    def do_POST(self):
        try:
            if self.path == "/api/coletar":
                threading.Thread(target=coletar, daemon=True).start()
                return self._json({"mensagem": "Coleta iniciada."})
            d = self._corpo()
            if self.path == "/api/link":
                try:
                    p = fontes.por_link(d["url"].strip())
                except fontes.Bloqueado:
                    return self._json({"bloqueado": True, "mensagem":
                                       "O site bloqueou a leitura automática. Cole o texto do projeto."}, 409)
                banco.gravar(con, analise.analisar(p))
                return self._json({"mensagem": f"Adicionado: {p['titulo']}"})
            if self.path == "/api/texto":
                p = fontes.por_texto(d.get("titulo", ""), d["texto"], d.get("link", ""), d.get("orcamento", ""))
                banco.gravar(con, analise.analisar(p))
                return self._json({"mensagem": f"Adicionado: {p['titulo']}"})
            if self.path.startswith("/api/status/"):
                banco.marcar(con, int(self.path.rsplit("/", 1)[1]), d["status"])
                return self._json({"ok": True})
            self._json({"erro": "não existe"}, 404)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json({"mensagem": f"Erro: {e}"}, 500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=laco, daemon=True).start()
    print(f"Painel em http://127.0.0.1:{PORTA}  (Ctrl+C para sair)")
    ThreadingHTTPServer(("127.0.0.1", PORTA), Painel).serve_forever()
