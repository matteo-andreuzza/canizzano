"""
Quello che l'assistente sa fare: gli strumenti MCP di canizzano.it.

Gli strumenti che creano e modificano contenuti (`crea_evento`,
`aggiorna_giornata`, `crea_articolo`…) non sono scritti a mano uno per uno:
nascono dal registro dei tipi in ``schemi.py``, che a sua volta legge i
modelli Django. Un campo nuovo in ``eventi/models.py`` compare da solo fra
gli strumenti al riavvio del CMS, con il suo tipo, i suoi valori ammessi e
il suo testo d'aiuto.

Scritti a mano restano solo quelli che fanno un mestiere, non una tabella:
guardare lo stato del sito, cercare, leggere il programma della sagra,
caricare un'immagine, cancellare con giudizio.
"""

from __future__ import annotations

import base64
import binascii
import io
import os
import urllib.error
import urllib.request

from django.contrib.admin.utils import NestedObjects
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.text import get_valid_filename

from eventi.models import (
    Articolo,
    DettaglioArticolo,
    Edizione,
    Evento,
    Giornata,
    ImpostazioniSito,
)

from . import guida as manuale
from .protocollo import Contesto, ErroreStrumento, ServerMCP, Strumento
from .schemi import (
    CARTELLE_MEDIA,
    TIPI,
    TIPI_SCRIVIBILI,
    Tipo,
    a_data,
    applica,
    converti,
    risolvi,
    schema_campo,
    schema_tipo,
    valori_ammessi,
)

VERSIONE = "1.0.0"

PROMEMORIA = (
    "Il sito è statico: questa modifica sarà online al prossimo «./canizzano.sh tutto»."
)

#: Quanto può pesare un'immagine caricata dall'assistente.
LIMITE_IMMAGINE = int(os.environ.get("MCP_MAX_IMMAGINE_MB", "20")) * 1024 * 1024

SERVER = ServerMCP("canizzano-cms", VERSIONE, manuale.istruzioni)


# ── piccoli aiuti condivisi ──────────────────────────────────────────────


def _link_admin(oggetto, contesto: Contesto) -> str:
    """L'indirizzo della pagina d'admin: serve a chi legge, non all'agente."""
    try:
        percorso = reverse(
            f"admin:{oggetto._meta.app_label}_{oggetto._meta.model_name}_change",
            args=[oggetto.pk],
        )
    except NoReverseMatch:  # pragma: no cover
        return ""
    return contesto.indirizzo(percorso)


def _salva(oggetto, azione: str = "salvare") -> None:
    """Valida come farebbe l'admin, poi salva. Gli errori tornano in italiano."""
    try:
        oggetto.full_clean()
    except ValidationError as rifiuto:
        if hasattr(rifiuto, "message_dict"):
            # «__all__» e' come Django chiama gli errori che non stanno su un
            # campo solo: all'agente non dice niente, meglio toglierlo.
            dettagli = " · ".join(
                (f"{campo}: " if campo != "__all__" else "")
                + " ".join(str(m) for m in messaggi)
                for campo, messaggi in rifiuto.message_dict.items()
            )
        else:
            dettagli = " · ".join(str(m) for m in rifiuto.messages)
        raise ErroreStrumento(f"Il CMS rifiuta di {azione}: {dettagli}") from rifiuto
    oggetto.save()


def _quando(evento: Evento) -> str:
    istante = timezone.localtime(evento.inizio)
    if evento.etichetta_data:
        return f"{evento.etichetta_data} (data tecnica {date_format(istante, 'd/m/Y')})"
    if evento.tutto_il_giorno:
        return date_format(istante, "l j F Y")
    return date_format(istante, "l j F Y, H:i")


def _riga_evento(evento: Evento) -> str:
    segni = []
    if not evento.pubblicato:
        segni.append("NON pubblicato")
    if evento.in_evidenza:
        segni.append("in evidenza")
    if evento.risalto:
        segni.append("risalto")
    if evento.piatto_del_giorno:
        segni.append(f"piatto: {evento.piatto_del_giorno}")
    articolo = getattr(evento, "articolo", None)
    if articolo:
        segni.append(f"articolo /eventi/{articolo.slug}")
    coda = f" · {', '.join(segni)}" if segni else ""
    return (
        f"- {date_format(timezone.localtime(evento.inizio), 'd/m/Y H:i')} — "
        f"**{evento.titolo}** (`{evento.slug}`, attività `{evento.attivita.slug}`){coda}"
    )


def _riga(oggetto, tipo: Tipo) -> str:
    if isinstance(oggetto, Evento):
        return _riga_evento(oggetto)
    etichetta = str(oggetto)
    slug = getattr(oggetto, "slug", "")
    riferimento = f"`{slug}`" if slug else f"id {oggetto.pk}"
    coda = ""
    if isinstance(oggetto, Articolo):
        coda = f" → /eventi/{oggetto.slug} (evento `{oggetto.evento.slug}`)"
    elif isinstance(oggetto, Giornata):
        coda = f" → {date_format(oggetto.data, 'd/m/Y')}, edizione `{oggetto.edizione.slug}`"
    if hasattr(oggetto, "pubblicato") and not oggetto.pubblicato:
        coda += " · NON pubblicato"
    return f"- **{etichetta}** ({riferimento}){coda}"


def _valore_leggibile(oggetto, campo) -> str:
    valore = getattr(oggetto, campo.name, None)
    if campo.is_relation:
        if valore is None:
            return "—"
        return f"`{getattr(valore, 'slug', '')}`" if getattr(valore, "slug", "") else str(valore)
    if valore is None or valore == "":
        return "—"
    if isinstance(valore, bool):
        return "sì" if valore else "no"
    if campo.get_internal_type() == "DateTimeField":
        return date_format(timezone.localtime(valore), "d/m/Y H:i")
    if campo.get_internal_type() == "DateField":
        return date_format(valore, "d/m/Y")
    if campo.get_internal_type() in {"ImageField", "FileField"}:
        return f"`{valore.name}`" if getattr(valore, "name", "") else "—"
    scelte = dict(valori_ammessi(campo))
    testo = str(valore)
    if scelte.get(testo):
        return f"{testo} ({scelte[testo]})"
    return testo if len(testo) <= 300 else testo[:300] + "…"


def _scheda(oggetto, tipo: Tipo, contesto: Contesto) -> str:
    righe = [f"## {tipo.nome}: {oggetto}", ""]
    for nome in tipo.campi:
        campo = tipo.campo(nome)
        righe.append(f"- **{nome}**: {_valore_leggibile(oggetto, campo)}")
    righe.append(f"- **id**: {oggetto.pk}")

    if isinstance(oggetto, Articolo):
        dettagli = list(oggetto.dettagli.all())
        righe.append("")
        righe.append("### Scheda pratica (dettagli)")
        righe += [f"- {d.etichetta}: {d.valore}" for d in dettagli] or ["- *nessuno: la pagina ripiega su data, luogo e ingresso*"]
        foto = list(oggetto.foto.all())
        righe.append("")
        righe.append(f"### Galleria dell'articolo ({len(foto)} foto)")
        righe += [
            f"- {f.didascalia or '(senza didascalia)'} — {f.sorgente or 'NESSUNA IMMAGINE'}"
            for f in foto
        ] or ["- *nessuna foto collegata a questo articolo*"]
    if isinstance(oggetto, Evento):
        articolo = getattr(oggetto, "articolo", None)
        righe.append("")
        righe.append(
            f"### Pagina di approfondimento\n- {'/eventi/' + articolo.slug if articolo else 'nessuna (e va benissimo, se non c’è molto da dire)'}"
        )

    collegamento = _link_admin(oggetto, contesto)
    if collegamento:
        righe += ["", f"Modificabile a mano su {collegamento}"]
    return "\n".join(righe)


def _tipo_richiesto(nome: str) -> Tipo:
    tipo = TIPI.get((nome or "").strip().lower())
    if tipo is None:
        raise ErroreStrumento(
            f"Tipo di contenuto sconosciuto: «{nome}». Quelli buoni sono: {', '.join(TIPI)}."
        )
    return tipo


def _dettagli_articolo(articolo: Articolo, righe) -> int:
    """Riscrive la scheda pratica di un articolo: le righe vecchie se ne vanno."""
    if not isinstance(righe, list):
        raise ErroreStrumento("«dettagli» dev'essere un elenco di {etichetta, valore}.")
    articolo.dettagli.all().delete()
    for posizione, riga in enumerate(righe):
        if not isinstance(riga, dict) or not riga.get("etichetta"):
            raise ErroreStrumento(
                "Ogni dettaglio è un oggetto con «etichetta» e «valore», "
                "es. {\"etichetta\": \"Ritrovo\", \"valore\": \"ore 7.00 in piazza\"}."
            )
        DettaglioArticolo.objects.create(
            articolo=articolo,
            etichetta=str(riga["etichetta"])[:60],
            valore=str(riga.get("valore", ""))[:200],
            ordine=posizione,
        )
    return len(righe)


# ── strumenti generati dai modelli ───────────────────────────────────────


def _registra_tipo(tipo: Tipo) -> None:
    """Crea gli strumenti «crea_x» e «aggiorna_x» per un tipo di contenuto."""

    def crea(argomenti: dict, contesto: Contesto) -> str:
        oggetto = tipo.modello()
        applica(oggetto, tipo, argomenti)
        _salva(oggetto, f"creare {tipo.nome}")
        coda = ""
        if isinstance(oggetto, Articolo) and "dettagli" in argomenti:
            quanti = _dettagli_articolo(oggetto, argomenti["dettagli"])
            coda = f"\nScheda pratica: {quanti} righe."
        return (
            f"✓ Creato {tipo.nome}: **{oggetto}**\n"
            + _scheda(oggetto, tipo, contesto).split("\n", 2)[2]
            + coda
            + f"\n\n{PROMEMORIA}"
        )

    def aggiorna(argomenti: dict, contesto: Contesto) -> str:
        riferimento = argomenti.get("id_o_slug")
        oggetto = risolvi(tipo.modello, riferimento, "id_o_slug")
        valori = {c: v for c, v in argomenti.items() if c != "id_o_slug"}
        if not valori:
            raise ErroreStrumento(
                f"Non mi hai detto che cosa cambiare di «{oggetto}». "
                f"Campi modificabili: {', '.join(tipo.campi)}."
            )
        toccati = applica(oggetto, tipo, valori)
        _salva(oggetto, f"aggiornare {tipo.nome}")
        coda = ""
        if isinstance(oggetto, Articolo) and "dettagli" in valori:
            quanti = _dettagli_articolo(oggetto, valori["dettagli"])
            coda = f"\nScheda pratica riscritta: {quanti} righe."
            toccati.append("dettagli")
        return (
            f"✓ Aggiornato {tipo.nome} **{oggetto}** "
            f"({', '.join(toccati) if toccati else 'nessun campo'}).\n"
            + _scheda(oggetto, tipo, contesto).split("\n", 2)[2]
            + coda
            + f"\n\n{PROMEMORIA}"
        )

    SERVER.aggiungi_strumento(
        Strumento(
            nome=f"crea_{tipo.nome}",
            titolo=f"Crea {tipo.nome}",
            descrizione=f"Crea un nuovo contenuto di tipo «{tipo.nome}». {tipo.descrizione}",
            schema=schema_tipo(tipo, creazione=True),
            funzione=crea,
            scrive=True,
        )
    )
    SERVER.aggiungi_strumento(
        Strumento(
            nome=f"aggiorna_{tipo.nome}",
            titolo=f"Aggiorna {tipo.nome}",
            descrizione=(
                f"Modifica un {tipo.nome} che esiste già: passa solo i campi da cambiare, "
                f"gli altri restano come sono. Che cos'è un {tipo.nome} lo spiega "
                f"«crea_{tipo.nome}»."
            ),
            schema=schema_tipo(tipo, creazione=False),
            funzione=aggiorna,
            scrive=True,
        )
    )


for _nome_tipo in TIPI_SCRIVIBILI:
    _registra_tipo(TIPI[_nome_tipo])


# ── conoscere ────────────────────────────────────────────────────────────


@SERVER.strumento(
    "guida_del_sito",
    titolo="La guida della redazione",
    descrizione=(
        "Come funziona canizzano.it e come si scrivono i contenuti: le regole della "
        "redazione, la struttura della sagra, quando un evento merita un articolo, quale "
        "icona scegliere, i campi di ogni tipo di contenuto. Leggila prima di creare "
        "qualcosa la prima volta."
    ),
    schema={
        "type": "object",
        "properties": {
            "argomento": {
                "type": "string",
                "enum": list(manuale.ARGOMENTI),
                "description": "Quale parte leggere. "
                + "; ".join(f"{k} = {v}" for k, v in manuale.ARGOMENTI.items()),
            }
        },
        "required": [],
        "additionalProperties": False,
    },
)
def _guida(argomenti: dict, contesto: Contesto) -> str:
    return manuale.guida(argomenti.get("argomento", "tutto"))


@SERVER.strumento(
    "panoramica",
    titolo="Com'è messo il sito",
    descrizione=(
        "Lo stato del CMS in una schermata: le realtà del quartiere con i loro slug, le "
        "edizioni, i luoghi, i prossimi appuntamenti, il banner in home e i conteggi. "
        "È il primo strumento da chiamare in una conversazione."
    ),
    schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
)
def _panoramica(argomenti: dict, contesto: Contesto) -> str:
    return manuale.stato_sito() + f"\n\n{PROMEMORIA}"


@SERVER.strumento(
    "cerca_contenuti",
    titolo="Cerca nel CMS",
    descrizione=(
        "Trova contenuti per parola, tipo, attività o periodo. Serve a non inventare slug: "
        "cerca prima, poi modifica quello che hai trovato."
    ),
    schema={
        "type": "object",
        "properties": {
            "testo": {"type": "string", "description": "Parola da cercare in titoli e testi."},
            "tipo": {
                "type": "string",
                "enum": ["tutto", *TIPI],
                "description": "Limita la ricerca a un tipo di contenuto. Vuoto = tutti.",
            },
            "attivita": {
                "type": "string",
                "description": "Slug di una realtà del quartiere: tiene solo i suoi contenuti.",
            },
            "dal": {"type": "string", "description": "Solo eventi/giornate da questa data: «2026-10-01»."},
            "al": {"type": "string", "description": "Solo eventi/giornate fino a questa data."},
            "limite": {"type": "integer", "description": "Quanti risultati per tipo (default 20)."},
        },
        "required": [],
        "additionalProperties": False,
    },
)
def _cerca(argomenti: dict, contesto: Contesto) -> str:
    testo = (argomenti.get("testo") or "").strip()
    limite = max(1, min(int(argomenti.get("limite") or 20), 100))
    richiesto = (argomenti.get("tipo") or "tutto").strip().lower()
    tipi = list(TIPI.values()) if richiesto in ("", "tutto") else [_tipo_richiesto(richiesto)]

    filtro_attivita = (argomenti.get("attivita") or "").strip()
    dal = argomenti.get("dal")
    al = argomenti.get("al")

    blocchi: list[str] = []
    totale = 0
    for tipo in tipi:
        insieme = tipo.modello.objects.all()

        if testo and tipo.ricerca:
            condizione = Q()
            for campo in tipo.ricerca:
                condizione |= Q(**{f"{campo}__icontains": testo})
            insieme = insieme.filter(condizione)
        elif testo:
            continue

        if filtro_attivita:
            attivita = risolvi(TIPI["attivita"].modello, filtro_attivita, "attivita")
            if tipo.nome == "evento":
                insieme = insieme.filter(attivita=attivita)
            elif tipo.nome == "attivita":
                insieme = insieme.filter(pk=attivita.pk)
            elif tipo.nome == "articolo":
                insieme = insieme.filter(evento__attivita=attivita)
            elif tipo.nome in ("edizione", "album", "foto"):
                insieme = insieme.filter(attivita=attivita)
            elif tipo.nome == "giornata":
                insieme = insieme.filter(edizione__attivita=attivita)

        if dal or al:
            campo_data = {"evento": "inizio__date", "giornata": "data"}.get(tipo.nome)
            if campo_data is None:
                continue
            if dal:
                insieme = insieme.filter(**{f"{campo_data}__gte": a_data(dal, "dal")})
            if al:
                insieme = insieme.filter(**{f"{campo_data}__lte": a_data(al, "al")})

        if tipo.nome == "evento":
            insieme = insieme.select_related("attivita", "articolo")
        elif tipo.nome == "articolo":
            insieme = insieme.select_related("evento")
        elif tipo.nome == "giornata":
            insieme = insieme.select_related("edizione")

        trovati = list(insieme[:limite])
        if trovati:
            totale += len(trovati)
            blocchi.append(
                f"### {tipo.plurale} ({len(trovati)})\n" + "\n".join(_riga(o, tipo) for o in trovati)
            )

    if not blocchi:
        return (
            "Nessun risultato. Prova con una parola più corta, togli i filtri, "
            "oppure guarda `panoramica` per vedere che cosa c'è."
        )
    return f"{totale} risultati.\n\n" + "\n\n".join(blocchi)


@SERVER.strumento(
    "leggi_contenuto",
    titolo="Leggi un contenuto",
    descrizione="Tutti i campi di un contenuto, con i suoi collegamenti e il link all'admin.",
    schema={
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": list(TIPI), "description": "Che cosa leggere."},
            "id_o_slug": {"type": "string", "description": "Lo slug (consigliato) o l'id numerico."},
        },
        "required": ["tipo", "id_o_slug"],
        "additionalProperties": False,
    },
)
def _leggi(argomenti: dict, contesto: Contesto) -> str:
    tipo = _tipo_richiesto(argomenti.get("tipo"))
    oggetto = risolvi(tipo.modello, argomenti.get("id_o_slug"), "id_o_slug")
    return _scheda(oggetto, tipo, contesto)


@SERVER.strumento(
    "programma_sagra",
    titolo="Il programma della sagra",
    descrizione=(
        "Le giornate della sagra con dentro i loro orari, i piatti del giorno e le "
        "prenotazioni: la vista da cui partire per cambiare il programma o il menù di una "
        "serata. Segnala anche gli eventi che cadono in un giorno senza giornata — quelli "
        "il programma non li mostra."
    ),
    schema={
        "type": "object",
        "properties": {
            "edizione": {
                "type": "string",
                "description": "Slug dell'edizione. Vuoto = l'ultima edizione con giornate.",
            }
        },
        "required": [],
        "additionalProperties": False,
    },
)
def _programma(argomenti: dict, contesto: Contesto) -> str:
    riferimento = (argomenti.get("edizione") or "").strip()
    if riferimento:
        edizione = risolvi(Edizione, riferimento, "edizione")
    else:
        edizione = (
            Edizione.objects.annotate(quante=Count("giornate"))
            .filter(quante__gt=0)
            .order_by("-anno")
            .select_related("attivita")
            .first()
        )
        if edizione is None:
            raise ErroreStrumento(
                "Non c'è nessuna edizione con delle giornate: il programma della sagra è "
                "ancora tutto da costruire. Si parte da `crea_edizione`, poi `crea_giornata` "
                "per ogni giorno, poi `crea_evento` per gli orari."
            )

    giornate = list(edizione.giornate.all().order_by("data"))
    # Gli eventi del programma sono quelli legati all'edizione piu' quelli
    # dell'attivita' che cadono nei giorni della festa: gli orari si attaccano
    # alla giornata per data, non da un collegamento, ed e' proprio li' che
    # capita di dimenticarsi l'edizione.
    dentro_le_date = Q(pk__in=[])
    if giornate:
        dentro_le_date = Q(
            attivita=edizione.attivita,
            inizio__date__gte=giornate[0].data,
            inizio__date__lte=giornate[-1].data,
        )
    eventi = list(
        Evento.objects.filter(Q(edizione=edizione) | dentro_le_date)
        .select_related("attivita", "articolo")
        .order_by("inizio", "ordine")
    )

    righe = [
        f"# {edizione.etichetta}",
        "",
        f"Edizione `{edizione.slug}` · attività `{edizione.attivita.slug}` · "
        f"{len(giornate)} giornate.",
        "",
    ]
    date_con_giornata = set()
    for giornata in giornate:
        date_con_giornata.add(giornata.data)
        del_giorno = [e for e in eventi if timezone.localtime(e.inizio).date() == giornata.data]
        stato = "" if giornata.pubblicato else "  ⚠ NON pubblicata"
        righe.append(
            f"## {giornata.etichetta} — {date_format(giornata.data, 'd/m/Y')}{stato}\n"
            f"*giornata id {giornata.pk} · occhiello «{giornata.occhiello or '—'}» · "
            f"tono {giornata.tono}*"
        )
        if del_giorno:
            for evento in del_giorno:
                righe.append(_riga_evento(evento))
        else:
            righe.append("- *nessun orario in programma per questo giorno*")
        righe.append("")

    orfani = [e for e in eventi if timezone.localtime(e.inizio).date() not in date_con_giornata]
    if orfani:
        righe += [
            "## ⚠ Eventi senza giornata",
            "",
            "Cadono in un giorno che non ha una card nel programma: sul sito compaiono nel "
            "calendario di quartiere ma **non** in /sagra. O crei la giornata, o sposti "
            "l'evento.",
            "",
            *[_riga_evento(e) for e in orfani],
            "",
        ]

    menu = [e for e in eventi if e.piatto_del_giorno or e.prenotazione_entro]
    righe += ["## Il menù della cucina", ""]
    if menu:
        for evento in menu:
            prenota = (
                f" · prenotare entro {date_format(evento.prenotazione_entro, 'd/m/Y')}"
                if evento.prenotazione_entro
                else ""
            )
            righe.append(
                f"- {date_format(timezone.localtime(evento.inizio), 'd/m')} — "
                f"**{evento.piatto_del_giorno or evento.titolo}** (evento `{evento.slug}`)"
                f"{prenota}"
            )
    else:
        righe.append("*Nessun piatto del giorno: la tabella del menù non compare sul sito.*")
    righe += [
        "",
        "Per cambiare il menù di una serata: `aggiorna_evento` sull'evento di quel giorno, "
        "campo `piatto_del_giorno`.",
    ]
    return "\n".join(righe)


# ── scrivere ─────────────────────────────────────────────────────────────


@SERVER.strumento(
    "imposta_dettagli_articolo",
    titolo="Scrivi la scheda pratica",
    descrizione=(
        "Riscrive per intero la scheda pratica di un articolo — le righe «Ritrovo · ore "
        "7.00 in piazza» che stanno sotto il titolo. Le righe precedenti vengono "
        "sostituite. Tre o quattro righe bastano: quelle che la gente cerca prima di "
        "leggere il testo."
    ),
    schema={
        "type": "object",
        "properties": {
            "articolo": {"type": "string", "description": "Slug o id dell'articolo."},
            "dettagli": TIPI["articolo"].extra["dettagli"],
        },
        "required": ["articolo", "dettagli"],
        "additionalProperties": False,
    },
    scrive=True,
)
def _imposta_dettagli(argomenti: dict, contesto: Contesto) -> str:
    articolo = risolvi(Articolo, argomenti.get("articolo"), "articolo")
    quanti = _dettagli_articolo(articolo, argomenti.get("dettagli") or [])
    righe = "\n".join(f"- {d.etichetta}: {d.valore}" for d in articolo.dettagli.all())
    return (
        f"✓ Scheda pratica di «{articolo.intestazione}» riscritta ({quanti} righe):\n{righe}"
        f"\n\n{PROMEMORIA}"
    )


CAMPI_IMPOSTAZIONI = (
    "mostra_banner_sagra", "banner_occhiello", "banner_titolo", "banner_testo",
    "banner_collegamento", "banner_etichetta_bottone",
    "modalita_sagra", "data_inizio_sagra", "mostra_conto_rovescia", "mostra_sponsor",
    "mostra_galleria_proloco", "iscrizioni_grest_aperte", "mostra_foto_grest",
)


@SERVER.strumento(
    "aggiorna_impostazioni",
    titolo="Interruttori del sito",
    descrizione=(
        "Il banner in cima alla home e gli interruttori delle sezioni condizionali "
        "(conto alla rovescia, sponsor, iscrizioni al Grest aperte, modalità sagra). "
        "Passa solo quello che vuoi cambiare. Il banner non è legato alla sagra: è lo "
        "spazio dell'appuntamento più imminente, qualunque esso sia."
    ),
    schema={
        "type": "object",
        "properties": {
            nome: schema_campo(ImpostazioniSito._meta.get_field(nome))
            for nome in CAMPI_IMPOSTAZIONI
        },
        "required": [],
        "additionalProperties": False,
    },
    scrive=True,
)
def _impostazioni(argomenti: dict, contesto: Contesto) -> str:
    impostazioni = ImpostazioniSito.caricate()
    if not argomenti:
        raise ErroreStrumento(
            "Non mi hai detto che cosa cambiare. Campi: " + ", ".join(CAMPI_IMPOSTAZIONI) + "."
        )
    toccati = []
    for nome, valore in argomenti.items():
        if nome not in CAMPI_IMPOSTAZIONI:
            raise ErroreStrumento(
                f"«{nome}» non è un'impostazione. Campi: {', '.join(CAMPI_IMPOSTAZIONI)}."
            )
        campo = ImpostazioniSito._meta.get_field(nome)
        setattr(impostazioni, nome, converti(campo, valore, nome))
        toccati.append(nome)
    _salva(impostazioni, "aggiornare le impostazioni")
    stato = "\n".join(
        f"- {nome}: {_valore_leggibile(impostazioni, ImpostazioniSito._meta.get_field(nome))}"
        for nome in CAMPI_IMPOSTAZIONI
    )
    return f"✓ Impostazioni aggiornate ({', '.join(toccati)}).\n\n{stato}\n\n{PROMEMORIA}"


@SERVER.strumento(
    "carica_immagine",
    titolo="Carica un'immagine",
    descrizione=(
        "Mette un'immagine fra i media del CMS e restituisce il percorso da usare nei campi "
        "«immagine» o «copertina» (per esempio la locandina di un evento). L'immagine "
        "arriva o come base64 o come indirizzo da scaricare. Per le foto d'archivio non "
        "usare questo strumento: là si incolla «url_esterna» e basta."
    ),
    schema={
        "type": "object",
        "properties": {
            "nome_file": {
                "type": "string",
                "description": "Come chiamare il file, es. «locandina-folpata.jpg».",
            },
            "destinazione": {
                "type": "string",
                "enum": list(CARTELLE_MEDIA),
                "description": "In quale cartella dei media: la stessa del contenuto a cui serve.",
            },
            "contenuto_base64": {
                "type": "string",
                "description": "Il file codificato in base64 (senza prefisso «data:»).",
            },
            "da_url": {
                "type": "string",
                "description": "In alternativa: l'indirizzo http(s) da cui scaricare l'immagine.",
            },
        },
        "required": ["nome_file"],
        "additionalProperties": False,
    },
    scrive=True,
)
def _carica_immagine(argomenti: dict, contesto: Contesto) -> str:
    try:
        from PIL import Image
    except ImportError as problema:  # pragma: no cover
        raise ErroreStrumento("Pillow non è installato nel CMS: non posso validare le immagini.") from problema

    base64_ricevuto = (argomenti.get("contenuto_base64") or "").strip()
    indirizzo = (argomenti.get("da_url") or "").strip()
    if bool(base64_ricevuto) == bool(indirizzo):
        raise ErroreStrumento("Serve «contenuto_base64» oppure «da_url»: uno dei due, non tutti e due.")

    if base64_ricevuto:
        if base64_ricevuto.startswith("data:"):
            base64_ricevuto = base64_ricevuto.split(",", 1)[-1]
        try:
            dati = base64.b64decode(base64_ricevuto, validate=True)
        except (binascii.Error, ValueError) as problema:
            raise ErroreStrumento("Il base64 non è valido: rimandalo senza spazi né a capo.") from problema
    else:
        if not indirizzo.lower().startswith(("http://", "https://")):
            raise ErroreStrumento("«da_url» deve cominciare con http:// o https://.")
        try:
            with urllib.request.urlopen(indirizzo, timeout=20) as risposta:  # noqa: S310 - schema verificato sopra
                dati = risposta.read(LIMITE_IMMAGINE + 1)
        except (urllib.error.URLError, ValueError, TimeoutError) as problema:
            raise ErroreStrumento(f"Non riesco a scaricare «{indirizzo}»: {problema}") from problema

    if not dati:
        raise ErroreStrumento("Il file è vuoto.")
    if len(dati) > LIMITE_IMMAGINE:
        raise ErroreStrumento(
            f"L'immagine pesa più di {LIMITE_IMMAGINE // (1024 * 1024)} MB: ridimensionala prima."
        )

    try:
        with Image.open(io.BytesIO(dati)) as immagine:
            immagine.verify()
            formato = (immagine.format or "").lower()
    except Exception as problema:  # noqa: BLE001 - Pillow alza di tutto
        raise ErroreStrumento(f"Non è un'immagine leggibile: {problema}") from problema

    estensioni = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif"}
    if formato not in estensioni:
        raise ErroreStrumento(
            f"Formato «{formato}» non adatto al sito: usa jpg, png o webp."
        )

    # L'estensione deve dire la verità sul formato: un .png che dentro è un
    # jpeg confonde il browser e, peggio, chi cerca il file fra i media.
    nome = get_valid_filename(os.path.basename(argomenti["nome_file"].strip())) or "immagine"
    radice, estensione = os.path.splitext(nome)
    attesa = estensioni[formato]
    if not (estensione.lower() == attesa or (attesa == ".jpg" and estensione.lower() == ".jpeg")):
        nome = (radice or "immagine") + attesa

    destinazione = (argomenti.get("destinazione") or "foto").strip().lower()
    if destinazione not in CARTELLE_MEDIA:
        raise ErroreStrumento(f"«destinazione» dev'essere una fra: {', '.join(CARTELLE_MEDIA)}.")

    percorso = default_storage.save(f"{destinazione}/{nome}", ContentFile(dati))
    peso = len(dati) / 1024
    return (
        f"✓ Immagine salvata: `{percorso}` ({peso:.0f} KB, {formato}).\n\n"
        "Adesso mettila dove serve:\n"
        f"- locandina di un evento → `aggiorna_evento` con `immagine: \"{percorso}\"`\n"
        f"- copertina di un articolo → `aggiorna_articolo` con `copertina: \"{percorso}\"`\n"
        f"- foto di una galleria → `crea_foto` con `immagine: \"{percorso}\"` e il collegamento "
        "giusto (`articolo`, `attivita`, `album` o `raccolta`).\n"
        "Ricordati il `testo_alternativo`: è quello che sentono gli screen reader."
    )


@SERVER.strumento(
    "elimina_contenuto",
    titolo="Elimina un contenuto",
    descrizione=(
        "Cancella un contenuto per sempre. Quasi sempre è meglio depubblicarlo "
        "(`pubblicato: false`): sparisce dal sito al prossimo build e resta recuperabile. "
        "Senza «conferma: true» questo strumento non cancella: mostra soltanto che cosa "
        "verrebbe portato via — eliminare un evento porta con sé il suo articolo, i "
        "dettagli e le foto."
    ),
    schema={
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": list(TIPI)},
            "id_o_slug": {"type": "string", "description": "Slug o id del contenuto."},
            "conferma": {
                "type": "boolean",
                "description": "Metti true solo dopo aver visto l'anteprima e averla fatta "
                "approvare a chi ti sta parlando.",
            },
        },
        "required": ["tipo", "id_o_slug"],
        "additionalProperties": False,
    },
    scrive=True,
)
def _elimina(argomenti: dict, contesto: Contesto) -> str:
    tipo = _tipo_richiesto(argomenti.get("tipo"))
    oggetto = risolvi(tipo.modello, argomenti.get("id_o_slug"), "id_o_slug")
    etichetta = str(oggetto)

    raccoglitore = NestedObjects(using=oggetto._state.db)
    raccoglitore.collect([oggetto])
    conteggi = {
        modello._meta.verbose_name_plural: len(oggetti)
        for modello, oggetti in raccoglitore.data.items()
    }
    riepilogo = " · ".join(f"{quanti} {nome}" for nome, quanti in conteggi.items())

    if not argomenti.get("conferma"):
        return (
            f"Non ho cancellato niente. Eliminare «{etichetta}» porterebbe via: {riepilogo}.\n\n"
            "Se è davvero quello che si vuole, richiama `elimina_contenuto` con "
            "`conferma: true`. Se invece basta toglierlo dal sito, `aggiorna_"
            f"{tipo.nome}` con `pubblicato: false` è più prudente e reversibile."
        )

    oggetto.delete()
    return f"✓ Eliminato «{etichetta}» e quello che ne dipendeva: {riepilogo}.\n\n{PROMEMORIA}"


# ── risorse e prompt ─────────────────────────────────────────────────────


@SERVER.risorsa(
    "canizzano://guida",
    nome="guida",
    titolo="La guida della redazione",
    descrizione="Come funziona il sito e come si scrivono i contenuti.",
)
def _risorsa_guida(contesto: Contesto) -> str:
    return manuale.guida("tutto")


@SERVER.risorsa(
    "canizzano://stato",
    nome="stato",
    titolo="Com'è messo il sito adesso",
    descrizione="Realtà, edizioni, prossimi appuntamenti, conteggi.",
)
def _risorsa_stato(contesto: Contesto) -> str:
    return manuale.stato_sito()


@SERVER.risorsa(
    "canizzano://modelli",
    nome="modelli",
    titolo="I campi di ogni tipo di contenuto",
    descrizione="Schema dei contenuti, letto dai modelli del CMS.",
)
def _risorsa_modelli(contesto: Contesto) -> str:
    return manuale.descrizione_modelli()


@SERVER.risorsa(
    "canizzano://icone",
    nome="icone",
    titolo="Le icone disponibili",
    descrizione="L'elenco delle icone e quale scegliere per ogni tipo di appuntamento.",
)
def _risorsa_icone(contesto: Contesto) -> str:
    return manuale.elenco_icone() + "\n\n" + manuale.SCELTA_ICONE


@SERVER.prompt(
    "nuovo_appuntamento",
    descrizione="Crea un evento (e, se serve, il suo articolo) partendo da quello che ti hanno detto.",
    argomenti=(
        {"name": "descrizione", "description": "Quello che si sa dell'appuntamento", "required": True},
    ),
)
def _prompt_evento(argomenti: dict) -> str:
    return f"""\
Devo mettere sul sito del quartiere questo appuntamento:

{argomenti.get('descrizione', '')}

Procedi così:
1. `panoramica` per vedere le attività e i loro slug.
2. `guida_del_sito` con argomento «regole» se non l'hai già letta in questa conversazione.
3. `cerca_contenuti` per controllare che l'evento non ci sia già.
4. `crea_evento` con l'attività giusta, data e ora italiane, un'icona coerente e un sommario
   di una o due righe. Metti `in_evidenza` solo se merita la home.
5. Valuta se serve un articolo: solo se c'è davvero altro da dire (ritrovo, quota, percorso).
   In quel caso `crea_articolo` con il corpo e tre o quattro righe di scheda pratica.
6. Chiudi dicendomi che cosa hai creato, con gli slug, e ricordami di pubblicare.
"""


@SERVER.prompt(
    "menu_della_sagra",
    descrizione="Rivedi il menù e il programma di una giornata della sagra.",
    argomenti=(
        {"name": "giorno", "description": "Il giorno da rivedere, es. «sabato 3 ottobre»", "required": False},
    ),
)
def _prompt_menu(argomenti: dict) -> str:
    giorno = argomenti.get("giorno") or "la prossima giornata"
    return f"""\
Voglio rivedere {giorno} della sagra.

Parti da `programma_sagra` per vedere le giornate con i loro orari e i piatti del giorno.
Poi dimmi com'è messa quella giornata e aspetta le mie modifiche: il menù si cambia con
`aggiorna_evento` sul campo `piatto_del_giorno` dell'evento di quella sera, non c'è una
tabella «menù» separata.
"""


@SERVER.prompt(
    "controllo_del_sito",
    descrizione="Cerca i buchi nei contenuti prima di una pubblicazione.",
)
def _prompt_controllo(argomenti: dict) -> str:
    return """\
Fammi un controllo del sito prima di pubblicare. Usa `panoramica` e `programma_sagra`, poi
segnalami: eventi passati ancora in evidenza in home; eventi della sagra in giorni senza
giornata; articoli senza copertina o senza scheda pratica; foto senza testo alternativo;
appuntamenti imminenti senza sommario. Non correggere niente da solo: fammi l'elenco e
aspetta che ti dica cosa sistemare.
"""
