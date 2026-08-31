#!/bin/sh
# Carica il sito generato sull'hosting statico via FTP/FTPS.
#
# Usa `lftp mirror`: trasferisce solo i file cambiati e, a fine mirror,
# rimuove dal server quelli non piu' presenti in locale.
set -eu

SORGENTE="${SORGENTE:-/sito}"
: "${FTP_HOST:?FTP_HOST non impostato: compila il file .env}"
: "${FTP_USER:?FTP_USER non impostato: compila il file .env}"
: "${FTP_PASSWORD:?FTP_PASSWORD non impostato: compila il file .env}"

FTP_PORT="${FTP_PORT:-21}"
FTP_REMOTE_DIR="${FTP_REMOTE_DIR:-/}"
FTP_PROTOCOLLO="${FTP_PROTOCOLLO:-ftp}"     # ftp | ftps
FTP_VERIFICA_CERTIFICATO="${FTP_VERIFICA_CERTIFICATO:-true}"
DRY_RUN="${DRY_RUN:-false}"
PARALLELI="${FTP_TRASFERIMENTI_PARALLELI:-4}"

if [ ! -d "$SORGENTE" ] || [ -z "$(ls -A "$SORGENTE" 2>/dev/null)" ]; then
    echo "✗ $SORGENTE e' vuota: esegui prima il build del sito." >&2
    exit 1
fi

if [ "$FTP_PROTOCOLLO" = "ftps" ]; then
    IMPOSTAZIONI_TLS="set ftp:ssl-force true; set ftp:ssl-protect-data true;"
else
    IMPOSTAZIONI_TLS="set ftp:ssl-allow ${FTP_SSL_ALLOW:-true};"
fi

OPZIONI_MIRROR="--reverse --delete --verbose --parallel=$PARALLELI \
    --exclude-glob .DS_Store --exclude-glob .git*"
[ "$DRY_RUN" = "true" ] && OPZIONI_MIRROR="$OPZIONI_MIRROR --dry-run"

echo "→ carico $SORGENTE su ftp://$FTP_HOST:$FTP_PORT$FTP_REMOTE_DIR"
[ "$DRY_RUN" = "true" ] && echo "  (prova a vuoto: nessun file verra' scritto)"

# La password arriva a lftp dall'ambiente: non finisce nella riga di comando.
LFTP_PASSWORD="$FTP_PASSWORD" lftp -u "$FTP_USER" --env-password \
    -p "$FTP_PORT" "$FTP_HOST" <<LFTP
set cmd:fail-exit true;
set ssl:verify-certificate $FTP_VERIFICA_CERTIFICATO;
set ftp:passive-mode ${FTP_PASSIVO:-true};
set net:max-retries 3;
set net:timeout 20;
$IMPOSTAZIONI_TLS
mirror $OPZIONI_MIRROR "$SORGENTE" "$FTP_REMOTE_DIR";
bye
LFTP

echo "✓ sito pubblicato su $FTP_HOST$FTP_REMOTE_DIR"
