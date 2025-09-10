#!/usr/bin/env bash
set -euo pipefail

# ========= Configuration =========
TICKETARR_USER="ticketarr"
TICKETARR_GROUP="ticketarr"
TICKETARR_UID=1500
TICKETARR_GID=1500

BASE_DIR="/opt/ticketarr"
SCRIPTS_DIR="${BASE_DIR}/scripts"
DATA_DIR="/data/ticketarr"
COMPOSE_FILE="${BASE_DIR}/docker-compose.yml"
ENV_FILE="${BASE_DIR}/.env"

# Mettez ici l'URL réelle de votre docker-compose.yml
COMPOSE_URL="https://example.com/path/to/docker-compose.yml"

# ========= Fonctions utilitaires =========
need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Ce script doit être exécuté en root (ou via sudo)." >&2
    exit 1
  fi
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

require_cmd() {
  local cmd="$1" hint="${2:-}"
  if ! have_cmd "$cmd"; then
    echo "❌ Dépendance manquante: ${cmd}" >&2
    [[ -n "$hint" ]] && echo "   Indice: ${hint}" >&2
    return 1
  fi
  return 0
}

detect_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif docker-compose version >/dev/null 2>&1; then
    echo "docker-compose"
  else
    echo ""
  fi
}

ensure_group() {
  local name="$1" gid="$2"
  if getent group "${name}" >/dev/null 2>&1; then
    echo "Groupe ${name} déjà présent."
  else
    # Essayer groupadd (Debian/RedHat) puis addgroup (Alpine)
    if have_cmd groupadd; then
      groupadd -g "${gid}" "${name}"
    elif have_cmd addgroup; then
      addgroup -g "${gid}" "${name}"
    else
      echo "Impossible de créer le groupe: ni groupadd ni addgroup disponibles." >&2
      exit 1
    fi
    echo "Groupe ${name} créé (GID=${gid})."
  fi
}

ensure_user() {
  local name="$1" uid="$2" group="$3"
  if id -u "${name}" >/dev/null 2>&1; then
    echo "Utilisateur ${name} déjà présent."
  else
    # Essayer useradd (Debian/RedHat) puis adduser (Alpine)
    if have_cmd useradd; then
      local nologin="/usr/sbin/nologin"
      [[ -x /sbin/nologin ]] && nologin="/sbin/nologin"
      useradd -u "${uid}" -g "${group}" -M -r -s "${nologin}" "${name}"
    elif have_cmd adduser; then
      # Alpine: -D (pas de mot de passe), -H (pas de home), -G groupe, -u uid
      local nologin="/sbin/nologin"
      adduser -D -H -G "${group}" -u "${uid}" -s "${nologin}" "${name}"
    else
      echo "Impossible de créer l'utilisateur: ni useradd ni adduser disponibles." >&2
      exit 1
    fi
    echo "Utilisateur ${name} créé (UID=${uid}, GID=${TICKETARR_GID})."
  fi
}

gen_secure() {
  # Génère une chaîne sûre, compatible .env (alphanum + ponctuation courante, sans espaces ni quotes)
  local length="${1:-48}"
  tr -dc 'A-Za-z0-9!@#%^&*()_+=-{}[]:,./?' </dev/urandom | head -c "${length}"
}

# ========= Pré-vol =========
need_root

echo "Vérification des dépendances…"
MISSING=0

require_cmd docker "Installez Docker (https://docs.docker.com/engine/install/)." || MISSING=1
COMPOSE_BIN="$(detect_compose_cmd)"
if [[ -z "${COMPOSE_BIN}" ]]; then
  echo "❌ Docker Compose manquant. Installez soit le plugin 'docker compose', soit 'docker-compose' v1." >&2
  MISSING=1
else
  echo "✔ Docker Compose détecté via: ${COMPOSE_BIN}"
fi

if have_cmd curl; then
  DL_CMD="curl -fsSL"
elif have_cmd wget; then
  DL_CMD="wget -qO-"
else
  echo "❌ curl ou wget requis pour télécharger docker-compose.yml." >&2
  MISSING=1
fi

require_cmd openssl "Installez openssl via votre gestionnaire de paquets." || true
# (On peut fonctionner sans openssl grâce à /dev/urandom + tr.)

if [[ "${MISSING}" -ne 0 ]]; then
  echo "Veuillez installer les dépendances manquantes puis relancer le script." >&2
  exit 1
fi

# S'assurer que le démon Docker tourne (si systemd présent)
if have_cmd systemctl; then
  if ! systemctl is-active --quiet docker; then
    echo "Démarrage du service Docker…"
    systemctl start docker || {
      echo "⚠ Impossible de démarrer Docker via systemd. Assurez-vous qu'il est en cours d'exécution." >&2
    }
  fi
fi

# ========= Comptes et répertoires =========
echo "Création du groupe et de l'utilisateur ${TICKETARR_USER}…"
ensure_group "${TICKETARR_GROUP}" "${TICKETARR_GID}"
ensure_user "${TICKETARR_USER}" "${TICKETARR_UID}" "${TICKETARR_GROUP}"

echo "Création des répertoires…"
mkdir -p "${DATA_DIR}"
mkdir -p "${SCRIPTS_DIR}"
chown -R "${TICKETARR_UID}:${TICKETARR_GID}" "${DATA_DIR}"

mkdir -p "${BASE_DIR}"
# Les fichiers de /opt/ticketarr appartiennent à root, mais on peut donner lecture au service si besoin
chmod 755 "${BASE_DIR}" "${SCRIPTS_DIR}"

# ========= Récupération du docker-compose.yml =========
echo "Téléchargement du docker-compose.yml depuis: ${COMPOSE_URL}"
if [[ "${DL_CMD}" == curl* ]]; then
  curl -fsSL "${COMPOSE_URL}" -o "${COMPOSE_FILE}"
else
  wget -qO "${COMPOSE_FILE}" "${COMPOSE_URL}"
fi
echo "docker-compose.yml enregistré dans ${COMPOSE_FILE}"

# ========= Génération du .env =========
if [[ -f "${ENV_FILE}" ]]; then
  echo "⚠ ${ENV_FILE} existe déjà, on ne l’écrase pas."
else
  echo "Génération des secrets…"
  DB_PASS="$(gen_secure 32)"
  DJANGO_SECRET="$(gen_secure 64)"

  cat > "${ENV_FILE}" <<EOF
DEBUG=False
POSTGRES_DB=helpdesk
POSTGRES_USER=helpdesk
POSTGRES_PASSWORD=${DB_PASS}
POSTGRES_HOST=pg
POSTGRES_PORT=5432
POSTGRES_SSLMODE=prefer
DJANGO_SECRET=${DJANGO_SECRET}
DATA_PATH=${DATA_DIR}
EOF

  chmod 640 "${ENV_FILE}"
  echo ".env généré dans ${ENV_FILE}"
fi

# ========= Scripts de gestion =========
compose_snippet='
# Détection de la commande Docker Compose
if docker compose version >/dev/null 2>&1; then
  COMPOSE_BIN="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE_BIN="docker-compose"
else
  echo "Docker Compose introuvable. Installez le plugin (docker compose) ou docker-compose v1." >&2
  exit 1
fi
COMPOSE_FILE="'"${COMPOSE_FILE}"'"
ENV_FILE="'"${ENV_FILE}"'"
'

cat > "${SCRIPTS_DIR}/start.sh" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
'"${compose_snippet}"'
exec ${COMPOSE_BIN} --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d
EOS

cat > "${SCRIPTS_DIR}/stop.sh" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
'"${compose_snippet}"'
exec ${COMPOSE_BIN} --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" down
EOS

cat > "${SCRIPTS_DIR}/restart.sh" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
'"${compose_snippet}"'
${COMPOSE_BIN} --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" down
exec ${COMPOSE_BIN} --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d
EOS

chmod +x "${SCRIPTS_DIR}/start.sh" "${SCRIPTS_DIR}/stop.sh" "${SCRIPTS_DIR}/restart.sh"

# ========= Premier démarrage =========
echo "Lancement initial des services via Docker Compose…"
if [[ "${COMPOSE_BIN}" == "docker compose" ]]; then
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d
else
  docker-compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d
fi

echo "✅ Installation terminée.
- Dossiers:
    ${DATA_DIR}
    ${SCRIPTS_DIR}
- Fichiers:
    ${COMPOSE_FILE}
    ${ENV_FILE}
- Scripts:
    ${SCRIPTS_DIR}/start.sh
    ${SCRIPTS_DIR}/stop.sh
    ${SCRIPTS_DIR}/restart.sh

Utilisation:
  ${SCRIPTS_DIR}/start.sh
  ${SCRIPTS_DIR}/stop.sh
  ${SCRIPTS_DIR}/restart.sh
"
