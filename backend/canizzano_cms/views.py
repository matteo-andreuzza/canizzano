"""Viste che non appartengono a nessuna app di contenuto (eventi, assistente):
la dashboard della redazione e le due rotte che la alimentano.

    /riservata/            la pagina
    /riservata/azione/     POST: mette in coda un comando di canizzano.sh
    /riservata/storico/    GET:  legge il registro delle attivita'

Tutte e tre dietro @staff_member_required, cioe' dietro il login dell'admin.

── Perche' qui non c'e' nessun subprocess.run ────────────────────────────────

Django gira dentro al container «backend», che viene costruito dalla sola
cartella ./backend: non contiene canizzano.sh, non ha la CLI di Docker e non
vede il socket del demone. Anche montandoceli, «avvia» e «tutto» eseguono
«compose up -d --build db backend»: ricreerebbero il container che sta
servendo la richiesta, uccidendo il processo a meta' comando e lasciando il
browser senza risposta.

Per questo l'esecuzione sta in un container separato («esecutore»), che
nessun comando della dashboard tocca. Qui si deposita solo il lavoro; l'esito
si legge dopo, dal registro condiviso, tramite polling.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

# ── Lista bianca dei comandi ────────────────────────────────────────────────
#
# Fissa nel codice, non in settings ne' nell'ambiente: nessuna variabile puo'
# allargarla. La chiave arriva dal browser, il valore no — l'argomento passato
# allo script non si costruisce mai da testo libero.
#
# «dev» punta a «dev-sfondo» e non a «dev»: il secondo resta in primo piano
# fino a Ctrl+C, cosa che da un bottone non ha senso.

AZIONI: dict[str, dict[str, str]] = {
    "avvia": {
        "comando": "avvia",
        "processo": "canizzano.sh avvia",
        "etichetta": "Avvia",
    },
    "dev": {
        "comando": "dev-sfondo",
        "processo": "canizzano.sh dev-sfondo",
        "etichetta": "Anteprima",
    },
    "ferma-dev": {
        "comando": "ferma-dev",
        "processo": "canizzano.sh ferma-dev",
        "etichetta": "Ferma anteprima",
    },
    "tutto": {
        "comando": "tutto",
        "processo": "canizzano.sh tutto",
        "etichetta": "Pubblica tutto",
    },
    # L'unica azione che non lancia canizzano.sh: il bot del foglietto vive in
    # un repository suo, un container a parte, e l'esecutore non lo esegue —
    # gli fa una richiesta HTTP sulla rete Docker condivisa (vedi
    # avvia_foglietto() in esecutore.py). Da qui la differenza non si vede: si
    # accoda un lavoro e si aspetta una riga nel registro, come per tutti gli
    # altri.
    #
    # Non ha la conferma rossa di «Pubblica tutto», e non e' una dimenticanza:
    # non tocca mai il sito pubblico. Scrive nel CMS, e quello che scrive resta
    # in redazione finche' una persona non lo pubblica — l'assistente non
    # pubblica mai.
    "foglietto": {
        "comando": "",
        "processo": "avvio_manuale_foglietto",
        "etichetta": "Elabora il foglietto",
    },
}

# Oltre questo silenzio il battito dell'esecutore e' considerato morto. Il
# ciclo lo aggiorna ogni mezzo secondo: trenta secondi sono larghi anche con
# la macchina sotto sforzo per un build.
SILENZIO_MASSIMO = 30

# Quante righe in fondo al registro si guardano per costruire la cronologia.
# Il file cresce di poche righe al giorno; leggerne mille copre mesi e tiene
# il riordino per timestamp su una finestra sensata.
FINESTRA_REGISTRO = 1000


# ── Lettura del registro ────────────────────────────────────────────────────


def _ultime_righe(percorso: Path, quante: int) -> list[str]:
    """Ultime «quante» righe del file, senza caricarlo tutto in memoria.

    Il registro e' pensato per crescere all'infinito (ci scriveranno anche lo
    scraper del foglietto e l'OCR del libretto): si legge dalla coda.
    """
    try:
        with percorso.open("rb") as f:
            f.seek(0, os.SEEK_END)
            fine = f.tell()
            # ~512 byte a riga con abbondanza: una passata basta quasi sempre,
            # e in ogni caso si raddoppia finche' le righe non bastano.
            blocco = min(fine, max(65536, quante * 512))
            f.seek(fine - blocco)
            dati = f.read(blocco)
    except OSError:
        return []

    righe = dati.decode("utf-8", "replace").splitlines()
    # Il primo pezzo puo' essere una riga tagliata a meta' dal seek: si butta,
    # a meno che non si sia partiti proprio dall'inizio del file.
    if blocco < fine and righe:
        righe = righe[1:]
    return righe[-quante:]


MESI = (
    "gen", "feb", "mar", "apr", "mag", "giu",
    "lug", "ago", "set", "ott", "nov", "dic",
)


def _quando(timestamp: str) -> str:
    """«5 set 2026, 14:32» — o il timestamp grezzo se non si riesce a leggerlo.

    L'ora viene riportata al fuso del sito prima di scriverla. Non e' un
    dettaglio: i processi che scrivono nel registro girano in container
    diversi, e chi non ha il TZ impostato registra in UTC. Senza conversione
    la stessa cronologia mostrerebbe due orari diversi per due eventi
    contemporanei.
    """
    try:
        momento = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return timestamp or "data sconosciuta"

    if momento.tzinfo is not None:
        momento = momento.astimezone(ZoneInfo(settings.TIME_ZONE))
    return f"{momento.day} {MESI[momento.month - 1]} {momento.year}, {momento:%H:%M}"


def _voce(riga: str) -> dict | None:
    """Trasforma una riga JSON Lines in una voce, o None se non e' valida.

    Volutamente tollerante: una riga malformata — scritta a meta' da un
    processo interrotto, o da un futuro processo che sbaglia formato — non
    deve far esplodere la pagina, deve solo sparire dall'elenco.
    """
    riga = riga.strip()
    if not riga:
        return None
    try:
        dati = json.loads(riga)
    except ValueError:
        return None
    if not isinstance(dati, dict):
        return None

    stato = str(dati.get("stato") or "").strip().lower()
    timestamp = str(dati.get("timestamp") or "")
    return {
        "timestamp": timestamp,
        # Formattata qui e non nel browser: la cronologia si disegna sia dal
        # template (primo caricamento) sia dal JSON («mostra altre»), e due
        # formattatori diversi darebbero due date diverse nella stessa lista.
        "quando": _quando(timestamp),
        "processo": str(dati.get("processo") or "processo sconosciuto"),
        # Qualunque cosa diversa da «ok» viene mostrata come errore: meglio un
        # falso allarme che un fallimento passato per riuscito.
        "stato": "ok" if stato == "ok" else "errore",
        "dettaglio": str(dati.get("dettaglio") or ""),
        "id": str(dati.get("id") or ""),
    }


def _ordine(voce: dict) -> tuple[int, float]:
    """Chiave di ordinamento: piu' recente prima, timestamp illeggibili in coda."""
    try:
        return (1, datetime.fromisoformat(voce["timestamp"]).timestamp())
    except (TypeError, ValueError):
        return (0, 0.0)


def _cronologia(limite: int, salto: int = 0) -> tuple[list[dict], bool]:
    """Voci del registro ordinate dalla piu' recente. Ritorna (voci, ce_ne_sono_altre).

    Agnostica rispetto a «processo»: qui non si sa nulla di canizzano.sh, dello
    scraper o dell'OCR. Si leggono righe, si scartano quelle rotte, si ordina.
    """
    righe = _ultime_righe(Path(settings.FILE_ATTIVITA), FINESTRA_REGISTRO)
    voci = [v for v in (_voce(r) for r in righe) if v is not None]
    voci.sort(key=_ordine, reverse=True)
    fetta = voci[salto : salto + limite]
    return fetta, len(voci) > salto + limite


# ── Stato dell'esecutore ────────────────────────────────────────────────────


def _stato_esecutore() -> dict:
    """Se c'e' qualcuno in ascolto, e se quel qualcuno riesce a fare qualcosa.

    Sono due cose diverse, e distinguerle conta: un esecutore acceso ma senza
    accesso al demone Docker batte regolarmente e sembra sano, mentre ogni
    bottone fallirebbe con «uscito con codice 1» e nessuna spiegazione.
    """
    battito = Path(settings.CARTELLA_CODA) / ".vivo"
    try:
        vivo = (time.time() - battito.stat().st_mtime) < SILENZIO_MASSIMO
    except OSError:
        return {"vivo": False, "docker": False, "perche": ""}

    if not vivo:
        return {"vivo": False, "docker": False, "perche": ""}

    # Il contenuto e' un di piu': un esecutore vecchio scriveva un file vuoto,
    # e in quel caso l'unica cosa che sappiamo e' che e' vivo.
    try:
        dati = json.loads(battito.read_text(encoding="utf-8"))
        docker = bool(dati.get("docker", True))
        perche = str(dati.get("perche") or "")
    except (OSError, ValueError, AttributeError):
        docker, perche = True, ""

    return {"vivo": True, "docker": docker, "perche": perche}


def _pronto(stato: dict) -> bool:
    return stato["vivo"] and stato["docker"]


def _stato_lavoro(identificativo: str) -> dict:
    """Dov'e' arrivato un lavoro: in coda, in esecuzione, o concluso.

    Lo stato non e' scritto da nessuna parte: si deduce da dove sta il file e
    dalla presenza della riga di esito nel registro. Un pezzo di stato in meno
    da tenere allineato.
    """
    coda = Path(settings.CARTELLA_CODA)
    nome = f"{identificativo}.json"

    for voce in _cronologia(FINESTRA_REGISTRO)[0]:
        if voce["id"] == identificativo:
            return {"stato": voce["stato"], "voce": voce}

    if (coda / "in-corso" / nome).exists():
        return {"stato": "in_esecuzione", "voce": None}
    if (coda / nome).exists():
        return {"stato": "in_attesa", "voce": None}

    # Ne' in coda ne' nel registro: l'esecutore l'ha preso e non ha ancora
    # finito di scrivere, oppure e' sparito. Chi interroga riprova.
    return {"stato": "in_esecuzione", "voce": None}


# ── Viste ───────────────────────────────────────────────────────────────────


@staff_member_required
def pagina_riservata(request):
    """La dashboard della redazione."""
    voci, altre = _cronologia(settings.CRONOLOGIA_INIZIALE)
    stato = _stato_esecutore()
    return render(
        request,
        "riservata.html",
        {
            "url_chiavi_ai": settings.AI_KEYS_ADMIN_URL,
            "chiavi_ai_da_configurare": "TODO" in settings.AI_KEYS_ADMIN_URL,
            "voci": voci,
            "altre_voci": altre,
            "esecutore": stato,
            "esecutore_pronto": _pronto(stato),
            # Senza l'URL del bot il bottone non compare: meglio niente che
            # un bottone che fallisce sempre.
            "foglietto_attivo": bool(settings.BOT_FOGLIETTO_URL),
            "quante_iniziali": settings.CRONOLOGIA_INIZIALE,
        },
    )


@staff_member_required
@require_POST
def esegui_azione(request):
    """Mette in coda un comando di canizzano.sh e ritorna l'id del lavoro.

    Non esegue nulla: scrive un file nella coda condivisa con il container
    «esecutore» (vedi il commento in cima al modulo). Il frontend poi
    interroga /riservata/stato/ finche' non compare l'esito.
    """
    azione = request.POST.get("azione", "")
    if azione not in AZIONI:
        return JsonResponse(
            {"ok": False, "errore": "Comando non consentito."},
            status=400,
        )

    if azione == "foglietto" and not settings.BOT_FOGLIETTO_URL:
        return JsonResponse(
            {
                "ok": False,
                "errore": (
                    "Non è configurato l'indirizzo del bot del foglietto. Scrivi "
                    "«BOT_FOGLIETTO_URL» (e «BOT_FOGLIETTO_TOKEN») nel .env e "
                    "rilancia «./canizzano.sh avvia»."
                ),
            },
            status=400,
        )

    stato = _stato_esecutore()
    if not stato["vivo"]:
        return JsonResponse(
            {
                "ok": False,
                "errore": (
                    "L'esecutore non è in ascolto, quindi il comando non partirebbe. "
                    "Riaccendi lo stack con «./canizzano.sh avvia» dal terminale."
                ),
            },
            status=503,
        )
    # Il foglietto e' l'unico comando che non ha bisogno del demone Docker
    # dell'host: l'esecutore fa una richiesta HTTP al container del bot sulla
    # rete condivisa, non passa da canizzano.sh. Rifiutarlo perche' il demone
    # non risponde vorrebbe dire bloccare l'unica cosa che, in quella
    # situazione, funzionerebbe ancora.
    if not stato["docker"] and azione != "foglietto":
        # Meglio rifiutare subito che accodare un lavoro destinato a fallire
        # con un messaggio incomprensibile.
        return JsonResponse(
            {
                "ok": False,
                "errore": (
                    "L'esecutore è acceso ma non riesce a comandare Docker, quindi "
                    "nessun comando andrebbe a buon fine. Succede quando lo stack "
                    "viene avviato con «docker compose up» invece che con "
                    "«./canizzano.sh avvia»: rilancia quest'ultimo dal terminale."
                    + (f"\n\nDettaglio: {stato['perche']}" if stato["perche"] else "")
                ),
            },
            status=503,
        )

    # L'id comincia col timestamp: l'esecutore prende i lavori in ordine di
    # nome, che cosi' e' anche l'ordine di arrivo.
    identificativo = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
    lavoro = {
        "id": identificativo,
        "azione": azione,
        "richiesto_da": request.user.get_username(),
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    coda = Path(settings.CARTELLA_CODA)
    try:
        coda.mkdir(parents=True, exist_ok=True)
        # Scrittura atomica: l'esecutore guarda solo i «*.json», quindi non
        # puo' pescare un file mentre lo stiamo ancora scrivendo.
        provvisorio = coda / f".{identificativo}.parziale"
        provvisorio.write_text(json.dumps(lavoro, ensure_ascii=False), encoding="utf-8")
        provvisorio.rename(coda / f"{identificativo}.json")
    except OSError as errore:
        return JsonResponse(
            {"ok": False, "errore": f"Non riesco a scrivere nella coda: {errore}"},
            status=500,
        )

    return JsonResponse(
        {"ok": True, "id": identificativo, "processo": AZIONI[azione]["processo"]}
    )


@staff_member_required
@require_GET
def stato_azione(request):
    """Stato di un lavoro messo in coda, interrogato dal frontend in polling."""
    identificativo = request.GET.get("id", "")
    if not identificativo or not identificativo.replace("-", "").isalnum():
        return JsonResponse({"ok": False, "errore": "Identificativo non valido."}, status=400)
    return JsonResponse({"ok": True, **_stato_lavoro(identificativo)})


@staff_member_required
@require_GET
def storico(request):
    """Pagina di cronologia: usata da «mostra altre N»."""
    try:
        salto = max(0, int(request.GET.get("salto", 0)))
        limite = min(50, max(1, int(request.GET.get("limite", 10))))
    except ValueError:
        return JsonResponse({"ok": False, "errore": "Parametri non validi."}, status=400)

    voci, altre = _cronologia(limite, salto)
    stato = _stato_esecutore()
    return JsonResponse(
        {
            "ok": True,
            "voci": voci,
            "altre": altre,
            "esecutore_pronto": _pronto(stato),
            "esecutore": stato,
        }
    )
