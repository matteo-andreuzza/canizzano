#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  canizzano.it — un solo comando per tutto
#
#    ./canizzano.sh avvia       CMS su http://localhost:8000/admin/
#    ./canizzano.sh dev         anteprima del sito con ricarica automatica
#    ./canizzano.sh build       genera il sito statico in ./dist
#    ./canizzano.sh pubblica    build + caricamento FTP sull'hosting
#    ./canizzano.sh tutto       avvia + build + pubblica
#    ./canizzano.sh mcp         chiave e istruzioni per l'assistente AI
#
#  Vedi «./canizzano.sh aiuto» per l'elenco completo.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CARTELLA="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CARTELLA"

VERDE=$'\033[0;32m'; GIALLO=$'\033[0;33m'; ROSSO=$'\033[0;31m'; GRASSETTO=$'\033[1m'; FINE=$'\033[0m'
info()   { printf '%s→%s %s\n' "$GRASSETTO" "$FINE" "$*"; }
ok()     { printf '%s✓%s %s\n' "$VERDE" "$FINE" "$*"; }
avviso() { printf '%s!%s %s\n' "$GIALLO" "$FINE" "$*"; }
errore() { printf '%s✗%s %s\n' "$ROSSO" "$FINE" "$*" >&2; exit 1; }

# Il demone Docker viene cercato solo quando serve davvero, cosi' comandi
# come «aiuto» o «chiave» funzionano anche su una macchina senza Docker.
DOCKER=()

trova_docker() {
    [[ ${#DOCKER[@]} -gt 0 ]] && return 0
    command -v docker >/dev/null 2>&1 || errore "Docker non e' installato."
    if docker info >/dev/null 2>&1; then
        DOCKER=(docker)
    elif sudo -n docker info >/dev/null 2>&1; then
        DOCKER=(sudo docker)
        avviso "il demone Docker richiede i privilegi: uso «sudo docker»."
    else
        errore "$(cat <<'MSG'
Docker non raggiungibile senza privilegi. Scegli una delle due strade:
  • aggiungi il tuo utente al gruppo docker (poi rifai il login):
      sudo usermod -aG docker "$USER"
  • oppure rilancia questo script con sudo:
      sudo ./canizzano.sh <comando>
MSG
)"
    fi
}

# Il container di build scrive in ./dist: gli passiamo l'utente dell'host
# cosi' i file generati restano nostri.
export UID_HOST GID_HOST
UID_HOST="$(id -u)"
GID_HOST="$(id -g)"

# Deve combaciare con «name:» in compose.yaml: i volumi ne prendono il prefisso.
NOME_PROGETTO=canizzano

compose() { trova_docker; "${DOCKER[@]}" compose "$@"; }

verifica_env() {
    [[ -f .env ]] || errore "manca il file .env — copialo da .env.example:  cp .env.example .env"
    if grep -q '^DJANGO_SECRET_KEY=cambiami' .env; then
        avviso "DJANGO_SECRET_KEY è ancora quella d'esempio: genera la tua con «./canizzano.sh chiave»."
    fi
}

attendi_cms() {
    info "attendo che il CMS risponda…"
    for _ in $(seq 1 60); do
        if compose ps backend --format '{{.Health}}' 2>/dev/null | grep -q healthy; then
            ok "CMS pronto."
            return 0
        fi
        sleep 2
    done
    errore "il CMS non è diventato pronto. Guarda i log con «./canizzano.sh log backend»."
}

comando_avvia() {
    verifica_env
    info "avvio database e CMS…"
    compose up -d --build db backend
    attendi_cms
    local porta; porta="$(grep -E '^CMS_PORT=' .env | cut -d= -f2 || true)"
    ok "redazione aperta su http://localhost:${porta:-8000}/admin/"
}

comando_ferma()   {
    compose --profile dev --profile build --profile deploy down "$@"
    ok "stack fermato. I dati restano: si cancellano solo con «pulisci»."
}
comando_stato()   { compose --profile dev --profile build --profile deploy ps; }
comando_log()     { compose logs -f "${@:-backend}"; }

comando_dev() {
    comando_avvia
    # Un container «dev» rimasto da una sessione precedente tiene occupata la
    # porta e si porta dietro il lock di Astro: lo elimino e ne creo uno nuovo.
    compose --profile dev rm --stop --force dev >/dev/null 2>&1 || true
    local porta; porta="$(grep -E '^DEV_PORT=' .env | cut -d= -f2 || true)"
    info "anteprima su http://localhost:${porta:-4321} — Ctrl+C per fermarla."
    compose --profile dev up --build --force-recreate dev
}

# Ferma solo l'anteprima, senza toccare CMS e database.
comando_ferma_dev() {
    compose --profile dev rm --stop --force dev >/dev/null 2>&1 || true
    ok "anteprima fermata. CMS e database restano accesi."
}

comando_build() {
    comando_avvia
    mkdir -p dist
    info "genero il sito statico…"
    compose --profile build run --rm --build sito
    ok "sito generato in ./dist ($(find dist -type f 2>/dev/null | wc -l) file)."
}

comando_pubblica() {
    verifica_env
    [[ -d dist && -n "$(ls -A dist 2>/dev/null)" ]] || comando_build
    if grep -q '^FTP_HOST=ftp.canizzano.it$' .env && grep -q '^FTP_USER=utente-ftp$' .env; then
        errore "le credenziali FTP nel .env sono ancora quelle d'esempio."
    fi
    info "carico il sito sull'hosting via FTP…"
    compose --profile deploy run --rm --build deploy
    ok "pubblicato."
}

comando_prova_ftp() {
    verifica_env
    info "prova a vuoto: elenco le operazioni FTP senza scrivere nulla."
    DRY_RUN=true compose --profile deploy run --rm --build -e DRY_RUN=true deploy
}

comando_tutto() { comando_build; comando_pubblica; }

comando_verifica_db() {
    verifica_env
    info "tabelle dell'app «eventi» presenti nel database:"
    compose exec -T backend python manage.py shell --no-imports -c \
        "from django.db import connection; [print('   -', t) for t in sorted(t for t in connection.introspection.table_names() if t.startswith('eventi_'))]"
    echo
    info "stato delle migrazioni:"
    compose exec -T backend python manage.py showmigrations eventi
}

comando_ripristina_db() {
    verifica_env
    trova_docker
    cat <<'AVVISO'
Questo comando ricrea il database da zero.

  • Si perdono gli EVENTI e i TESTI inseriti in redazione.
  • Le FOTO caricate NON si toccano (stanno in un volume separato).

Serve quando lo schema del database e' rimasto indietro rispetto al codice
— l'errore tipico e' «relation "eventi_..." does not exist» nell'admin.
Se hai contenuti da salvare, esci ora e lancia prima «./canizzano.sh backup».
AVVISO
    read -r -p 'Procedo? Scrivi «si» per confermare: ' risposta
    [[ "$risposta" == "si" ]] || { avviso "annullato."; return 1; }

    info "fermo lo stack…"
    compose --profile dev --profile build --profile deploy down

    # Il volume va cercato, non indovinato: se in passato lo stack e' partito
    # da una cartella con un altro nome, il prefisso del progetto e' diverso.
    local volumi
    volumi="$("${DOCKER[@]}" volume ls --quiet --filter 'name=dati_postgres' || true)"

    if [[ -z "$volumi" ]]; then
        avviso "nessun volume «dati_postgres» trovato: il database era gia' pulito."
    else
        while read -r volume; do
            [[ -n "$volume" ]] || continue
            info "elimino il volume $volume…"
            if ! "${DOCKER[@]}" volume rm "$volume"; then
                errore "$(cat <<MSG
Non sono riuscito a eliminare il volume «$volume».
Di solito vuol dire che un container lo sta ancora usando. Guarda quali con:
    docker ps -a --filter volume=$volume
fermali, poi rilancia «./canizzano.sh ripristina-db».
MSG
)"
            fi
        done <<< "$volumi"
    fi

    comando_avvia
    info "ricarico i contenuti d'esempio…"
    compose exec backend python manage.py dati_esempio
    verifica_schema
    ok "database ricreato e riallineato al codice."
}

# Controlla che le tabelle attese esistano davvero: senza questa verifica un
# ripristino fallito a meta' si scoprirebbe solo aprendo l'admin.
verifica_schema() {
    info "verifico lo schema del database…"
    local attese="album articolo attivita dettaglioarticolo edizione evento foto giornata impostazionisito luogo"
    local presenti
    presenti="$(compose exec -T backend python manage.py shell --no-imports -c \
        "from django.db import connection; print(' '.join(sorted(t.removeprefix('eventi_') for t in connection.introspection.table_names() if t.startswith('eventi_'))))" \
        2>/dev/null | tr '\r\n' '  ')"

    local mancanti=""
    for tabella in $attese; do
        [[ " $presenti " == *" $tabella "* ]] || mancanti="$mancanti $tabella"
    done

    if [[ -n "$mancanti" ]]; then
        errore "$(cat <<MSG
Mancano ancora delle tabelle:$mancanti
Lo schema non e' allineato. Mandami l'output di:
    ./canizzano.sh gestisci showmigrations eventi
MSG
)"
    fi
    ok "schema completo: $(echo "$presenti" | wc -w) tabelle."
}

comando_gestisci() {
    [[ $# -gt 0 ]] || errore "uso: ./canizzano.sh gestisci <comando django>  (es. «gestisci createsuperuser»)"
    compose exec backend python manage.py "$@"
}

# Le istruzioni per collegare un agente AI al CMS: indirizzo, chiave e i
# comandi gia' pronti per i client piu' diffusi.
comando_mcp() {
    verifica_env
    if ! compose ps backend --format '{{.Health}}' 2>/dev/null | grep -q healthy; then
        avviso "il CMS non è acceso: lo avvio."
        comando_avvia
    fi
    compose exec -T backend python manage.py chiave_assistente "$@"
}

comando_esempi()  { compose exec backend python manage.py dati_esempio; }
comando_backup() {
    mkdir -p backup
    local file="backup/canizzano-$(date +%Y%m%d-%H%M%S).sql"
    compose exec -T db pg_dump -U "$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2)" \
        "$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2)" > "$file"
    ok "backup del database in $file"
}

comando_chiave() {
    local chiave; chiave="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
    if [[ -f .env ]] && grep -q '^DJANGO_SECRET_KEY=' .env; then
        sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$chiave|" .env
        ok "nuova DJANGO_SECRET_KEY scritta nel .env"
    else
        echo "DJANGO_SECRET_KEY=$chiave"
    fi
}

comando_pulisci() {
    compose --profile dev --profile build --profile deploy down -v
    rm -rf dist frontend/public/media
    ok "container, volumi e build rimossi."
}

comando_aiuto() {
    cat <<'AIUTO'
canizzano.it — gestione dello stack locale

  COMANDI PRINCIPALI
    avvia         Avvia PostgreSQL + CMS Django (redazione su :8000/admin/)
    dev           Anteprima del sito con ricarica automatica (:4321)
    ferma-dev     Ferma solo l'anteprima (CMS e database restano accesi)
    build         Genera il sito statico in ./dist
    pubblica      Carica ./dist sull'hosting via FTP (fa il build se manca)
    tutto         build + pubblica

  ASSISTENTE AI
    mcp           Indirizzo e chiave per collegare un agente AI al CMS
                  («mcp --nuova --nome "..."» ne crea un'altra)

  UTILITÀ
    prova-ftp     Simula il caricamento FTP senza scrivere sul server
    stato         Mostra i container attivi
    log [servizio] Segue i log (default: backend)
    gestisci ...  Esegue un comando manage.py di Django nel container
    esempi        Popola il CMS con eventi d'esempio
    backup        Esporta il database in ./backup
    verifica-db   Mostra tabelle e migrazioni: non modifica nulla
    ripristina-db Ricrea il database quando lo schema e' rimasto indietro
                  (perde gli eventi inseriti, tiene le foto)
    chiave        Genera e scrive una nuova DJANGO_SECRET_KEY nel .env
    ferma         Ferma tutti i container
    pulisci       Ferma tutto ed elimina volumi e build (ATTENZIONE: cancella i dati)
AIUTO
}

case "${1:-aiuto}" in
    avvia|up)          shift; comando_avvia "$@" ;;
    dev)               shift; comando_dev "$@" ;;
    ferma-dev)         shift; comando_ferma_dev "$@" ;;
    build)             shift; comando_build "$@" ;;
    pubblica|deploy)   shift; comando_pubblica "$@" ;;
    tutto|all)         shift; comando_tutto "$@" ;;
    prova-ftp)         shift; comando_prova_ftp "$@" ;;
    stato|ps)          shift; comando_stato "$@" ;;
    log|logs)          shift; comando_log "$@" ;;
    gestisci|manage)   shift; comando_gestisci "$@" ;;
    ripristina-db)     shift; comando_ripristina_db "$@" ;;
    verifica-db)       shift; comando_verifica_db "$@" ;;
    mcp|assistente)    shift; comando_mcp "$@" ;;
    esempi)            shift; comando_esempi "$@" ;;
    backup)            shift; comando_backup "$@" ;;
    chiave)            shift; comando_chiave "$@" ;;
    ferma|down)        shift; comando_ferma "$@" ;;
    pulisci|clean)     shift; comando_pulisci "$@" ;;
    aiuto|help|-h|--help) comando_aiuto ;;
    *) echo "Comando sconosciuto: $1" >&2; echo; comando_aiuto; exit 1 ;;
esac
