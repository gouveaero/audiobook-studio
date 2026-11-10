#!/bin/bash
# Roda as camadas de teste do beta e grava o resultado em EVIDENCE_PATH.
#
# Variáveis obrigatórias:
#   LOCAL_MD        arquivo com os dados desta máquina (fora do git)
#   VOICE_PACK_DIR  pasta do pacote da voz padrão (fora do git)
#   EVIDENCE_PATH   arquivo onde o resultado é anexado
#
# Opcionais:
#   VERIFY_LAYERS   camadas a rodar, separadas por espaço. Padrão: "base model package"
#                   base     testes sem marca (motor falso, segundos)
#                   model    @pytest.mark.model (Pocket real, um processo por vez)
#                   package  @pytest.mark.package (app empacotado)
#   PYTHON          interpretador. Padrão: .venv/bin/python do repositório
#
# Sai com erro se faltar variável, se alguma camada falhar ou se uma camada não tiver teste.
set -u

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ" || exit 2

faltando=0
for var in LOCAL_MD VOICE_PACK_DIR EVIDENCE_PATH; do
  if [ -z "${!var:-}" ]; then
    echo "verify_beta: falta a variável $var" >&2
    faltando=1
  fi
done
[ "$faltando" -eq 0 ] || exit 2

if [ ! -f "$LOCAL_MD" ]; then
  echo "verify_beta: LOCAL_MD não aponta para um arquivo" >&2
  exit 2
fi

PYTHON="${PYTHON:-$RAIZ/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  echo "verify_beta: sem Python em .venv. Rode: uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt" >&2
  exit 2
fi

export LOCAL_MD VOICE_PACK_DIR EVIDENCE_PATH
CAMADAS="${VERIFY_LAYERS:-base model package}"
saida="$(mktemp -t verify_beta)"
trap 'rm -f "$saida"' EXIT

mkdir -p "$(dirname "$EVIDENCE_PATH")"
{
  echo
  echo "## Execução do verify_beta.sh"
  echo
  echo "- Data: $(date '+%Y-%m-%d %H:%M')"
  echo "- Commit: $(git rev-parse --short HEAD 2>/dev/null || echo desconhecido)$(git diff --quiet HEAD 2>/dev/null || echo ' (com alterações não commitadas)')"
  echo "- Camadas pedidas: $CAMADAS"
} >> "$EVIDENCE_PATH"

falhou=0
for camada in $CAMADAS; do
  case "$camada" in
    base)    filtro="not model and not package" ;;
    model)   filtro="model" ;;
    package) filtro="package" ;;
    *) echo "verify_beta: camada desconhecida: $camada" >&2; exit 2 ;;
  esac
  echo "== camada $camada =="
  "$PYTHON" -m pytest -m "$filtro" 2>&1 | tee "$saida"
  codigo=${PIPESTATUS[0]}
  resumo="$(grep -E '^=+ .*(passed|failed|error|skipped|deselected|no tests ran).* =+$' "$saida" | tail -1 | sed -E 's/^=+ //; s/ =+$//')"
  if [ "$codigo" -eq 0 ]; then
    estado="passou"
  elif [ "$codigo" -eq 5 ]; then
    estado="FALHOU (nenhum teste na camada)"; falhou=1
  else
    estado="FALHOU (código $codigo)"; falhou=1
  fi
  echo "- Camada \`$camada\`: $estado. ${resumo:-sem resumo do pytest}" >> "$EVIDENCE_PATH"
done

if [ "$falhou" -eq 0 ]; then
  echo "- Resultado: passou" >> "$EVIDENCE_PATH"
  echo "verify_beta: passou"
  exit 0
fi
echo "- Resultado: FALHOU" >> "$EVIDENCE_PATH"
echo "verify_beta: FALHOU" >&2
exit 1
