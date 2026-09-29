# Orquestrador — sidecar local para n8n

O container do **n8n** não consegue falar com o **host**: o handshake HTTP falha
(timeout em `172.20.0.1:8788`) porque o firewall bloqueia container → host. E o
n8n sozinho não pode ler o estado dos seus timers, containers e janelas, nem
escrever no vault do Obsidian.

Este sidecar resolve os dois lados, e é um padrão que reaparece em qualquer
setup self-hosted: **não force rede entre container e host — use as duas
mãos que você já tem.**

```
┌─────────────────┐   arquivos montados    ┌──────────────────────┐
│  n8n (container) │ ────────────────────▶ │  volume /workflows   │
│                 │      payload.json     │  host/               │
│ Rotina 10h/18h   │                       │   appender.sh        │
│  Monitor 30min   │                       │   outbox.txt         │
└─────────────────┘                       └──────────┬───────────┘
        │                                            │
        │  HTTP 127.0.0.1:8787 (n8n → host)         │
        ▼                                            ▼
┌──────────────────────────────────────────────────────────────┐
│  HOST                                                        │
│  api.py (sidecar systemd de usuário)  ──▶ timers/containers    │
│                                       ──▶ ~/Obsidian           │
└──────────────────────────────────────────────────────────────┘
```

Duas pontas, nenhuma abrindo porta para a internet:

- **host → n8n**: o sidecar escuta em `127.0.0.1:8787`.
- **n8n → host**: o container escreve `payload.json` num volume montado e o
  `appender.sh` roda *dentro* do container, aplicando a escrita no vault. O
  container roda como o mesmo uid do usuário, então o arquivo criado pertence a
  você — sem `sudo`, sem `chown`.

## Endpoints (`localhost:8787`, stdlib puro)

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/status` | JSON com estado dos timers, containers e post-its |
| `POST` | `/obsidian/digest` | grava o resumo do dia em `~/Obsidian/Sessões/AAAA/MM/DD.md` |
| `POST` | `/obsidian/session` | append de log de sessão (projeto + texto) no diário do dia |
| `POST` | `/obsidian/bulletin` | append de alerta em `~/Obsidian/Infra/Boletim.md` |
| `POST` | `/alerta` | notificação desktop (`notify-send`) no host |

## Payload do `appender.sh`

```json
{"projeto": "<nome>", "texto": "<markdown>"}
```
→ bloco `## <projeto> (HH:MM)` no diário do dia.

```json
{"target": "Infra/Boletim.md", "texto": "…", "outbox": "⚠️ msg"}
```
→ uma linha datada no arquivo + alerta na fila `outbox.txt` (que vira
`notify-send` no host).

## Instalação

```bash
mkdir -p ~/orquestrador
cp api.py ~/orquestrador/
cp orquestrador.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now orquestrador.service
```

O `appender.sh` vai para o diretório montado no container
(`/workflows/host/appender.sh`) e é chamado por um nó `Execute Command` do n8n.

## O comando `/obsidian` para o opencode

`obsidian.md` é o comando slash que amarra isso ao
[opencode](https://opencode.ai): o agente lê o índice de projetos, cria ou
atualiza a nota, e depois dispara o webhook para o diário do dia cair sozinho.
Se o n8n estiver fora do ar, ele escreve direto no arquivo com o mesmo formato.

## Variáveis

| Chave | Padrão | Para quê |
|---|---|---|
| `VAULT` | `~/Obsidian` | raiz do vault |
| `SHARED` | `~/n8n-docker/workflows/host` | pasta de troca com o container |

## Requisitos

- Python 3 (só stdlib — `http.server`, `subprocess`)
- `systemd` (unidade de usuário)
- Docker + n8n com o volume `host/` montado, se for usar o lado do container
