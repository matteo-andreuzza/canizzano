"""
Quello che l'assistente deve sapere prima di toccare il sito.

Un agente che sa solo «esiste una tabella eventi» combina disastri educati:
crea un articolo per l'apertura degli stand, attacca le foto all'attività
invece che all'articolo, mette la gita di montagna con l'icona della chiesa.
Qui c'e' il mestiere della redazione — le regole che stanno scritte nel
README, nei docstring dei modelli e nella testa di chi il sito lo aggiorna.

Meta' di questo testo e' fisso (le regole editoriali), meta' viene letto dal
database quando serve (le realta' del quartiere, le edizioni, le raccolte
che esistono davvero): cosi' l'agente non lavora mai su un elenco vecchio.
"""

from __future__ import annotations

from django.utils import timezone
from django.utils.formats import date_format

from eventi.models import (
    Album,
    Articolo,
    Attivita,
    Edizione,
    Evento,
    Foto,
    Giornata,
    Icona,
    ImpostazioniSito,
    Luogo,
)

from .schemi import TIPI, TIPI_SCRIVIBILI, valori_ammessi

# ── quello che non si legge dal database: il mestiere ────────────────────

SCELTA_ICONE = """\
| Se l'evento è… | icona |
| --- | --- |
| stand gastronomico, cena, folpata, pesce, griglia | `posate` |
| piatto del giorno, serata a tema, gara di dolci | `cucina` |
| concerto, orchestra, ballo, dj, banda | `musica` |
| messa, rosario, processione, benedizione | `croce` |
| parrocchia in generale, patrono, sagra religiosa | `chiesa` |
| Grest, bambini, catechismo, festa dei ragazzi | `bambini` |
| Pimpa, appuntamenti per i più piccoli | `pimpa` |
| torneo, partita, sport | `pallone` |
| gita in montagna, camminata, Cansiglio | `montagna` |
| biciclettata, pedalata | `bici` |
| lotteria, premiazione, riffa | `regalo` |
| falò, panevin, fuochi | `fuoco` |
| laboratori, pittura, mani in pasta | `pennello` |
| cinema, proiezione, video | `video` |
| giochi, gonfiabili, caccia al tesoro | `gioco` |
| assemblea, ritrovo soci, volontari, tesseramento | `persone` |
| apertura del tendone, la sagra come contenitore | `tendone` |
| ricorrenze del Principato di Canizzano | `canneto` |
| pulizia del quartiere, natura, alberi | `foglia` |
| Sile, argini, gite sull'acqua | `fiume` |
| racconto, libro, presentazione, storia del paese | `libro` |
| mostra fotografica, archivio | `fotografia` |
| circolo, bar, sala, tombola al coperto | `casa` |
| orari, aperture, «dalle 19 alle 23» | `orologio` |
| festa generica, mercatino, quando nient'altro calza | `stella` |

L'icona di un evento è **facoltativa**: se la lasci vuota il sito usa quella
della sua attività, che spesso è la scelta giusta. Mettila quando dice
qualcosa in più della realtà che organizza.
"""

REGOLE = """\
## Le dieci regole della redazione

1. **Non inventare gli slug.** Prima `cerca_contenuti` o `panoramica`, poi
   scrivi. Gli slug si generano da soli dal titolo: lasciali vuoti.
2. **Le date sono ore italiane.** «2026-12-13T19:30» è le sette e mezza di
   sera del campanile, non UTC.
3. **Ogni evento sta su un'attività esistente.** Non creare realtà nuove per
   un singolo appuntamento: la folpata del Principato è un *evento*
   dell'attività «Principato di Canizzano», non una nuova attività.
4. **L'articolo è l'eccezione, non la regola.** «Apertura degli stand» si
   esaurisce in una riga di programma. Fai un articolo solo quando c'è
   davvero altro da dire: un ritrovo, una quota, un percorso, una storia.
   Appena l'articolo esiste, *tutte* le card di quell'evento sul sito
   diventano un link a `/eventi/<slug>`.
5. **Le foto di un articolo si collegano all'articolo.** Il campo `articolo`
   della foto, non `attivita`: è l'errore classico, e la foto finisce nella
   pagina sbagliata senza dare errore.
6. **`in_evidenza` è la home, `risalto` è la sagra.** Il primo mette l'evento
   fra i «prossimi appuntamenti» in home; il secondo lo fa diventare un
   blocco colorato a tutta larghezza nel programma della sagra. Sono cose
   diverse: non accenderli a caso.
7. **Quando la data non è precisa, scrivila a parole.** `etichetta_data`:
   «metà quaresima», «un sabato di maggio», «aprile → settembre». Il campo
   `inizio` serve comunque all'ordinamento, quindi mettici una data
   plausibile.
8. **Depubblicare invece di cancellare.** `pubblicato: false` toglie il
   contenuto dal prossimo build e lo lascia recuperabile. Cancella solo
   quando è davvero spazzatura: eliminare un evento porta via con sé il suo
   articolo, i dettagli e le foto.
9. **L'archivio storico sta fuori.** Lo spazio sull'hosting è poco: le foto
   d'archivio si mettono su un servizio cloud e qui si incolla `url_esterna`.
10. **Le modifiche non sono online finché non si pubblica.** Il sito è
    statico: dopo aver scritto nel CMS qualcuno deve lanciare
    `./canizzano.sh tutto` dalla cartella del progetto. L'anteprima su
    `localhost:4321`, invece, si aggiorna ricaricando il browser.
"""

CORPO_ARTICOLO = """\
## Come si scrive il corpo di un articolo

Il campo `corpo` usa quattro segni, gli stessi che si scrivono in admin:

```
## Un sottotitolo
Un paragrafo qualsiasi. Una riga vuota separa i paragrafi.
- una voce di elenco
> una nota da mettere in evidenza
```

Niente HTML, niente grassetti: il sito impagina da sé. Sopra il testo compare
la **scheda pratica** — le righe di `dettagli` («Ritrovo · ore 7.00 in
piazza», «Quota · 25 € con pranzo»): mettine tre o quattro, quelle che la
gente cerca prima di leggere. Se non ne scrivi nessuna, la pagina ripiega su
data, luogo e ingresso dell'evento, e va benissimo.

Il tono di voce del sito è quello di un vicino che racconta, non di un
comunicato: frasi corte, nessun punto esclamativo, nessun «imperdibile».
"""

SAGRA = """\
## La sagra, pezzo per pezzo

«Canizzano in Festa» è la festa d'ottobre sotto il tendone, e sul sito è
`/sagra`. Si compone di tre cose che stanno in tre tabelle diverse:

- **L'edizione** (`edizione`) è l'annata: «Canizzano in Festa 2026». Tiene
  insieme tutto il resto.
- **Le giornate** (`giornata`) sono le *cornici* dei singoli giorni: titolo,
  occhiello («si apre il tendone»), colore della pastiglia. Non contengono
  orari.
- **Gli eventi** (`evento`) sono le righe orarie dentro la card del giorno.
  Un evento finisce nel programma di una giornata semplicemente perché ha la
  **stessa data**: non c'è un collegamento diretto fra evento e giornata.

Quindi: per aggiungere una riga al programma si crea un **evento** con la
data giusta, l'attività «Sagra», l'edizione dell'anno e il luogo «Tendone
della sagra». Per cambiare come si presenta il giorno (titolo, colore) si
modifica la **giornata**.

**Il menù della cucina** è la tabella in fondo a `/sagra`: la compongono gli
eventi che hanno `piatto_del_giorno` valorizzato (oppure una
`prenotazione_entro`). Cambiare il menù di una serata vuol dire modificare
`piatto_del_giorno` sull'evento di quella sera — non esiste una tabella
«menù» separata. Usa `programma_sagra` per vedere giornate e piatti in un
colpo solo.

A parità di orario, `ordine` decide chi viene prima. `risalto` fa diventare
la riga un blocco colorato a tutta larghezza: uno o due per giornata, non di
più, o non risalta più niente.
"""

PAGINE = """\
## Le pagine del sito e cosa le alimenta

| Indirizzo | Cosa mostra | Da dove viene |
| --- | --- | --- |
| `/` | Banner, prossimi appuntamenti, le realtà del quartiere | impostazioni + eventi con `in_evidenza` + attività con `in_home` |
| `/calendario` | Tutti gli appuntamenti, mese per mese | tutti gli eventi pubblicati |
| `/proloco` | L'anno della Pro Loco per stagioni | eventi dell'attività «Pro Loco Cannetum», divisi per `stagione` |
| `/sagra` | Programma giorno per giorno e menù | edizione + giornate + eventi dell'attività «Sagra» |
| `/grest` | Il Grest dei ragazzi | impostazioni (iscrizioni aperte) + foto raccolta `grest` |
| `/storia` | La storia del quartiere | testi fissi nel codice |
| `/archivio` | Le raccolte fotografiche storiche | album + foto con `url_esterna` |
| `/eventi/<slug>` | L'approfondimento di un evento | un articolo, se esiste |

La stagione di un evento si deduce dal mese; `stagione_scelta` serve solo a
smentire il calendario quando la festa appartiene a un'altra stagione (il
Processo alla Vecchia è di marzo ma è una festa d'inverno).
"""

COLORI = """\
## Colori: identità e toni

Il sistema ha due voci cromatiche, più il neutro:

- **terracotta** — la sagra, il Grest, il calore della festa;
- **salvia** — il quartiere di tutti i giorni: Pro Loco, parrocchia, storia;
- **neutro** — le realtà che non vogliono un colore proprio.

`identita` decide il colore generale di una realtà o di un articolo; `tono`
decide la singola tinta di un disco, di una pastiglia o di una card, ed è
scelto a mano perché in home le card alternano volutamente tinte diverse.
Se non sai quale mettere, lascia `tono` vuoto: il sito usa il colore
dell'identità, che è quasi sempre la scelta giusta.
"""


# ── quello che si legge dal database ─────────────────────────────────────


def _realta() -> str:
    righe = ["| slug | nome | identità | icona | in home | in menu |", "| --- | --- | --- | --- | --- | --- |"]
    for attivita in Attivita.objects.all().order_by("ordine", "nome"):
        righe.append(
            f"| `{attivita.slug}` | {attivita.nome} | {attivita.identita} | "
            f"{attivita.icona or '—'} | {'sì' if attivita.in_home else 'no'} | "
            f"{'sì' if attivita.in_menu else 'no'} |"
        )
    if len(righe) == 2:
        righe.append("| — | *nessuna attività ancora: il CMS è vuoto* | | | | |")
    return "\n".join(righe)


def _edizioni() -> str:
    righe = []
    for edizione in Edizione.objects.select_related("attivita").order_by("-anno"):
        giornate = edizione.giornate.count()
        eventi = edizione.eventi.count()
        righe.append(
            f"- `{edizione.slug}` — {edizione.etichetta} (attività `{edizione.attivita.slug}`, "
            f"{giornate} giornate, {eventi} eventi)"
        )
    return "\n".join(righe) or "- *nessuna edizione ancora*"


def _luoghi() -> str:
    nomi = [f"`{luogo.nome}`" for luogo in Luogo.objects.all()[:20]]
    return ", ".join(nomi) or "*nessun luogo salvato*"


def _raccolte() -> str:
    nomi = sorted(
        {raccolta for raccolta in Foto.objects.values_list("raccolta", flat=True) if raccolta}
    )
    return ", ".join(f"`{nome}`" for nome in nomi) or "*nessuna raccolta ancora*"


def elenco_icone() -> str:
    return "\n".join(f"- `{valore}` — {etichetta}" for valore, etichetta in Icona.choices)


def descrizione_modelli() -> str:
    """I campi di ogni tipo di contenuto, letti dai modelli: non invecchia mai."""
    pezzi = []
    for nome in (*TIPI_SCRIVIBILI, "dettaglio"):
        tipo = TIPI[nome]
        pezzi.append(f"### {tipo.nome} ({tipo.plurale})\n\n{tipo.descrizione}\n")
        righe = ["| campo | tipo | obbligatorio | a cosa serve |", "| --- | --- | --- | --- |"]
        for campo_nome in tipo.campi:
            campo = tipo.campo(campo_nome)
            scelte = valori_ammessi(campo)
            if scelte:
                genere = "scelta fra: " + ", ".join(valore for valore, _ in scelte)
            elif campo.is_relation:
                genere = f"→ {campo.related_model._meta.verbose_name}"
            else:
                genere = campo.get_internal_type().replace("Field", "").lower()
            aiuto = " ".join(str(campo.help_text or campo.verbose_name).split())
            obbligo = "sì" if (not campo.blank and not campo.has_default() and not campo.null) else "—"
            righe.append(f"| `{campo_nome}` | {genere} | {obbligo} | {aiuto} |")
        pezzi.append("\n".join(righe) + "\n")
    return "\n".join(pezzi)


def stato_sito() -> str:
    """Com'è messo il sito adesso: la fotografia che serve prima di agire."""
    adesso = timezone.now()
    impostazioni = ImpostazioniSito.caricate()
    prossimi = list(
        Evento.visibili.select_related("attivita")
        .filter(inizio__gte=adesso)
        .order_by("inizio")[:10]
    )
    ultima_modifica = (
        Evento.objects.order_by("-aggiornato_il").values_list("aggiornato_il", flat=True).first()
    )

    righe = [
        "## Com'è messo il sito adesso",
        "",
        f"Oggi è {date_format(timezone.localtime(adesso), 'l j F Y, H:i')} (ora italiana).",
        "",
        "### Le realtà del quartiere",
        "",
        _realta(),
        "",
        "### Edizioni",
        "",
        _edizioni(),
        "",
        f"**Luoghi salvati:** {_luoghi()}",
        "",
        f"**Raccolte di foto in uso:** {_raccolte()}",
        "",
        "### Conteggi",
        "",
        f"- eventi: {Evento.objects.count()} ({Evento.visibili.count()} pubblicati, "
        f"{Evento.visibili.filter(inizio__gte=adesso).count()} ancora da venire)",
        f"- articoli: {Articolo.objects.count()} · giornate di sagra: {Giornata.objects.count()}",
        f"- foto: {Foto.objects.count()} · album d'archivio: {Album.objects.count()}",
        "",
        "### Prossimi appuntamenti",
        "",
    ]
    if prossimi:
        for evento in prossimi:
            segni = []
            if evento.in_evidenza:
                segni.append("in evidenza")
            if hasattr(evento, "articolo"):
                segni.append(f"articolo /eventi/{evento.articolo.slug}")
            coda = f" · {', '.join(segni)}" if segni else ""
            righe.append(
                f"- {timezone.localtime(evento.inizio):%d/%m/%Y %H:%M} — **{evento.titolo}** "
                f"(`{evento.slug}`, attività `{evento.attivita.slug}`){coda}"
            )
    else:
        righe.append("*Nessun appuntamento futuro: il calendario del sito è vuoto.*")

    righe += [
        "",
        "### Banner in home",
        "",
        f"- acceso: {'sì' if impostazioni.mostra_banner_sagra else 'no'}",
        f"- titolo: «{impostazioni.banner_titolo or '—'}»",
        f"- occhiello: «{impostazioni.banner_occhiello or '—'}» · "
        f"bottone: «{impostazioni.banner_etichetta_bottone or 'Vai al programma'}» "
        f"→ {impostazioni.banner_collegamento or '/sagra'}",
        "",
        f"Ultima modifica a un evento: "
        f"{timezone.localtime(ultima_modifica):%d/%m/%Y %H:%M}" if ultima_modifica else "",
    ]
    return "\n".join(riga for riga in righe if riga is not None)


# ── i testi che gli strumenti servono all'agente ─────────────────────────

ARGOMENTI = {
    "tutto": "l'intera guida",
    "regole": "le regole della redazione",
    "sagra": "come è fatta la sagra",
    "articoli": "quando e come si scrive un articolo",
    "foto": "come si mettono le foto",
    "icone": "quale icona scegliere",
    "colori": "identità e toni",
    "modelli": "i campi di ogni tipo di contenuto",
    "pagine": "le pagine del sito e cosa le alimenta",
    "stato": "com'è messo il sito adesso",
    "pubblicazione": "come si manda online",
}

INTRODUZIONE = """\
# canizzano.it — la guida della redazione

Canizzano è un quartiere di Treviso. Il suo sito è un **sito statico**: le
pagine vengono generate una volta e caricate su un hosting condiviso, senza
database e senza runtime. Quello che stai governando adesso è il **CMS**, che
gira solo sul computer di casa: qui si redigono i contenuti, e a ogni build
Astro li legge e ne fa pagine HTML.

```
   redazione (tu)          build                    pubblicazione
┌──────────────────┐   ┌──────────────┐        ┌──────────────────┐
│ CMS Django + MCP │──▶│ Astro build  │──dist/─▶│ hosting via FTP  │
└──────────────────┘   └──────────────┘        └──────────────────┘
```

**Conseguenza pratica, la più importante di tutte:** quello che scrivi qui
non è online finché qualcuno non lancia `./canizzano.sh tutto` dalla cartella
del progetto. Dillo sempre a chi ti sta parlando quando hai finito di
scrivere, invece di lasciargli credere che il sito sia già cambiato.
"""

FOTO = """\
## Come si mettono le foto

Una foto può stare in due posti, e il campo che scegli decide dove compare:

- **`immagine`** — il file caricato nel CMS. Lo carichi con
  `carica_immagine`, che ti restituisce un percorso tipo `foto/locandina.jpg`
  da mettere in questo campo. Va sull'hosting insieme al sito, quindi si usa
  per le foto che contano: locandine, copertine, gallerie degli articoli.
- **`url_esterna`** — l'indirizzo diretto di un'immagine ospitata altrove.
  Obbligatoria per l'archivio storico, dove lo spazio dell'hosting non
  basterebbe.

Poi c'è il **collegamento**, che decide in quale pagina finisce:

| Campo valorizzato | Dove compare la foto |
| --- | --- |
| `articolo` | nella galleria «Com'è andata» di quell'articolo |
| `attivita` | nella raccolta di quella realtà |
| `album` | nell'album dell'archivio storico |
| `raccolta` | in una galleria di pagina (`grest`, `proloco`, `storia`…) |

Se una foto non compare dove ti aspettavi, il motivo è quasi sempre questo:
è stata collegata all'attività invece che all'articolo. Sono due gallerie
diverse.

Scrivi sempre `testo_alternativo`: è quello che sentono gli screen reader.
La `didascalia` invece si vede sotto la foto, e può restare vuota.

**Copertina di un articolo:** non è una foto della galleria, è il campo
`copertina` (file) o `copertina_url` (link) dell'articolo stesso.
"""

PUBBLICAZIONE = """\
## Come va online quello che scrivi

Il sito è statico: il CMS non lo aggiorna da solo.

```bash
./canizzano.sh dev      # anteprima su localhost:4321, si aggiorna ricaricando
./canizzano.sh tutto    # genera il sito e lo carica sull'hosting via FTP
```

Tu non puoi lanciare questi comandi: girano sulla macchina di casa, fuori dal
CMS. Quando hai finito un lavoro, chiudi dicendo che cosa hai cambiato e
ricorda che per vederlo su canizzano.it serve `./canizzano.sh tutto`.

Se chi ti sta parlando ha un terminale sulla cartella del progetto (per
esempio Claude Code), può lanciarlo lui subito dopo.
"""


def guida(argomento: str = "tutto") -> str:
    argomento = (argomento or "tutto").strip().lower()
    pezzi: dict[str, str] = {
        "regole": REGOLE,
        "sagra": SAGRA,
        "articoli": CORPO_ARTICOLO,
        "foto": FOTO,
        "icone": "## Le icone disponibili\n\n" + elenco_icone() + "\n\n" + SCELTA_ICONE,
        "colori": COLORI,
        "modelli": "## I tipi di contenuto\n\n" + descrizione_modelli(),
        "pagine": PAGINE,
        "stato": stato_sito(),
        "pubblicazione": PUBBLICAZIONE,
    }
    if argomento in pezzi:
        return pezzi[argomento]
    if argomento != "tutto":
        return (
            f"Non ho una sezione «{argomento}». Argomenti: "
            + ", ".join(ARGOMENTI)
            + ".\n\n"
            + INTRODUZIONE
        )
    return "\n\n".join(
        [
            INTRODUZIONE,
            REGOLE,
            stato_sito(),
            SAGRA,
            CORPO_ARTICOLO,
            FOTO,
            PAGINE,
            COLORI,
            "## Le icone disponibili\n\n" + elenco_icone() + "\n\n" + SCELTA_ICONE,
            "## I tipi di contenuto\n\n" + descrizione_modelli(),
            PUBBLICAZIONE,
        ]
    )


def istruzioni() -> str:
    """
    Il biglietto da visita del server: e' la prima cosa che il client MCP
    infila nel contesto dell'agente, quindi dev'essere corto e vero.
    """
    realta = ", ".join(
        f"«{a.nome}» (`{a.slug}`)" for a in Attivita.visibili.all().order_by("ordine")[:10]
    )
    return f"""\
Sei la redazione di **canizzano.it**, il sito del quartiere di Canizzano (Treviso).
Da qui governi il CMS: eventi, articoli, programma della sagra, foto, impostazioni.

Le realtà del quartiere in questo momento: {realta or "nessuna, il CMS è vuoto"}.

Come lavorare, in breve:
1. Prima guarda, poi scrivi: `panoramica` per lo stato del sito, `cerca_contenuti`
   per trovare le cose, `programma_sagra` per il programma di ottobre.
2. Non inventare slug, id o nomi di attività: cercali.
3. `guida_del_sito` contiene le regole della redazione (quando un evento merita un
   articolo, quale icona scegliere, come si scrive il corpo di un articolo, come è
   fatta la sagra). Leggila prima di creare contenuti, non dopo.
4. Le date sono ore italiane: «2026-12-13T19:30».
5. Il sito è statico: quello che scrivi va online solo quando qualcuno lancia
   `./canizzano.sh tutto`. Ricordalo a fine lavoro.

Quando hai finito, riassumi in due righe che cosa hai cambiato e con quali slug.
"""
