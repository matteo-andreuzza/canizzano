#!/usr/bin/env python3
"""Esegue i comandi chiesti dai bottoni della dashboard riservata.

Il giro completo:

    browser ──POST──▶ Django (container «backend»)
                          │  scrive coda/<id>.json  (bind mount sull'host)
                          ▼
                      coda/  ◀──── questo processo legge ogni mezzo secondo
                          │
                          │  subprocess.run(["canizzano.sh", <comando>])
                          ▼
                   logs/attivita.log  (JSON Lines)
                          │
    browser ◀──polling──  Django rilegge il registro e mostra l'esito

Django non esegue mai nulla: si limita a depositare un lavoro. Il motivo sta
nel Dockerfile qui accanto.

La coda e' un confine di fiducia: chi riesce a scriverci dentro ottiene
l'esecuzione di uno dei comandi in COMANDI. Per questo la lista bianca e'
ripetuta qui e non arriva mai dal file del lavoro: il nome del comando passato
allo script esce sempre da questo dizionario, mai dal contenuto del JSON.

C'e' un secondo giro, piu' corto, per il bot del foglietto parrocchiale: la',
invece di eseguire, si fa una richiesta HTTP al suo container, sulla rete
Docker condivisa. Vedi avvia_foglietto().
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Configurazione ──────────────────────────────────────────────────────────

SCRIPT = Path(os.environ.get("CANIZZANO_SCRIPT", "/progetto/canizzano.sh"))
CODA = Path(os.environ.get("CANIZZANO_CODA", "/progetto/coda"))
REGISTRO = Path(os.environ.get("CANIZZANO_REGISTRO", "/progetto/logs/attivita.log"))

def _tetto(nome: str, predefinito: int) -> int:
    """Timeout in secondi, scavalcabile dall'ambiente.

    Serve alle macchine lente: su un Raspberry Pi lo stesso build puo'
    metterci un ordine di grandezza in piu' che su un portatile. I valori
    predefiniti sono larghi apposta — il timeout esiste per non restare
    appesi in eterno, non per misurare quanto e' veloce la macchina.
    """
    try:
        return max(60, int(os.environ.get(nome, predefinito)))
    except ValueError:
        return predefinito


# Lista bianca fissa: chiave usata dalla dashboard → (sottocomando dello
# script, timeout in secondi).
COMANDI: dict[str, tuple[str, int]] = {
    "avvia": ("avvia", _tetto("TIMEOUT_AVVIA", 1800)),
    "dev": ("dev-sfondo", _tetto("TIMEOUT_DEV", 1800)),
    "ferma-dev": ("ferma-dev", _tetto("TIMEOUT_FERMA_DEV", 300)),
    "tutto": ("tutto", _tetto("TIMEOUT_TUTTO", 7200)),
}

# ── Il bot del foglietto parrocchiale ───────────────────────────────────────
#
# Vive in un repository suo (canizzano-mcp), in un container suo, e non passa
# da canizzano.sh: e' l'unico comando della dashboard che non esegue niente
# qui dentro, chiede a un altro container di farlo.
#
# Il container del bot espone un endpoint HTTP (/attiva) protetto da un
# token condiviso, raggiungibile solo sulla rete Docker esterna che i due
# stack hanno in comune (vedi «networks:» nel compose.yaml di entrambi i
# repository — non e' mai pubblicato su una porta dell'host). Noi scriviamo
# nel registro che il bottone e' stato premuto e come e' andata la
# *consegna* della richiesta; l'esito vero dell'elaborazione lo scrive il
# bot stesso, col suo nome di processo, quando avra' finito.
BOT_FOGLIETTO_URL = os.environ.get("BOT_FOGLIETTO_URL", "").strip()
BOT_FOGLIETTO_TOKEN = os.environ.get("BOT_FOGLIETTO_TOKEN", "").strip()

# Il container del bot risponde subito (occupato/libero) e basta: non c'e'
# niente da aspettare oltre al tempo di una richiesta HTTP.
TIMEOUT_FOGLIETTO = _tetto("TIMEOUT_FOGLIETTO", 10)

# Il nome che compare nel registro per l'atto di aver premuto il bottone,
# tenuto distinto da «scraper_foglietto» e «ocr_redazione_foglietto», che sono
# le righe che scrive il bot per il proprio esito.
PROCESSO_FOGLIETTO = "avvio_manuale_foglietto"

IN_CORSO = CODA / "in-corso"
BATTITO = CODA / ".vivo"
INTERVALLO = 0.5

# Un lavoro piu' vecchio di cosi' non si esegue piu'. Serve al caso in cui la
# macchina si spegne subito dopo il clic: senza, al ritorno della corrente —
# magari ore dopo, con nessuno davanti allo schermo — l'esecutore troverebbe
# la richiesta in coda e pubblicherebbe il sito per conto suo.
ETA_MASSIMA = _tetto("ETA_MASSIMA_LAVORO", 600)

# Ogni quanto ricontrollare di riuscire a parlare col demone Docker.
CONTROLLO_DOCKER = 30

# Il dettaglio finisce in una pagina HTML: l'output di lftp su tutto il sito
# puo' essere enorme. Teniamo la testa (cosa stava facendo) e la coda (come e'
# finita), che sono le due parti che servono davvero a capire.
TETTO_DETTAGLIO = 16000
COLORI_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Le righe di avanzamento di BuildKit («#7 1.537 (9/15) Installing …»): sono
# centinaia, e a chi legge la dashboard non dicono niente. Si tolgono solo
# quando il comando e' andato bene — se e' fallito, l'errore e' proprio li'
# dentro e va mostrato per intero.
RUMORE_BUILD = re.compile(r"^#\d+ ")
RIGHE_VUOTE = re.compile(r"\n{3,}")

_fermati = False

# Stato dell'accesso a Docker, aggiornato ogni CONTROLLO_DOCKER secondi e
# pubblicato nel file del battito perche' la dashboard possa dirlo.
_docker_ok = True
_docker_perche = ""
_ultimo_controllo = 0.0


# ── Utilita' ────────────────────────────────────────────────────────────────


def adesso() -> str:
    """Timestamp ISO 8601 con fuso orario, al secondo."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def accorcia(testo: str, tutto: bool = False) -> str:
    testo = COLORI_ANSI.sub("", testo)
    if not tutto:
        testo = "\n".join(r for r in testo.splitlines() if not RUMORE_BUILD.match(r))
        testo = RIGHE_VUOTE.sub("\n\n", testo)
    testo = testo.strip()
    if len(testo) <= TETTO_DETTAGLIO:
        return testo
    meta = TETTO_DETTAGLIO // 2
    tagliati = len(testo) - TETTO_DETTAGLIO
    return f"{testo[:meta]}\n\n[… {tagliati} caratteri omessi …]\n\n{testo[-meta:]}"


def registra(processo: str, stato: str, dettaglio: str, identificativo: str = "") -> None:
    """Appende una riga al registro condiviso, in formato JSON Lines.

    Stesso schema che useranno lo scraper del foglietto e l'OCR del libretto:
    timestamp / processo / stato / dettaglio. Le chiavi in piu' («id») sono
    ammesse — chi legge ignora quello che non conosce.
    """
    riga = {
        "timestamp": adesso(),
        "processo": processo,
        "stato": stato,
        "dettaglio": accorcia(dettaglio, tutto=(stato != "ok")),
    }
    if identificativo:
        riga["id"] = identificativo
    try:
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        with REGISTRO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(riga, ensure_ascii=False) + "\n")
    except OSError as errore:
        # Il registro e' un di piu': se non si riesce a scriverlo, il comando
        # e' comunque stato eseguito. Meglio un messaggio nei log del
        # container che un esecutore che muore.
        print(f"! non riesco a scrivere {REGISTRO}: {errore}", file=sys.stderr)


def controlla_docker() -> None:
    """Verifica di riuscire a parlare col demone Docker, ogni tanto.

    Senza questo controllo un esecutore che non arriva al socket sembra sano:
    il battito continua, la dashboard scrive «pronta», e ogni bottone
    risponde «uscito con codice 1» senza una riga di spiegazione — perche'
    canizzano.sh manda quell'errore su stderr, che in alcuni sottocomandi e'
    rediretto a /dev/null. Succede, per esempio, se lo stack viene tirato su
    con «docker compose up» invece che con «./canizzano.sh avvia»: il gruppo
    del socket lo calcola lo script, e senza di lui resta quello di ripiego.
    """
    global _docker_ok, _docker_perche, _ultimo_controllo

    if time.monotonic() - _ultimo_controllo < CONTROLLO_DOCKER:
        return
    _ultimo_controllo = time.monotonic()

    prima = _docker_ok
    try:
        esito = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        _docker_ok = esito.returncode == 0
        _docker_perche = "" if _docker_ok else (esito.stderr or esito.stdout).strip()[:500]
    except (OSError, subprocess.TimeoutExpired) as errore:
        _docker_ok = False
        _docker_perche = str(errore)[:500]

    if prima and not _docker_ok:
        print(f"✗ non raggiungo il demone Docker: {_docker_perche}", file=sys.stderr, flush=True)
    elif _docker_ok and not prima:
        print("→ demone Docker di nuovo raggiungibile.", flush=True)


def batti() -> None:
    """Aggiorna il file del battito: dice che siamo vivi e se Docker risponde.

    La data di modifica basta alla dashboard per sapere che qualcuno ascolta;
    il contenuto le serve a distinguere «pronta» da «viva ma inutile».
    """
    try:
        BATTITO.write_text(
            json.dumps({"docker": _docker_ok, "perche": _docker_perche}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


# ── Il bot del foglietto ────────────────────────────────────────────────────


def avvia_foglietto(lavoro: dict, identificativo: str) -> None:
    """Chiede al bot del foglietto di partire adesso, senza aspettarlo.

    Una singola POST /attiva, con un timeout breve: il container del bot
    risponde subito (occupato o libero), non fa aspettare l'esecutore fino a
    elaborazione finita. La riga che scriviamo nel registro dice sempre
    «richiesta consegnata» o perche' non lo e' stata — mai «foglietto
    elaborato»: l'esito vero arriva dopo, quando il bot avra' finito, e la
    dashboard lo mostrera' da sola alla prossima lettura della cronologia.
    """
    if not BOT_FOGLIETTO_URL:
        registra(
            PROCESSO_FOGLIETTO,
            "errore",
            "Non so dove sia il bot del foglietto: BOT_FOGLIETTO_URL non è "
            "impostata. Scrivi l'indirizzo del suo container nel .env e rilancia "
            "«./canizzano.sh avvia».",
            identificativo,
        )
        return

    richiesta = urllib.request.Request(
        BOT_FOGLIETTO_URL,
        method="POST",
        headers={"Authorization": f"Bearer {BOT_FOGLIETTO_TOKEN}"},
        data=b"",
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT_FOGLIETTO) as risposta:
            risposta.read()  # scarichiamo il corpo solo per chiudere pulito la connessione
    except urllib.error.HTTPError as errore:
        if errore.code == 409:
            registra(
                PROCESSO_FOGLIETTO,
                "errore",
                "Esecuzione già in corso, avvio ignorato.\n\n"
                "Il bot sta già lavorando — di solito perché è partito da solo "
                "poco fa (lo scheduler interno gira ogni mezz'ora). Non serve "
                "fare niente: quando avrà finito, l'esito comparirà qui nel "
                "registro.",
                identificativo,
            )
        elif errore.code in (401, 403):
            registra(
                PROCESSO_FOGLIETTO,
                "errore",
                f"Il bot ha rifiutato la richiesta (HTTP {errore.code}): "
                "BOT_FOGLIETTO_TOKEN non corrisponde a quello impostato nel .env "
                "del bot (ATTIVA_TOKEN). Controlla che siano la stessa stringa "
                "nei due repository.",
                identificativo,
            )
        else:
            registra(
                PROCESSO_FOGLIETTO,
                "errore",
                f"Il bot ha risposto con un errore inatteso (HTTP {errore.code}): "
                f"{errore.reason}",
                identificativo,
            )
        return
    except urllib.error.URLError as errore:
        # Connessione rifiutata, host sconosciuto, timeout: il bot è spento,
        # non è ancora stato avviato, o la rete Docker condivisa non esiste
        # ancora. Un esito chiaro in dashboard, non un timeout silenzioso.
        registra(
            PROCESSO_FOGLIETTO,
            "errore",
            f"Non riesco a raggiungere il bot del foglietto su {BOT_FOGLIETTO_URL} "
            f"({errore.reason}).\n\n"
            "Controlla che il container del bot sia acceso (nel suo repository: "
            "«docker compose up -d») e che la rete Docker condivisa esista "
            "(«docker network create canizzano_rete», una tantum) e sia "
            "referenziata allo stesso modo nei due .env.",
            identificativo,
        )
        return

    registra(
        PROCESSO_FOGLIETTO,
        "ok",
        "Richiesta consegnata al bot del foglietto.\n\n"
        "Adesso scarica il foglietto, lo legge e scrive nel CMS quello che trova: "
        "ci vogliono alcuni minuti. Non pubblica niente sul sito — al massimo "
        "lascia contenuti da rivedere in redazione.\n\n"
        "Com'è andata lo scrive lui qui nel registro, sotto «scraper_foglietto» e "
        "«ocr_redazione_foglietto», e nella mail di riepilogo.",
        identificativo,
    )


# ── Ciclo di lavoro ─────────────────────────────────────────────────────────


def esegui(lavoro: dict, percorso: Path) -> None:
    azione = lavoro.get("azione")
    identificativo = str(lavoro.get("id") or percorso.stem)

    if azione not in COMANDI and azione != "foglietto":
        registra(
            f"azione sconosciuta: {azione!r}",
            "errore",
            "Il lavoro chiedeva un comando che non è nella lista consentita: ignorato.",
            identificativo,
        )
        percorso.unlink(missing_ok=True)
        return

    if azione == "foglietto":
        processo = PROCESSO_FOGLIETTO
        sottocomando, timeout = "", 0
    else:
        sottocomando, timeout = COMANDI[azione]
        processo = f"canizzano.sh {sottocomando}"

    # Una richiesta che ha aspettato troppo non si esegue: quasi sempre vuol
    # dire che la macchina si e' spenta subito dopo il clic, e nessuno si
    # aspetta che il sito venga pubblicato al ritorno della corrente.
    try:
        eta = time.time() - percorso.stat().st_mtime
    except OSError:
        eta = 0.0
    if eta > ETA_MASSIMA:
        registra(
            processo,
            "errore",
            f"Non eseguito: la richiesta era ferma in coda da {int(eta // 60)} minuti. "
            "Di solito succede quando la macchina si spegne subito dopo il clic. "
            "Se serve ancora, premi di nuovo il bottone.",
            identificativo,
        )
        percorso.unlink(missing_ok=True)
        return

    # Il foglietto non passa da «in-corso»: non c'e' niente da eseguire, si
    # deposita una richiesta e si scrive subito com'e' andata la consegna.
    if azione == "foglietto":
        avvia_foglietto(lavoro, identificativo)
        percorso.unlink(missing_ok=True)
        return

    # Sposto il lavoro in «in-corso» prima di partire: e' cosi' che la
    # dashboard distingue «in coda» da «in esecuzione», ed e' anche il modo in
    # cui ci si accorge, al riavvio, di un lavoro rimasto a meta'.
    IN_CORSO.mkdir(parents=True, exist_ok=True)
    attivo = IN_CORSO / percorso.name
    try:
        percorso.rename(attivo)
    except OSError:
        percorso.unlink(missing_ok=True)
        return

    ambiente = dict(os.environ)
    # Lo script, quando gira qui dentro, non deve scrivere lui la riga di
    # registro: la scriviamo noi con l'id del lavoro, cosi' la dashboard sa
    # quale bottone ha prodotto quale esito e non si vedono righe doppie.
    ambiente["CANIZZANO_SENZA_LOG"] = "1"
    # Marcatore che dice allo script «sei dentro all'esecutore»: gli impedisce
    # di ricreare il container in cui sta girando.
    ambiente["CANIZZANO_ESECUTORE"] = "1"

    inizio = time.monotonic()
    try:
        esito = subprocess.run(
            [str(SCRIPT), sottocomando],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SCRIPT.parent),
            env=ambiente,
            check=True,
        )
        uscita = (esito.stdout or "") + (esito.stderr or "")
        registra(processo, "ok", uscita or "Comando eseguito senza output.", identificativo)
    except subprocess.CalledProcessError as errore:
        uscita = (errore.stdout or "") + (errore.stderr or "")
        registra(
            processo,
            "errore",
            uscita or f"Il comando è uscito con codice {errore.returncode}.",
            identificativo,
        )
    except subprocess.TimeoutExpired as errore:
        parziale = (errore.stdout or "") + (errore.stderr or "")
        if isinstance(parziale, bytes):  # pragma: no cover - solo se text=False
            parziale = parziale.decode("utf-8", "replace")
        registra(
            processo,
            "errore",
            f"Interrotto dopo {timeout} secondi senza terminare.\n\n{parziale}",
            identificativo,
        )
    except OSError as errore:
        registra(processo, "errore", f"Non riesco a eseguire {SCRIPT}: {errore}", identificativo)
    finally:
        durata = round(time.monotonic() - inizio, 1)
        print(f"→ {processo} concluso in {durata}s", flush=True)
        attivo.unlink(missing_ok=True)


def recupera_interrotti() -> None:
    """Chiude i lavori rimasti appesi da un'esecuzione precedente.

    Se il container e' stato fermato mentre un comando era in corso, il file
    resta in «in-corso» e la dashboard aspetterebbe per sempre una riga che
    nessuno scrivera' piu'. Meglio dirlo.
    """
    if not IN_CORSO.is_dir():
        return
    for percorso in sorted(IN_CORSO.glob("*.json")):
        try:
            lavoro = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            lavoro = {}
        azione = lavoro.get("azione", "?")
        if azione == "foglietto":
            processo = PROCESSO_FOGLIETTO
        else:
            processo = f"canizzano.sh {COMANDI.get(azione, (azione, 0))[0]}"
        registra(
            processo,
            "errore",
            "L'esecutore si è fermato mentre il comando era in corso: esito sconosciuto.",
            str(lavoro.get("id") or percorso.stem),
        )
        percorso.unlink(missing_ok=True)


def chiudi(numero, _frame) -> None:
    global _fermati
    _fermati = True
    print(f"→ ricevuto segnale {numero}, esco.", flush=True)


def main() -> int:
    signal.signal(signal.SIGTERM, chiudi)
    signal.signal(signal.SIGINT, chiudi)

    CODA.mkdir(parents=True, exist_ok=True)
    IN_CORSO.mkdir(parents=True, exist_ok=True)

    if not SCRIPT.is_file():
        print(f"✗ non trovo {SCRIPT}: la cartella del progetto è montata?", file=sys.stderr)
        return 1

    recupera_interrotti()
    print(f"→ esecutore in ascolto su {CODA} (script: {SCRIPT})", flush=True)
    if BOT_FOGLIETTO_URL:
        print(f"→ bot del foglietto: {BOT_FOGLIETTO_URL}", flush=True)

    while not _fermati:
        # Il battito dice alla dashboard che qualcuno sta ascoltando: senza,
        # un bottone premuto con l'esecutore spento resterebbe «in attesa»
        # all'infinito senza spiegare perche'.
        controlla_docker()
        batti()

        # I lavori si prendono in ordine di nome: l'id comincia col timestamp,
        # quindi e' anche l'ordine di arrivo.
        for percorso in sorted(CODA.glob("*.json")):
            if _fermati:
                break
            try:
                lavoro = json.loads(percorso.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # File a meta' scrittura o spazzatura: Django scrive con
                # rename atomico, quindi qui ci finisce solo roba anomala.
                percorso.unlink(missing_ok=True)
                continue
            esegui(lavoro, percorso)

        time.sleep(INTERVALLO)

    return 0


if __name__ == "__main__":
    sys.exit(main())
