#!/bin/sh
# Appender do orquestrador (roda DENTRO do container n8n).
# Lê /workflows/host/payload.json e faz append no vault em /obsidian.
#
# Payload:
#   {"projeto":"<nome>","texto":"<markdown>"}  -> bloco no diário do dia
#   {"target":"Infra/Boletim.md","texto":"...","outbox":"⚠️ msg"} -> linha no arquivo + alerta desktop
VAULT="${1:-/obsidian}"
PAYLOAD="/workflows/host/payload.json"
[ -f "$PAYLOAD" ] || { echo "sem payload em $PAYLOAD" >&2; exit 1; }

projeto=$(sed -n 's/.*"projeto":[[:space:]]*"\([^"]*\)".*/\1/p' "$PAYLOAD")
texto=$(sed -n 's/.*"texto":[[:space:]]*"\([^"]*\)".*/\1/p' "$PAYLOAD" | sed 's/\\n/\n/g' | sed 's/\\t/\t/g')
target=$(sed -n 's/.*"target":[[:space:]]*"\([^"]*\)".*/\1/p' "$PAYLOAD")
outbox=$(sed -n 's/.*"outbox":[[:space:]]*"\([^"]*\)".*/\1/p' "$PAYLOAD" | sed 's/\\n/\n/g')
[ -z "$texto" ] && texto="(vazio)"

if [ -n "$target" ]; then
  rel="$VAULT/$target"
  mkdir -p "$(dirname "$rel")"
  if [ ! -s "$rel" ]; then
    printf -- '---\ntags: [infra, boletim]\n---\n\n# %s\n\n' "$(basename "$rel" .md)" > "$rel"
  fi
  printf -- '%s\n' "- $(date '+%Y/%m/%d %H:%M') · $texto" >> "$rel"
  if [ -n "$outbox" ]; then
    printf -- '%s\n' "$outbox" >> /workflows/host/outbox.txt
  fi
  echo "ok: $rel"
else
  Y=$(date +%Y); M=$(date +%m); D=$(date +%d)
  dir="$VAULT/Sessões/$Y/$M"
  file="$dir/$D.md"
  mkdir -p "$dir"
  if [ ! -s "$file" ]; then
    printf -- "---\nprojeto: Sessão\n---\n\n# Sessão — %s-%s-%s\n\n" "$Y" "$M" "$D" > "$file"
  fi
  {
    printf -- "## %s (%s)\n" "$projeto" "$(date +%H:%M)"
    printf -- '%s\n' "$texto"
  } >> "$file"
  echo "ok: $file"
fi