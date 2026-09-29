#!/usr/bin/env python3
"""Orquestrador host — API local que o n8n consome.

Endpoints (localhost:8787):
  GET  /status             — JSON com status de timers, containers e post-its
  POST /obsidian/digest    — grava resumo do dia em ~/Obsidian/Sessões/AAAA/MM/DD.md
  POST /obsidian/session   — append de log de sessão (projeto + texto) no dia
  POST /obsidian/bulletin  — append de linha de alerta em ~/Obsidian/Infra/Boletim.md
  POST /alerta             — notificação desktop (notify-send) no host
Sem dependências (stdlib). Rode via systemd (orquestrador.service).
"""
import json
import os
import re
import subprocess
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VAULT = os.path.expanduser("~/Obsidian")
SHARED = os.path.expanduser("~/n8n-docker/workflows/host")


def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (p.stdout + p.stderr).strip()
    except Exception as e:
        return f"erro: {e}"


def timer_state(name):
    out = run(["systemctl", "--user", "is-active", name])
    enabled = run(["systemctl", "--user", "is-enabled", name]) if out == "active" else "?"
    return {"active": out, "enabled": enabled}


def container_state(name):
    out = run(["docker", "ps", "--filter", f"name=^{name}$",
               "--format", "{{.Names}} {{.Status}}"])
    return out if out else "down"


def do_status():
    timers = {
        "leitormail": timer_state("leitormail.timer"),
        "leitormail-relatorio": timer_state("leitormail-relatorio.timer"),
        "sysmon-relatorio": timer_state("sysmon-relatorio.timer"),
        "orquestrador": timer_state("orquestrador.service"),
    }
    containers = {n: container_state(n) for n in ["localai", "open-webui", "radarr", "n8n"]}
    postit = run(["pgrep", "-f", "mail_postit_tmp"]) or "nenhum"
    sobre = run(["bash", "-c", "uptime -p"])
    return {
        "data": date.today().isoformat(),
        "hora": datetime.now().strftime("%H:%M"),
        "timers": timers,
        "containers": containers,
        "postit": postit,
        "uptime": sobre,
    }


def hoje_note_path():
    hoje = date.today()
    d = os.path.join(VAULT, "Sessões", str(hoje.year), f"{hoje.month:02d}")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{hoje.day:02d}.md")


def atualiza_yaml_ultima(note_path, data):
    """Garante o campo ultima_atualizacao no frontmatter (cria se faltar)."""
    try:
        with open(note_path, "r", encoding="utf-8") as f:
            txt = f.read()
    except FileNotFoundError:
        return
    pat = re.compile(r"^ultima_atualizacao:.*$", re.M)
    if pat.search(txt):
        txt = pat.sub(f"ultima_atualizacao: {data}", txt, count=1)
    else:
        m = re.match(r"^---\n(.*?)\n---", txt, re.S)
        if m:
            txt = txt.replace(m.group(1), m.group(1) + f"\nultima_atualizacao: {data}")
        else:
            txt = f"---\nultima_atualizacao: {data}\n---\n" + txt
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(txt)


def digest(extra=""):
    s = do_status()
    note = hoje_note_path()
    if not os.path.exists(note):
        base = f"---\nprojeto: Sessão\nultima_atualizacao: {s['data']}\n---\n\n# Sessão — {s['data']}\n\n"
        with open(note, "w", encoding="utf-8") as f:
            f.write(base)
    linhas_timers = "\n".join(
        f"- **{k}**: `{v['active']}` (enabled {v['enabled']})"
        for k, v in s["timers"].items()
    )
    linhas_cont = "\n".join(f"- **{k}**: {v}" for k, v in s["containers"].items())
    bloco = (
        f"\n## Digest do orquestrador — {s['hora']} ({s['data']})\n"
        f"- Uptime da máquina: {s['uptime']}\n"
        f"- Timers: \n{linhas_timers}\n"
        f"- Containers: \n{linhas_cont}\n"
        f"- Post-its na tela: `{s['postit']}`\n"
    )
    if extra:
        bloco += f"- Observação: {extra}\n"
    with open(note, "a", encoding="utf-8") as f:
        f.write(bloco + "\n")
    atualiza_yaml_ultima(note, s["data"])
    return f"ok: {note}"


def session(payload):
    projeto = payload.get("projeto", "Geral")
    texto = (payload.get("texto") or "").strip()
    if not texto:
        return "erro: campo 'texto' vazio"
    note = hoje_note_path()
    if not os.path.exists(note):
        d = date.today().isoformat()
        with open(note, "w", encoding="utf-8") as f:
            f.write(f"---\nprojeto: Sessão\nultima_atualizacao: {d}\n---\n\n# Sessão — {d}\n\n")
    with open(note, "a", encoding="utf-8") as f:
        f.write(f"\n## {projeto} ({datetime.now().strftime('%H:%M')})\n{texto}\n")
    atualiza_yaml_ultima(note, date.today().isoformat())
    return f"ok: {note}"


def bulletin(payload):
    texto = (payload.get("texto") or "").strip()
    if not texto:
        return "erro: campo 'texto' vazio"
    os.makedirs(os.path.join(VAULT, "Infra"), exist_ok=True)
    note = os.path.join(VAULT, "Infra", "Boletim.md")
    if not os.path.exists(note):
        with open(note, "w", encoding="utf-8") as f:
            f.write("---\ntags: [infra, boletim]\n---\n\n# Boletim de Infra\n\n")
    with open(note, "a", encoding="utf-8") as f:
        f.write(f"- {datetime.now().strftime('%Y-%m-%d %H:%M')} · {texto}\n")
    atualiza_yaml_ultima(note, date.today().isoformat())
    return f"ok: {note}"


def alerta(payload):
    texto = (payload.get("texto") or "").strip()
    if not texto:
        return "erro: campo 'texto' vazio"
    run(["notify-send", "-u", "critical", "Orquestrador", texto])
    return "ok: notificação enviada"


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/status":
            self._send(200, do_status())
        else:
            self._send(404, {"erro": "rota inexistente; use /status"})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(ln) if ln else b"{}"
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        path = self.path.split("?")[0]
        if path == "/obsidian/digest":
            self._send(200, {"resultado": digest(payload.get("extra", ""))})
        elif path == "/obsidian/session":
            self._send(200, {"resultado": session(payload)})
        elif path == "/obsidian/bulletin":
            self._send(200, {"resultado": bulletin(payload)})
        elif path == "/alerta":
            self._send(200, {"resultado": alerta(payload)})
        else:
            self._send(404, {"erro": "/obsidian/digest|session|bulletin|alerta"})

    def log_message(self, *a):
        pass


def escritor_loop():
    """Reescreve status.json para o n8n a cada 60s e consome alertas do outbox."""
    os.makedirs(SHARED, exist_ok=True)
    outbox = os.path.join(SHARED, "outbox.txt")
    while True:
        try:
            with open(os.path.join(SHARED, "status.json"), "w", encoding="utf-8") as f:
                json.dump(do_status(), f, ensure_ascii=False)
            if os.path.exists(outbox):
                with open(outbox, "r", encoding="utf-8") as f:
                    linhas = [l.strip() for l in f if l.strip()]
                if linhas:
                    run(["notify-send", "-u", "critical", "Orquestrador",
                         "\n".join(linhas[:5])])
                os.remove(outbox)
        except Exception as e:
            print("loop:", e, flush=True)
        time.sleep(60)


if __name__ == "__main__":
    print("orquestrador escutando em 127.0.0.1:8787", flush=True)
    threading.Thread(target=escritor_loop, daemon=True).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", 8787), H).serve_forever()
    except KeyboardInterrupt:
        pass