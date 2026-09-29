---
description: Registra o projeto/conversa atual no vault do Obsidian.
---

Registre o trabalho desta sessão no vault do Obsidian em `~/Obsidian/`:

1. Leia `~/Obsidian/Projetos/_Índice de Projetos.md` e o guia
   `~/Obsidian/Projetos/README - Guia de Registro.md`.
2. Identifique a qual(is) projeto(s) esta sessão pertence.
3. Se for projeto novo: crie a nota `~/Obsidian/Projetos/<Nome>.md` e adicione
   o link ao índice.
4. Se for projeto existente: atualize/append a seção de log com data
   (`## Log 2026-09-22`) descrevendo o que foi feito, decisões, arquivos e
   próximos passos.
5. Atualize o YAML (`status`, `ultima_atualizacao`) e os `## Relacionados`
   (sempre com `[[links]]` + porquê).
6. Nunca escreva senhas/chaves (referencie `.env` apenas).

Depois de registrar, **também registre o resumo no diário do dia** via webhook
(põe o `## Projeto (HH:MM)` no `Sessões/AAAA/MM/DD.md` automaticamente):

```bash
curl -s -X POST http://127.0.0.1:5678/webhook/session -H 'Content-Type: application/json' \
  -d '{"projeto":"<Nome do projeto>","texto":"<1-2 linhas: o que mudou>"}'
```

Se o curl falhar (n8n fora do ar), escreva direto no arquivo
`~/Obsidian/Sessões/<AAAA>/<MM>/<DD>.md` usando o mesmo formato
(`## <projeto> (<HH:MM>)` seguido das linhas).

Contexto extra se informado: $ARGUMENTS