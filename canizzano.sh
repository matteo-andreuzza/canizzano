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
#  Gli stessi comandi hanno un bottone nella dashboard della redazione, su
#  http://localhost:8000/riservata/ — a premerli e' il container «esecutore»,
#  che «avvia» accende insieme al resto.
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

# ── Adattamento alla macchina ────────────────────────────────────────────────
#
# Niente di quello che segue va scritto a mano: si ricava tutto al volo, cosi'
# lo stesso repo gira su questo portatile, su un Raspberry Pi o su un server
# senza modifiche. Ogni valore resta comunque scavalcabile — prima
# dall'ambiente, poi dal .env — per le macchine fuori standard.

# Legge una variabile dal .env senza caricarlo tutto: il .env contiene anche
# password, e non vogliamo esportarle nell'ambiente di ogni comando.
da_env() {
    [[ -f .env ]] || return 0
    grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true
}

# stat -c e' GNU (Linux), stat -f e' BSD (macOS): proviamo entrambi.
proprietario() {  # proprietario <percorso> <u|g>
    stat -c "%$2" "$1" 2>/dev/null || stat -f "%$2" "$1" 2>/dev/null || true
}

# La cartella del progetto, comunicata esplicitamente a compose. Senza,
# compose ripiega su ${PWD}, che e' giusto solo se lo si lancia da qui.
export CARTELLA_PROGETTO="$CARTELLA"

# Il container di build scrive in ./dist, e il CMS scrive in coda/: a
# entrambi passiamo l'utente dell'host, cosi' i file restano nostri.
#
#  • dall'ambiente: e' il container «esecutore» che lancia questo script, e
#    «id -u» risponderebbe per il container invece che per l'host;
#  • da SUDO_UID: sotto «sudo» l'utente vero e' chi ha invocato il comando —
#    senza questo, «sudo ./canizzano.sh avvia» proverebbe a creare nel
#    container un utente con uid 0 e il build morirebbe con
#    «useradd: UID 0 is not unique».
export UID_HOST GID_HOST
UID_HOST="${UID_HOST:-$(da_env UID_HOST)}"
GID_HOST="${GID_HOST:-$(da_env GID_HOST)}"
UID_HOST="${UID_HOST:-${SUDO_UID:-$(id -u)}}"
GID_HOST="${GID_HOST:-${SUDO_GID:-$(id -g)}}"

# Restiamo comunque senza un uid utilizzabile se si gira da root in un guscio
# che non viene da sudo: ripieghiamo su chi possiede la cartella del progetto,
# e in ultima istanza sul primo utente del sistema.
if [[ "$UID_HOST" == "0" ]]; then
    UID_HOST="$(proprietario "$CARTELLA" u)"; GID_HOST="$(proprietario "$CARTELLA" g)"
fi
UID_HOST="${UID_HOST:-1000}"; GID_HOST="${GID_HOST:-1000}"
[[ "$UID_HOST" == "0" ]] && { UID_HOST=1000; GID_HOST=1000; }

# L'esecutore parla col demone Docker attraverso il socket dell'host. Per
# aprirlo senza girare da root gli serve il gruppo proprietario del socket,
# che cambia da macchina a macchina. Il percorso e' quello standard, ma le
# installazioni rootless lo mettono altrove: si scavalca dal .env.
export DOCKER_SOCKET DOCKER_GID
DOCKER_SOCKET="${DOCKER_SOCKET:-$(da_env DOCKER_SOCKET)}"
DOCKER_SOCKET="${DOCKER_SOCKET:-/var/run/docker.sock}"
DOCKER_GID="${DOCKER_GID:-$(proprietario "$DOCKER_SOCKET" g)}"
DOCKER_GID="${DOCKER_GID:-999}"

# Il bot del foglietto parrocchiale vive in un repository suo (canizzano-mcp),
# in un container suo, raggiunto dall'esecutore via HTTP sulla rete Docker
# condivisa (vedi «networks:» in compose.yaml) — non c'e' nessun percorso su
# disco da conoscere qui. BOT_FOGLIETTO_URL e BOT_FOGLIETTO_TOKEN li legge
# compose.yaml direttamente da questo .env (`environment:` dell'esecutore):
# niente da esportare o dedurre in questo script.

# ── Registro delle attivita' ─────────────────────────────────────────────────
#
# Un file JSON Lines condiviso: una riga per evento, sempre nella stessa forma
#
#   {"timestamp": "...ISO8601...", "processo": "...", "stato": "ok"|"errore",
#    "dettaglio": "..."}
#
# Ci scrivono questo script e il container «esecutore»; ci scriveranno lo
# scraper del foglietto parrocchiale e l'OCR del libretto quando esisteranno.
# La dashboard lo legge senza sapere nulla di chi ha scritto: aggiungere un
# processo non richiede di toccare ne' il formato ne' la pagina.
#
# La stessa scrittura esiste anche in esecutore/esecutore.py: i due girano in
# ambienti diversi (host e container) e nessuno dei due puo' importare l'altro.

CARTELLA_LOG="$CARTELLA/logs"
FILE_ATTIVITA="$CARTELLA_LOG/attivita.log"
CARTELLA_CODA="$CARTELLA/coda"

# registra <processo> <ok|errore> [file con il dettaglio]
# Il dettaglio arriva da un file e non da un argomento: l'output di lftp su
# tutto il sito supera comodamente la lunghezza massima della riga di comando.
registra() {
    local processo="$1" stato="$2" sorgente="${3:-}"
    # L'esecutore scrive lui la riga, con l'identificativo del lavoro: se
    # scrivessimo anche noi, la dashboard vedrebbe ogni comando due volte.
    [[ -n "${CANIZZANO_SENZA_LOG:-}" ]] && return 0
    command -v python3 >/dev/null 2>&1 || return 0
    mkdir -p "$CARTELLA_LOG" 2>/dev/null || return 0
    python3 - "$processo" "$stato" "$sorgente" "$FILE_ATTIVITA" <<'PY' || true
import datetime, json, re, sys

processo, stato, sorgente, destinazione = sys.argv[1:5]

dettaglio = ""
if sorgente:
    try:
        with open(sorgente, encoding="utf-8", errors="replace") as f:
            dettaglio = f.read()
    except OSError:
        pass

# I codici colore servono al terminale, non a una pagina HTML.
dettaglio = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", dettaglio)

# Le righe di avanzamento di BuildKit («#7 1.537 (9/15) Installing …») sono
# centinaia e non dicono niente a chi legge la dashboard. Si tolgono solo se
# il comando e' riuscito: quando fallisce, l'errore sta proprio li'.
if stato == "ok":
    dettaglio = "\n".join(
        r for r in dettaglio.splitlines() if not re.match(r"^#\d+ ", r)
    )
    dettaglio = re.sub(r"\n{3,}", "\n\n", dettaglio)

dettaglio = dettaglio.strip()

TETTO = 16000
if len(dettaglio) > TETTO:
    meta = TETTO // 2
    omessi = len(dettaglio) - TETTO
    dettaglio = (
        f"{dettaglio[:meta]}\n\n[… {omessi} caratteri omessi …]\n\n{dettaglio[-meta:]}"
    )

riga = json.dumps(
    {
        "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "processo": processo,
        "stato": stato,
        "dettaglio": dettaglio,
    },
    ensure_ascii=False,
)
try:
    with open(destinazione, "a", encoding="utf-8") as f:
        f.write(riga + "\n")
except OSError as errore:
    print(f"! non riesco a scrivere il registro: {errore}", file=sys.stderr)
PY
}

# con_log <etichetta> <comando...> — esegue e registra l'esito, lasciando
# passare a schermo tutto l'output e restituendo il codice di uscita vero.
con_log() {
    local etichetta="$1"; shift
    if [[ -n "${CANIZZANO_SENZA_LOG:-}" ]]; then
        "$@"
        return
    fi

    local traccia uscita
    traccia="$(mktemp)"
    # «set +e» perche' l'errore lo vogliamo registrare, non subire: senza,
    # «set -e» farebbe uscire lo script prima della riga di log.
    set +e
    "$@" 2>&1 | tee "$traccia"
    uscita=${PIPESTATUS[0]}
    set -e

    if [[ $uscita -eq 0 ]]; then
        registra "$etichetta" ok "$traccia"
    elif [[ $uscita -eq 130 || $uscita -eq 143 ]]; then
        # Ctrl+C su «dev» e' il modo normale di chiudere l'anteprima.
        printf '\nfermato dall'\''utente.\n' >> "$traccia"
        registra "$etichetta" ok "$traccia"
    else
        printf '\nil comando è uscito con codice %s.\n' "$uscita" >> "$traccia"
        registra "$etichetta" errore "$traccia"
    fi

    rm -f "$traccia"
    return $uscita
}

# Le due cartelle condivise col container del CMS. Vanno create da qui, prima
# che parta il compose: se le crea Docker montandole, nascono di root e ne'
# Django ne' l'esecutore riescono a scriverci.
prepara_cartelle() {
    mkdir -p "$CARTELLA_LOG" "$CARTELLA_CODA/in-corso"
    [[ -e "$FILE_ATTIVITA" ]] || : > "$FILE_ATTIVITA"
    # Se questo script gira da root (sudo, o un servizio di sistema), quello
    # che ha appena creato appartiene a root e Django — che nel container gira
    # con l'uid dell'host — non riuscirebbe a scriverci. Da root il chown
    # riesce; negli altri casi e' un no-op che puo' fallire senza conseguenze.
    chown -R "$UID_HOST:$GID_HOST" "$CARTELLA_LOG" "$CARTELLA_CODA" 2>/dev/null || true
}

# Deve combaciare con «name:» in compose.yaml: i volumi ne prendono il prefisso.
NOME_PROGETTO=canizzano

compose() {
    trova_docker
    "${DOCKER[@]}" compose "$@"
}

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

# L'esecutore e' il braccio operativo della dashboard: il container che riceve
# i comandi premuti su /riservata/ e li esegue qui. Sta fuori dal giro di
# «avvia» apposta — nessun comando della dashboard lo ricrea, altrimenti si
# spegnerebbe da solo a meta' lavoro.
avvia_esecutore() {
    # Quando e' proprio l'esecutore a lanciare questo script, ricrearlo
    # vorrebbe dire uccidere il processo che sta eseguendo il comando.
    [[ -n "${CANIZZANO_ESECUTORE:-}" ]] && return 0
    compose up -d --build esecutore
}

comando_avvia() {
    verifica_env
    prepara_cartelle
    info "avvio database e CMS…"
    compose up -d --build db backend
    attendi_cms
    avvia_esecutore
    local porta; porta="$(grep -E '^CMS_PORT=' .env | cut -d= -f2 || true)"
    ok "redazione aperta su http://localhost:${porta:-8000}/admin/"
    ok "dashboard su http://localhost:${porta:-8000}/riservata/"
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

# Come «dev», ma senza restare in primo piano: e' la forma che serve al
# bottone della dashboard, che non ha un terminale su cui premere Ctrl+C.
# L'anteprima resta accesa e si spegne con «ferma-dev».
comando_dev_sfondo() {
    comando_avvia
    compose --profile dev rm --stop --force dev >/dev/null 2>&1 || true
    compose --profile dev up -d --build --force-recreate dev
    local porta; porta="$(grep -E '^DEV_PORT=' .env | cut -d= -f2 || true)"
    ok "anteprima accesa su http://localhost:${porta:-4321} — si ferma con «ferma-dev»."
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
    avvia         Avvia PostgreSQL + CMS Django (redazione su :8000/admin/,
                  dashboard su :8000/riservata/)
    dev           Anteprima del sito con ricarica automatica (:4321)
    dev-sfondo    Come «dev» ma senza restare in primo piano (usato dalla
                  dashboard: l'anteprima si ferma con «ferma-dev»)
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
    avvia|up)          shift; con_log "canizzano.sh avvia" comando_avvia "$@" ;;
    dev)               shift; con_log "canizzano.sh dev" comando_dev "$@" ;;
    dev-sfondo)        shift; con_log "canizzano.sh dev-sfondo" comando_dev_sfondo "$@" ;;
    ferma-dev)         shift; con_log "canizzano.sh ferma-dev" comando_ferma_dev "$@" ;;
    build)             shift; comando_build "$@" ;;
    pubblica|deploy)   shift; comando_pubblica "$@" ;;
    tutto|all)         shift; con_log "canizzano.sh tutto" comando_tutto "$@" ;;
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
