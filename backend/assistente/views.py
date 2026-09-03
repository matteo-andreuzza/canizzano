"""
La rotta del server MCP: ``POST /mcp/``.

Qui dentro c'e' solo il mestiere dell'HTTP — chi bussa, con che chiave, e
come si impacchetta la risposta. Il protocollo sta in ``protocollo.py``, gli
strumenti in ``strumenti.py``.

Chi apre lo stesso indirizzo con il browser non trova un errore ma una
paginetta che dice dove prendere la chiave: e' l'unica cosa che una persona
puo' voler fare, aprendo a mano l'indirizzo di un server per agenti.
"""

from __future__ import annotations

import json
import logging

from django.core.exceptions import RequestDataTooBig
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from .collegamento import indirizzo_mcp
from .models import ChiaveAssistente
from .protocollo import Contesto
from .strumenti import SERVER, VERSIONE

logger = logging.getLogger("assistente")


def _chiave_presentata(richiesta) -> str:
    """La chiave, comunque il client abbia deciso di consegnarla."""
    autorizzazione = richiesta.headers.get("Authorization", "")
    if autorizzazione[:7].lower() == "bearer ":
        return autorizzazione[7:].strip()
    intestazione = richiesta.headers.get("X-Chiave-Assistente", "").strip()
    if intestazione:
        return intestazione
    # Ultima spiaggia: i client che sanno configurare solo un indirizzo.
    return richiesta.GET.get("chiave", "").strip()


def _errore(codice: int, messaggio: str, stato: int, intestazioni: dict | None = None):
    return JsonResponse(
        {"jsonrpc": "2.0", "id": None, "error": {"code": codice, "message": messaggio}},
        status=stato,
        headers=intestazioni or {},
    )


@csrf_exempt
@never_cache
def endpoint(richiesta):
    if richiesta.method == "GET":
        # Un client MCP che chiede lo stream SSE va rimandato indietro con
        # garbo: questo server non tiene sessioni aperte, ogni richiesta e'
        # completa in se'.
        if "text/event-stream" in richiesta.headers.get("Accept", ""):
            return _metodo_non_ammesso()
        return _pagina_per_gli_umani()

    if richiesta.method != "POST":
        return _metodo_non_ammesso()

    chiave = ChiaveAssistente.riconosci(_chiave_presentata(richiesta))
    if chiave is None:
        return _errore(
            -32001,
            "Chiave mancante o non valida. La trovi nell'admin del CMS, in «Assistente AI "
            "→ chiavi dell'assistente», e va mandata come intestazione "
            "«Authorization: Bearer <chiave>».",
            401,
            {"WWW-Authenticate": 'Bearer realm="canizzano"'},
        )

    try:
        grezzo = richiesta.body
    except RequestDataTooBig:
        return _errore(
            -32001,
            "Richiesta troppo grande. Se stai caricando un'immagine, ridimensionala: "
            "sopra i venti megabyte il CMS non la accetta.",
            413,
        )

    try:
        messaggio = json.loads(grezzo or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _errore(-32700, "Il corpo della richiesta non è JSON valido.", 400)

    chiave.registra_uso()
    contesto = Contesto(
        sola_lettura=chiave.sola_lettura, chiave=str(chiave), richiesta=richiesta
    )

    if isinstance(messaggio, list):
        risposte = [
            risposta
            for risposta in (SERVER.gestisci(singolo, contesto) for singolo in messaggio)
            if risposta is not None
        ]
        if not risposte:
            return HttpResponse(status=202)
        return JsonResponse(risposte, safe=False)

    risposta = SERVER.gestisci(messaggio, contesto)
    if risposta is None:
        # Era una notifica: il client non aspetta niente.
        return HttpResponse(status=202)
    return JsonResponse(risposta)


def _metodo_non_ammesso():
    risposta = _errore(-32600, "Questo server MCP parla solo con POST.", 405)
    risposta["Allow"] = "POST"
    return risposta


def _pagina_per_gli_umani():
    quante = ChiaveAssistente.objects.filter(attiva=True).count()
    stato = (
        f"Ci sono {quante} chiavi attive."
        if quante != 1
        else "C'è una chiave attiva."
    ) if quante else (
        "Non c'è ancora nessuna chiave attiva: creane una dall'admin."
    )
    return HttpResponse(
        f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Assistente di canizzano.it</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 46rem; margin: 3rem auto;
         padding: 0 1.25rem; line-height: 1.6; color: #2e2b25; background: #faf7f2; }}
  h1 {{ font-size: 1.6rem; margin-bottom: .25rem; }}
  code, pre {{ background: #f3f0ea; border-radius: 8px; }}
  code {{ padding: 2px 6px; }}
  pre {{ padding: 12px 14px; overflow-x: auto; }}
  a {{ color: #8c491a; }}
  .nota {{ color: #6b6459; font-size: .95rem; }}
</style></head><body>
<h1>Assistente di canizzano.it</h1>
<p class="nota">Server MCP {VERSIONE} · {stato}</p>
<p>Questo indirizzo non si apre col browser: ci parlano gli assistenti AI, in
JSON-RPC su <code>POST</code>. Serve a modificare i contenuti del sito
—&nbsp;eventi, programma della sagra, articoli, foto&nbsp;— parlando con un
agente invece che compilando moduli.</p>
<h2>Come collegare il tuo agente</h2>
<ol>
  <li>Apri <a href="/admin/assistente/chiaveassistente/">admin → Assistente AI →
      chiavi dell'assistente</a>.</li>
  <li>Apri la chiave che c'è (o creane una nuova con «Aggiungi»).</li>
  <li>Copia il comando già pronto per il tuo client.</li>
</ol>
<p>In sostanza si tratta di puntare il client a <code>{indirizzo_mcp()}</code>
mandando l'intestazione <code>Authorization: Bearer &lt;chiave&gt;</code>.</p>
<p class="nota">La chiave vale come una password: chi ce l'ha può cambiare il
sito. Si revoca togliendo la spunta «attiva».</p>
</body></html>""",
        content_type="text/html; charset=utf-8",
    )
