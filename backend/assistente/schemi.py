"""
I contenuti del sito, descritti una volta sola.

Ogni strumento che crea o modifica qualcosa ha bisogno di sapere *quali*
campi esistono, di che tipo sono e che valori accettano. Quell'elenco pero'
c'e' gia': sta nei modelli di ``eventi/models.py``. Riscriverlo qui vorrebbe
dire tenerlo allineato a mano, e alla prima icona aggiunta l'agente
comincerebbe a proporre valori che il database rifiuta.

Quindi non lo riscriviamo: lo **leggiamo dai modelli**. Da un campo Django
sappiamo gia' tutto — tipo, obbligatorieta', valori ammessi, testo d'aiuto —
e da li' nasce sia lo schema JSON che il client MCP mostra all'agente, sia
la conversione dei valori che tornano indietro. Aggiungere un'icona resta
una riga in ``models.py``, come aggiungere una tinta e' una riga in
``toni.ts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from eventi.models import (
    Album,
    Articolo,
    Attivita,
    DettaglioArticolo,
    Edizione,
    Evento,
    Foto,
    Giornata,
    Luogo,
)

from .protocollo import ErroreStrumento

# Le cartelle dei media, una per tipo di contenuto: le stesse che usano gli
# ``upload_to`` dei modelli, cosi' i file caricati dall'agente finiscono
# dove finirebbero quelli caricati dall'admin.
CARTELLE_MEDIA = ("eventi", "articoli", "attivita", "edizioni", "album", "foto")


@dataclass(frozen=True)
class Tipo:
    """Un tipo di contenuto governabile dall'assistente."""

    nome: str
    modello: type[models.Model]
    plurale: str
    descrizione: str
    #: I campi che l'assistente puo' scrivere, nell'ordine in cui ha senso leggerli.
    campi: tuple[str, ...]
    #: Dove cerca ``cerca_contenuti``.
    ricerca: tuple[str, ...] = ()
    #: Campi in piu' che lo strumento accetta ma che non stanno sul modello.
    extra: dict = field(default_factory=dict)

    def campo(self, nome: str):
        try:
            return self.modello._meta.get_field(nome)
        except Exception as problema:  # pragma: no cover - percorso d'errore
            raise ErroreStrumento(
                f"«{nome}» non è un campo di {self.nome}. Campi validi: {', '.join(self.campi)}."
            ) from problema


TIPI: dict[str, Tipo] = {
    "evento": Tipo(
        nome="evento",
        modello=Evento,
        plurale="eventi",
        descrizione=(
            "L'appuntamento singolo. Lo stesso record alimenta quattro viste del sito: "
            "la card dei «prossimi appuntamenti» in home (se in_evidenza), la riga del "
            "calendario di quartiere, la riga oraria del programma della sagra e la "
            "colonna stagionale della pagina Pro Loco."
        ),
        campi=(
            "attivita", "titolo", "inizio", "fine", "tutto_il_giorno", "etichetta_data",
            "sommario", "descrizione", "categoria", "icona", "tono",
            "edizione", "stagione_scelta", "luogo", "luogo_libero",
            "piatto_del_giorno", "ingresso", "prenotazione_entro",
            "link", "link_etichetta", "immagine", "immagine_alt",
            "in_evidenza", "risalto", "ordine", "pubblicato", "slug",
        ),
        ricerca=("titolo", "sommario", "descrizione", "categoria", "piatto_del_giorno"),
    ),
    "articolo": Tipo(
        nome="articolo",
        modello=Articolo,
        plurale="articoli",
        descrizione=(
            "La pagina di approfondimento di un evento, su /eventi/<slug>. È facoltativa: "
            "esiste solo quando l'evento ha davvero qualcosa da raccontare (un ritrovo, una "
            "quota, un percorso). Appena esiste, tutte le card di quell'evento sul sito "
            "diventano un link alla pagina."
        ),
        campi=(
            "evento", "titolo", "occhiello", "sottotitolo", "corpo",
            "copertina", "copertina_url", "copertina_alt",
            "identita", "tono", "firma", "data_pubblicazione", "pubblicato", "slug",
        ),
        ricerca=("titolo", "sottotitolo", "corpo", "occhiello"),
        extra={
            "dettagli": {
                "type": "array",
                "description": (
                    "La scheda pratica in testa all'articolo: le righe «Ritrovo · ore 7.00». "
                    "Sostituisce per intero quelle già presenti. Se resta vuota la pagina "
                    "ripiega su data, luogo e ingresso dell'evento."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "etichetta": {"type": "string", "description": "«Quando», «Ritrovo», «Quota»…"},
                        "valore": {"type": "string", "description": "«ore 7.00 in piazza»"},
                    },
                    "required": ["etichetta", "valore"],
                },
            }
        },
    ),
    "giornata": Tipo(
        nome="giornata",
        modello=Giornata,
        plurale="giornate",
        descrizione=(
            "Come si presenta la card di un giorno della sagra: titolo, riga di richiamo e "
            "colore della pastiglia. Gli orari NON stanno qui: sono gli eventi con quella "
            "data. La giornata è solo la cornice."
        ),
        campi=("edizione", "data", "titolo", "occhiello", "tono", "sfondo_chiaro", "pubblicato"),
        ricerca=("titolo", "occhiello"),
    ),
    "foto": Tipo(
        nome="foto",
        modello=Foto,
        plurale="foto",
        descrizione=(
            "Una foto. Dove compare lo decide il collegamento che le dai: «articolo» la mette "
            "nella galleria di quell'articolo, «attivita» nella raccolta di quella realtà, "
            "«album» nell'archivio storico, «raccolta» in una galleria di pagina (grest, "
            "proloco, storia). L'immagine può stare qui (immagine) o su un servizio esterno "
            "(url_esterna): serve almeno una delle due."
        ),
        campi=(
            "raccolta", "articolo", "attivita", "album",
            "immagine", "url_esterna", "didascalia", "testo_alternativo",
            "anno", "ordine", "pubblicato",
        ),
        ricerca=("didascalia", "testo_alternativo", "raccolta"),
    ),
    "attivita": Tipo(
        nome="attivita",
        modello=Attivita,
        plurale="attività",
        descrizione=(
            "Una realtà del quartiere (Pro Loco, Parrocchia, Grest, Sagra, Calcio, Circolo "
            "NOI, Principato di Canizzano). Decide colore, icona e card in home. Se ne "
            "creano pochissime: prima di aggiungerne una, controlla che non esista già."
        ),
        campi=(
            "nome", "sottotitolo", "descrizione_breve", "descrizione",
            "identita", "icona", "tono", "sfondo_caldo",
            "collegamento", "etichetta_collegamento", "immagine", "immagine_alt",
            "email", "telefono", "ordine", "in_menu", "in_home", "pubblicato", "slug",
        ),
        ricerca=("nome", "sottotitolo", "descrizione", "descrizione_breve"),
    ),
    "edizione": Tipo(
        nome="edizione",
        modello=Edizione,
        plurale="edizioni",
        descrizione=(
            "L'annata di una realtà: «Canizzano in Festa 2026», «Pro Loco Cannetum 2026». "
            "Tiene insieme le giornate della sagra e gli eventi di quel programma."
        ),
        campi=("attivita", "anno", "titolo", "descrizione", "immagine", "immagine_alt",
               "pubblicato", "slug"),
        ricerca=("titolo", "descrizione"),
    ),
    "luogo": Tipo(
        nome="luogo",
        modello=Luogo,
        plurale="luoghi",
        descrizione=(
            "Una sede ricorrente (Tendone della sagra, Sala del Circolo NOI, chiesa…), così "
            "non va riscritta a ogni evento. Per una sede occasionale usa «luogo_libero» "
            "sull'evento invece di creare un luogo nuovo."
        ),
        campi=("nome", "indirizzo", "mappa_url"),
        ricerca=("nome", "indirizzo"),
    ),
    "album": Tipo(
        nome="album",
        modello=Album,
        plurale="album",
        descrizione=(
            "Una raccolta dell'archivio storico su /archivio. Le foto d'archivio NON si "
            "caricano nel CMS — lo spazio sull'hosting è poco: stanno su un servizio cloud "
            "e qui si incolla il link (url_esterna sulle foto, album_url per la raccolta)."
        ),
        campi=("titolo", "anno", "periodo", "descrizione", "copertina", "copertina_url",
               "copertina_alt", "attivita", "album_url", "ordine", "pubblicato", "slug"),
        ricerca=("titolo", "descrizione", "periodo"),
    ),
    "dettaglio": Tipo(
        nome="dettaglio",
        modello=DettaglioArticolo,
        plurale="dettagli d'articolo",
        descrizione="Una riga della scheda pratica di un articolo. Si scrivono con «imposta_dettagli_articolo».",
        campi=("articolo", "etichetta", "valore", "ordine"),
        ricerca=("etichetta", "valore"),
    ),
}

#: I tipi per cui generiamo gli strumenti «crea_…» e «aggiorna_…».
TIPI_SCRIVIBILI = ("evento", "articolo", "giornata", "foto", "attivita", "edizione", "luogo", "album")


# ── dal campo Django allo schema JSON ────────────────────────────────────


def valori_ammessi(campo) -> list[tuple[str, str]]:
    """I valori di un campo a scelta fissa, con la loro etichetta italiana."""
    return [(str(valore), str(etichetta)) for valore, etichetta in (campo.choices or [])]


def _descrizione_campo(campo) -> str:
    """
    Il testo d'aiuto del campo, piu' quello che l'agente non puo' indovinare.

    Se il modello non ha un ``help_text`` la descrizione resta vuota: il nome
    del campo dice gia' tutto (``titolo``, ``email``), e ogni parola in piu'
    e' peso che il client si porta dietro in ogni conversazione.
    """
    testo = str(campo.help_text or "").strip()

    if isinstance(campo, (models.ForeignKey, models.OneToOneField)):
        bersaglio = campo.related_model
        ha_slug = any(getattr(c, "name", "") == "slug" for c in bersaglio._meta.get_fields())
        chiave = "lo slug" if ha_slug else "il nome"
        testo = f"{testo} Indica {chiave} (consigliato) o l'id numerico come stringa."
    elif isinstance(campo, models.ImageField):
        testo = f"{testo} Percorso restituito da «carica_immagine», es. «eventi/locandina.jpg»."
    elif isinstance(campo, models.DateTimeField):
        testo = f"{testo} Data e ora italiane: «2026-12-13T19:30»."
    elif isinstance(campo, models.DateField):
        testo = f"{testo} Data: «2026-12-13»."
    return " ".join(testo.split())


def schema_campo(campo) -> dict:
    """Lo schema JSON di un singolo campo del modello."""
    descrizione = _descrizione_campo(campo)
    scelte = valori_ammessi(campo)

    if scelte:
        # I valori ammessi stanno nell'«enum», che il client mostra da se':
        # ripeterli nella descrizione con la loro etichetta italiana
        # raddoppierebbe il peso dello schema. Il significato di ognuno sta
        # nella guida — `guida_del_sito` con argomento «icone» o «colori».
        valori = [valore for valore, _ in scelte]
        if campo.blank:
            valori.append("")
        return _con_descrizione({"type": "string", "enum": valori}, descrizione)

    if isinstance(campo, models.BooleanField):
        return _con_descrizione({"type": "boolean"}, descrizione)
    # Attenzione all'ordine: DateTimeField eredita da DateField, e un istante
    # non e' una data — deve restare una stringa con dentro anche l'ora.
    if isinstance(campo, models.DateField) and not isinstance(campo, models.DateTimeField):
        return _con_descrizione({"type": "string", "format": "date"}, descrizione)
    if isinstance(campo, models.IntegerField):
        return _con_descrizione({"type": "integer"}, descrizione)
    return _con_descrizione({"type": "string"}, descrizione)


def _con_descrizione(schema: dict, descrizione: str) -> dict:
    if descrizione:
        schema["description"] = descrizione
    return schema


def obbligatorio(campo) -> bool:
    """Vero se il campo va per forza valorizzato alla creazione."""
    if campo.blank or campo.has_default() or campo.null:
        return False
    return not getattr(campo, "auto_now", False) and not getattr(campo, "auto_now_add", False)


def schema_tipo(tipo: Tipo, *, creazione: bool) -> dict:
    """Lo schema JSON dello strumento «crea_x» o «aggiorna_x»."""
    proprieta: dict = {}
    richiesti: list[str] = []

    if not creazione:
        proprieta["id_o_slug"] = {
            "type": "string",
            "description": f"Quale {tipo.nome} modificare: lo slug (consigliato) o l'id numerico.",
        }
        richiesti.append("id_o_slug")

    for nome in tipo.campi:
        campo = tipo.campo(nome)
        proprieta[nome] = schema_campo(campo)
        if creazione and obbligatorio(campo):
            richiesti.append(nome)

    for nome, schema in tipo.extra.items():
        proprieta[nome] = schema

    return {
        "type": "object",
        "properties": proprieta,
        "required": richiesti,
        "additionalProperties": False,
    }


# ── dai valori dell'agente ai campi del modello ──────────────────────────


FORMATI_DATA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
FORMATI_ISTANTE = (
    "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M", "%d/%m/%Y %H.%M", "%Y-%m-%d %H.%M",
)


def a_data(valore, nome: str) -> date:
    if isinstance(valore, date) and not isinstance(valore, datetime):
        return valore
    testo = str(valore).strip()
    letta = parse_date(testo)
    if letta:
        return letta
    for formato in FORMATI_DATA:
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    raise ErroreStrumento(f"«{nome}»: non riesco a leggere la data «{valore}». Scrivila «2026-12-13».")


def a_istante(valore, nome: str) -> datetime:
    """
    Da testo a istante, sempre con il fuso del quartiere.

    Un orario senza fuso («2026-12-13T19:30») e' l'ora del campanile: va
    interpretato come Europe/Rome, non come UTC, o la sagra apre due ore
    prima sul sito.
    """
    if isinstance(valore, datetime):
        letto = valore
    else:
        testo = str(valore).strip()
        letto = parse_datetime(testo)
        if letto is None:
            for formato in FORMATI_ISTANTE:
                try:
                    letto = datetime.strptime(testo, formato)
                    break
                except ValueError:
                    continue
        if letto is None:
            giorno = parse_date(testo)
            if giorno is None:
                for formato in FORMATI_DATA:
                    try:
                        giorno = datetime.strptime(testo, formato).date()
                        break
                    except ValueError:
                        continue
            if giorno is not None:
                letto = datetime(giorno.year, giorno.month, giorno.day)
        if letto is None:
            raise ErroreStrumento(
                f"«{nome}»: non riesco a leggere data e ora da «{valore}». "
                "Scrivile «2026-12-13T19:30» (ora italiana)."
            )
    if timezone.is_naive(letto):
        letto = timezone.make_aware(letto, timezone.get_current_timezone())
    return letto


def risolvi(modello: type[models.Model], riferimento, campo: str = "") -> models.Model:
    """Trova un record da slug, id o nome — nell'ordine in cui li scrive un umano."""
    testo = str(riferimento).strip()
    if not testo:
        raise ErroreStrumento(f"Manca il riferimento a {modello._meta.verbose_name}.")

    nomi_campi = {c.name for c in modello._meta.get_fields() if hasattr(c, "name")}

    if "slug" in nomi_campi:
        trovato = modello.objects.filter(slug=testo).first()
        if trovato:
            return trovato
    if testo.isdigit():
        trovato = modello.objects.filter(pk=int(testo)).first()
        if trovato:
            return trovato
    for alternativa in ("nome", "titolo"):
        if alternativa in nomi_campi:
            trovati = list(modello.objects.filter(**{f"{alternativa}__iexact": testo})[:2])
            if len(trovati) == 1:
                return trovati[0]
            if len(trovati) > 1:
                raise ErroreStrumento(
                    f"«{testo}» corrisponde a più di un {modello._meta.verbose_name}: "
                    "usa lo slug o l'id."
                )
    # Ultimo tentativo: una corrispondenza parziale, che spesso e' quello che
    # l'agente intendeva («parrocchia» per «Parrocchia della Visitazione»).
    for alternativa in ("nome", "titolo"):
        if alternativa in nomi_campi:
            trovati = list(modello.objects.filter(**{f"{alternativa}__icontains": testo})[:2])
            if len(trovati) == 1:
                return trovati[0]

    disponibili = ", ".join(str(oggetto) for oggetto in modello.objects.all()[:15]) or "nessuno"
    dove = f"«{campo}»: " if campo else ""
    raise ErroreStrumento(
        f"{dove}non trovo {modello._meta.verbose_name} «{testo}». Ci sono: {disponibili}."
    )


def _valore_da_scelte(campo, valore, nome: str) -> str:
    """Accetta il valore giusto o la sua etichetta («Montagna / gita fuori porta»)."""
    scelte = valori_ammessi(campo)
    testo = str(valore).strip()
    if testo == "" and campo.blank:
        return ""
    ammessi = {valore for valore, _ in scelte}
    if testo in ammessi:
        return testo
    for chiave, etichetta in scelte:
        if testo.lower() in (chiave.lower(), etichetta.lower()):
            return chiave
    elenco = "; ".join(f"{chiave} = {etichetta}" for chiave, etichetta in scelte)
    raise ErroreStrumento(f"«{nome}»: «{valore}» non è un valore ammesso. Scegli fra: {elenco}.")


def _a_booleano(valore, nome: str) -> bool:
    if isinstance(valore, bool):
        return valore
    testo = str(valore).strip().lower()
    if testo in {"true", "1", "si", "sì", "vero", "yes"}:
        return True
    if testo in {"false", "0", "no", "falso"}:
        return False
    raise ErroreStrumento(f"«{nome}»: serve vero o falso, non «{valore}».")


def _a_intero(valore, nome: str) -> int:
    try:
        return int(str(valore).strip())
    except (TypeError, ValueError) as problema:
        raise ErroreStrumento(f"«{nome}»: serve un numero intero, non «{valore}».") from problema


def _percorso_media(valore, nome: str) -> str:
    percorso = str(valore).strip().lstrip("/")
    if percorso.startswith("media/"):
        percorso = percorso[len("media/"):]
    if not percorso:
        return ""
    if not default_storage.exists(percorso):
        raise ErroreStrumento(
            f"«{nome}»: il file «{percorso}» non c'è fra i media. Caricalo prima con "
            "«carica_immagine», che ti restituisce il percorso da usare qui — oppure, "
            "se l'immagine sta su un servizio esterno, usa il campo con «_url»."
        )
    return percorso


def converti(campo, valore, nome: str):
    """Il valore che arriva dall'agente, nella forma che vuole il modello."""
    if valore is None:
        if campo.null:
            return None
        if isinstance(campo, (models.CharField, models.TextField)) and campo.blank:
            return ""
        raise ErroreStrumento(f"«{nome}» non può essere vuoto.")

    if isinstance(campo, (models.ForeignKey, models.OneToOneField)):
        if str(valore).strip() == "":
            if campo.null:
                return None
            raise ErroreStrumento(f"«{nome}» non può essere vuoto.")
        return risolvi(campo.related_model, valore, nome)
    if campo.choices:
        return _valore_da_scelte(campo, valore, nome)
    if isinstance(campo, models.BooleanField):
        return _a_booleano(valore, nome)
    if isinstance(campo, models.ImageField):
        return _percorso_media(valore, nome)
    if isinstance(campo, models.DateTimeField):
        return a_istante(valore, nome)
    if isinstance(campo, models.DateField):
        return a_data(valore, nome)
    if isinstance(campo, (models.IntegerField, models.SmallIntegerField)):
        return _a_intero(valore, nome)
    return str(valore)


def applica(oggetto: models.Model, tipo: Tipo, valori: dict) -> list[str]:
    """Scrive i campi ricevuti sull'oggetto. Torna l'elenco di quelli toccati."""
    toccati: list[str] = []
    for nome, valore in valori.items():
        if nome in tipo.extra or nome == "id_o_slug":
            continue
        if nome not in tipo.campi:
            raise ErroreStrumento(
                f"«{nome}» non è un campo di {tipo.nome}. Campi validi: {', '.join(tipo.campi)}."
            )
        campo = tipo.campo(nome)
        setattr(oggetto, nome, converti(campo, valore, nome))
        toccati.append(nome)
    return toccati
