"""
Il trasporto MCP: JSON-RPC 2.0 su HTTP, senza dipendenze in piu'.

Un client MCP («streamable HTTP») parla con una sola rotta:

    POST /mcp/      un messaggio JSON-RPC, una risposta JSON

Qui c'e' soltanto il protocollo — il registro degli strumenti, delle risorse
e dei prompt, e lo smistamento dei metodi. Questo file non sa nulla di
eventi, sagre e articoli: il mestiere sta in ``strumenti.py``.

Perche' scritto a mano invece di prendere una libreria: il CMS gira in un
container minimo e i metodi che servono davvero sono otto. Nessun pacchetto
da aggiornare, nessuna sorpresa al prossimo build.

Il server e' volutamente **senza sessione**: non emette ``Mcp-Session-Id``,
quindi ogni richiesta e' completa in se'. Con tre worker gunicorn davanti e
nessuno stato condiviso, e' l'unica scelta che non si rompe a caso.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger("assistente")

# Le versioni del protocollo che sappiamo parlare. Al client rispondiamo con
# la sua, se la conosciamo: e' la regola che tiene insieme client vecchi e
# nuovi senza costringere nessuno ad aggiornarsi.
VERSIONI_SUPPORTATE = ("2025-06-18", "2025-03-26", "2024-11-05")
VERSIONE_PREDEFINITA = "2025-06-18"

# Codici d'errore JSON-RPC 2.0.
ERRORE_PARSING = -32700
ERRORE_RICHIESTA = -32600
ERRORE_METODO = -32601
ERRORE_PARAMETRI = -32602
ERRORE_INTERNO = -32603


class ErroreProtocollo(Exception):
    """Guasto di protocollo: diventa un errore JSON-RPC."""

    def __init__(self, codice: int, messaggio: str):
        super().__init__(messaggio)
        self.codice = codice


class ErroreStrumento(Exception):
    """
    Errore «di mestiere»: dato sbagliato, evento inesistente, campo ignoto.

    Non e' un guasto del server: torna al modello come *risultato* marcato
    ``isError``, cosi' l'agente lo legge, capisce cosa ha sbagliato e
    riprova. Un errore JSON-RPC, invece, molti client lo nascondono.
    """


@dataclass(frozen=True)
class Strumento:
    nome: str
    titolo: str
    descrizione: str
    schema: dict
    funzione: Callable[[dict, "Contesto"], str]
    #: Se vero la chiave di sola lettura non puo' invocarlo.
    scrive: bool = False


@dataclass(frozen=True)
class Risorsa:
    uri: str
    nome: str
    titolo: str
    descrizione: str
    mime: str
    funzione: Callable[["Contesto"], str]


@dataclass(frozen=True)
class Prompt:
    nome: str
    descrizione: str
    argomenti: tuple[dict, ...]
    funzione: Callable[[dict], str]


@dataclass
class Contesto:
    """Chi sta parlando e con che diritti."""

    #: La chiave puo' solo leggere: gli strumenti che scrivono sono chiusi.
    sola_lettura: bool = False
    #: Come si chiama la chiave usata, per i log e i messaggi.
    chiave: str = ""
    #: La richiesta HTTP, per costruire i link assoluti all'admin.
    richiesta: Any = None

    def indirizzo(self, percorso: str) -> str:
        """Trasforma «/admin/…» nell'indirizzo completo da dare a chi legge."""
        if self.richiesta is not None:
            return self.richiesta.build_absolute_uri(percorso)
        return percorso


class ServerMCP:
    """Il registro degli strumenti e lo smistamento dei metodi MCP."""

    def __init__(self, nome: str, versione: str, istruzioni: Callable[[], str]):
        self.nome = nome
        self.versione = versione
        # Le istruzioni si calcolano quando servono: dentro c'e' lo stato del
        # sito, che cambia mentre il server e' acceso.
        self.istruzioni = istruzioni
        self._strumenti: dict[str, Strumento] = {}
        self._risorse: dict[str, Risorsa] = {}
        self._prompt: dict[str, Prompt] = {}

    # ── registrazione ────────────────────────────────────────────────────

    def strumento(self, nome: str, *, titolo: str, descrizione: str, schema: dict,
                  scrive: bool = False):
        def registra(funzione):
            self.aggiungi_strumento(
                Strumento(nome, titolo, descrizione, schema, funzione, scrive)
            )
            return funzione

        return registra

    def aggiungi_strumento(self, strumento: Strumento) -> None:
        if strumento.nome in self._strumenti:
            raise ValueError(f"Strumento duplicato: {strumento.nome}")
        self._strumenti[strumento.nome] = strumento

    def risorsa(self, uri: str, *, nome: str, titolo: str, descrizione: str,
                mime: str = "text/markdown"):
        def registra(funzione):
            self._risorse[uri] = Risorsa(uri, nome, titolo, descrizione, mime, funzione)
            return funzione

        return registra

    def prompt(self, nome: str, *, descrizione: str, argomenti: tuple[dict, ...] = ()):
        def registra(funzione):
            self._prompt[nome] = Prompt(nome, descrizione, argomenti, funzione)
            return funzione

        return registra

    @property
    def strumenti(self) -> dict[str, Strumento]:
        return self._strumenti

    # ── smistamento ──────────────────────────────────────────────────────

    def gestisci(self, messaggio: Any, contesto: Contesto) -> dict | None:
        """
        Un messaggio JSON-RPC in, una risposta (o ``None``) fuori.

        ``None`` vuol dire «notifica»: il client non aspetta risposta e la
        rotta HTTP restituisce 202 senza corpo.
        """
        if not isinstance(messaggio, dict) or messaggio.get("jsonrpc") != "2.0":
            return self._errore(None, ERRORE_RICHIESTA, "Serve un messaggio JSON-RPC 2.0.")

        metodo = messaggio.get("method")
        identificativo = messaggio.get("id")
        # Una notifica e' un messaggio *senza* la chiave «id» (diverso da
        # «id: null», che invece e' una richiesta con identificativo nullo).
        e_notifica = "id" not in messaggio

        if not isinstance(metodo, str):
            return None if e_notifica else self._errore(
                identificativo, ERRORE_RICHIESTA, "Manca il nome del metodo."
            )

        parametri = messaggio.get("params") or {}
        if not isinstance(parametri, dict):
            return None if e_notifica else self._errore(
                identificativo, ERRORE_PARAMETRI, "«params» deve essere un oggetto."
            )

        try:
            risultato = self._esegui(metodo, parametri, contesto)
        except ErroreProtocollo as guasto:
            return None if e_notifica else self._errore(identificativo, guasto.codice, str(guasto))
        except Exception:  # noqa: BLE001 — l'endpoint non deve mai morire
            logger.exception("MCP: il metodo %s è esploso", metodo)
            return None if e_notifica else self._errore(
                identificativo, ERRORE_INTERNO, "Errore interno del CMS: guarda i log del backend."
            )

        if e_notifica:
            return None
        return {"jsonrpc": "2.0", "id": identificativo, "result": risultato}

    def _esegui(self, metodo: str, parametri: dict, contesto: Contesto) -> dict:
        if metodo == "initialize":
            return self._inizializza(parametri)
        if metodo == "ping":
            return {}
        if metodo.startswith("notifications/"):
            return {}
        if metodo == "tools/list":
            return {"tools": [self._descrivi_strumento(s) for s in self._strumenti.values()]}
        if metodo == "tools/call":
            return self._chiama_strumento(parametri, contesto)
        if metodo == "resources/list":
            return {"resources": [
                {
                    "uri": r.uri,
                    "name": r.nome,
                    "title": r.titolo,
                    "description": r.descrizione,
                    "mimeType": r.mime,
                }
                for r in self._risorse.values()
            ]}
        if metodo == "resources/templates/list":
            return {"resourceTemplates": []}
        if metodo == "resources/read":
            return self._leggi_risorsa(parametri, contesto)
        if metodo == "prompts/list":
            return {"prompts": [
                {"name": p.nome, "description": p.descrizione, "arguments": list(p.argomenti)}
                for p in self._prompt.values()
            ]}
        if metodo == "prompts/get":
            return self._leggi_prompt(parametri)
        if metodo == "logging/setLevel":
            return {}
        raise ErroreProtocollo(ERRORE_METODO, f"Metodo non gestito: {metodo}")

    def _inizializza(self, parametri: dict) -> dict:
        richiesta = parametri.get("protocolVersion")
        versione = richiesta if richiesta in VERSIONI_SUPPORTATE else VERSIONE_PREDEFINITA
        return {
            "protocolVersion": versione,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {"name": self.nome, "version": self.versione},
            "instructions": self.istruzioni(),
        }

    @staticmethod
    def _descrivi_strumento(strumento: Strumento) -> dict:
        return {
            "name": strumento.nome,
            "title": strumento.titolo,
            "description": strumento.descrizione,
            "inputSchema": strumento.schema,
        }

    def _chiama_strumento(self, parametri: dict, contesto: Contesto) -> dict:
        nome = parametri.get("name")
        argomenti = parametri.get("arguments") or {}
        if not isinstance(argomenti, dict):
            raise ErroreProtocollo(ERRORE_PARAMETRI, "«arguments» deve essere un oggetto.")

        strumento = self._strumenti.get(nome)
        if strumento is None:
            raise ErroreProtocollo(
                ERRORE_PARAMETRI,
                f"Strumento sconosciuto: {nome}. Chiedi «tools/list» per l'elenco.",
            )

        if strumento.scrive and contesto.sola_lettura:
            return self._risposta(
                f"⚠ La chiave «{contesto.chiave}» è di sola lettura: «{nome}» non può essere "
                "usato. Togli la spunta «sola lettura» in admin → Assistente AI → chiavi.",
                errore=True,
            )

        try:
            self._verifica_argomenti(strumento, argomenti)
            testo = strumento.funzione(argomenti, contesto)
        except ErroreStrumento as problema:
            return self._risposta(f"⚠ {problema}", errore=True)
        except Exception as guasto:  # noqa: BLE001 — l'agente deve poter correggere
            logger.exception("MCP: lo strumento %s è esploso", nome)
            return self._risposta(
                f"⚠ Lo strumento «{nome}» si è fermato: {type(guasto).__name__}: {guasto}",
                errore=True,
            )
        return self._risposta(testo)

    @staticmethod
    def _verifica_argomenti(strumento: Strumento, argomenti: dict) -> None:
        """
        Controlli minimi prima di entrare nello strumento.

        I client seri validano gia' contro lo schema, ma non tutti: meglio un
        messaggio in italiano che un ``KeyError`` fra i log.
        """
        proprieta = strumento.schema.get("properties", {})
        mancanti = [c for c in strumento.schema.get("required", []) if argomenti.get(c) in (None, "")]
        if mancanti:
            raise ErroreStrumento(
                f"Mancano dei campi obbligatori per «{strumento.nome}»: {', '.join(mancanti)}."
            )
        ignoti = [c for c in argomenti if c not in proprieta]
        if ignoti:
            raise ErroreStrumento(
                f"Campi che «{strumento.nome}» non conosce: {', '.join(sorted(ignoti))}. "
                f"Quelli buoni sono: {', '.join(sorted(proprieta))}."
            )

    def _leggi_risorsa(self, parametri: dict, contesto: Contesto) -> dict:
        uri = parametri.get("uri")
        risorsa = self._risorse.get(uri)
        if risorsa is None:
            raise ErroreProtocollo(ERRORE_PARAMETRI, f"Risorsa sconosciuta: {uri}")
        return {
            "contents": [
                {"uri": risorsa.uri, "mimeType": risorsa.mime, "text": risorsa.funzione(contesto)}
            ]
        }

    def _leggi_prompt(self, parametri: dict) -> dict:
        nome = parametri.get("name")
        prompt = self._prompt.get(nome)
        if prompt is None:
            raise ErroreProtocollo(ERRORE_PARAMETRI, f"Prompt sconosciuto: {nome}")
        argomenti = parametri.get("arguments") or {}
        return {
            "description": prompt.descrizione,
            "messages": [
                {"role": "user", "content": {"type": "text", "text": prompt.funzione(argomenti)}}
            ],
        }

    @staticmethod
    def _risposta(testo: str, errore: bool = False) -> dict:
        risposta: dict = {"content": [{"type": "text", "text": testo}]}
        if errore:
            risposta["isError"] = True
        return risposta

    @staticmethod
    def _errore(identificativo: Any, codice: int, messaggio: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": identificativo,
            "error": {"code": codice, "message": messaggio},
        }
