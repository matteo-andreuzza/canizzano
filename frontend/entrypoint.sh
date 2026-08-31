#!/bin/sh
# Genera il sito statico (o avvia il dev server) e consegna dist/ all'host.
set -eu

MEDIA_SORGENTE="${MEDIA_SORGENTE:-/media}"
CARTELLA_USCITA="${CARTELLA_USCITA:-/output}"

# Le immagini caricate in admin vivono nel volume condiviso col CMS.
# Copiandole in public/ finiscono dentro dist/ e quindi sul server FTP.
sincronizza_media() {
    if [ -d "$MEDIA_SORGENTE" ]; then
        mkdir -p /app/public/media
        rsync -a --delete "$MEDIA_SORGENTE/" /app/public/media/
        echo "→ media sincronizzati da $MEDIA_SORGENTE"
    else
        echo "→ nessuna cartella media in $MEDIA_SORGENTE: la salto"
    fi
}

case "${1:-build}" in
    build)
        sincronizza_media
        echo "→ build del sito statico…"
        npm run build
        if [ -d "$CARTELLA_USCITA" ]; then
            rsync -a --delete /app/dist/ "$CARTELLA_USCITA/"
            # Senza questo dist/ resterebbe di root sull'host e non si
            # potrebbe cancellare senza sudo.
            if [ -n "${UID_HOST:-}" ]; then
                chown -R "$UID_HOST:${GID_HOST:-$UID_HOST}" "$CARTELLA_USCITA"
            fi
            echo "→ sito pronto in $CARTELLA_USCITA"
        fi
        ;;
    dev)
        sincronizza_media
        # Astro segna il server di sviluppo con un lock in .astro/dev.json e
        # lo cancella solo se lo spegni con garbo. Un container fermato di
        # colpo lo lascia li', e al riavvio Astro crede che ci sia gia' un
        # server acceso: il controllo si basa sul PID, che dentro a un
        # container viene riassegnato da zero. Lo togliamo noi.
        rm -f /app/.astro/dev.json /app/.astro/dev.log
        exec npm run dev
        ;;
    preview)
        exec npm run preview
        ;;
    *)
        exec "$@"
        ;;
esac
