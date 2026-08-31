"""
Popola il CMS con i contenuti reali di Canizzano.

I dati vengono dall'handoff di design: le sei realta' del quartiere, gli
appuntamenti della Pro Loco e il programma completo di «Canizzano in Festa»
2026 preso dalla locandina. Il comando e' idempotente: rilanciarlo aggiorna
i record esistenti senza duplicarli.
"""

from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from eventi.models import (
    Album, Articolo, Attivita, DettaglioArticolo, Edizione, Evento, Giornata, Icona,
    Identita, ImpostazioniSito, Luogo, Tono,
)

ANNO = 2026

ATTIVITA = [
    {
        "nome": "Pro Loco Cannetum",
        "sottotitolo": "A.R.C. Cannetum · Pro Loco di Canizzano",
        "descrizione_breve": "Sportizzando, il Processo alla Vecchia, «Ama il tuo quartiere» e la sagra d'ottobre.",
        "descrizione": (
            "La Pro Loco di Canizzano tiene insieme l'anno del quartiere: le feste, "
            "i mercatini, le serate in piazza e la sagra d'ottobre.\n\n"
            "Ottanta volontari, una tessera da dieci euro e l'assemblea il primo "
            "martedi' del mese: si entra quando si vuole."
        ),
        "identita": Identita.SALVIA,
        "icona": Icona.TENDONE,
        "tono": Tono.ACCENT,
        "collegamento": "/proloco",
        "etichetta_collegamento": "canizzano.it/proloco",
        "telefono": "328 2143250",
        "ordine": 1,
        "in_menu": True,
    },
    {
        "nome": "Parrocchia",
        "sottotitolo": "Visitazione della Beata Vergine Maria",
        "descrizione_breve": "Visitazione della Beata Vergine Maria: orari delle messe, catechismo, sacramenti, caritas.",
        "descrizione": "Gli appuntamenti della comunita' parrocchiale di Canizzano.",
        "identita": Identita.SALVIA,
        "icona": Icona.CHIESA,
        "tono": Tono.ACCENT_2_700,
        "collegamento": "https://www.parrocchiacanizzano.it",
        "etichetta_collegamento": "parrocchiacanizzano.it",
        "email": "canizzano@diocesitv.it",
        "telefono": "0422 379269",
        "ordine": 2,
        "in_menu": True,
    },
    {
        "nome": "Grest",
        "sottotitolo": "Canizzano sulle orme di San Francesco",
        "descrizione_breve": "Dal 15 giugno al 3 luglio, sulle orme di San Francesco: iscrizioni, animatori e foto.",
        "descrizione": (
            "Tre settimane di giochi, laboratori e uscite per bambini e ragazzi "
            "dalla prima elementare alla terza media, dalle 15.30 alle 18.30."
        ),
        "identita": Identita.TERRACOTTA,
        "icona": Icona.BAMBINI,
        "tono": Tono.ACCENT_400,
        "collegamento": "/grest",
        "etichetta_collegamento": "canizzano.it/grest",
        "email": "canizzano.grest2021@gmail.com",
        "ordine": 3,
        "in_menu": True,
    },
    {
        "nome": "Calcio",
        "sottotitolo": "Il campo dietro la chiesa",
        "descrizione_breve": "Il campo dietro la chiesa: squadre, allenamenti, risultati del weekend, iscrizioni.",
        "identita": Identita.SALVIA,
        "icona": Icona.PALLONE,
        "tono": Tono.ACCENT_2_500,
        "collegamento": "",
        "etichetta_collegamento": "canizzano.it/calcio",
        "ordine": 4,
    },
    {
        # Il NOI resta una realta' del quartiere con la sua scheda, ma in home
        # sta fra «gli altri»: il suo posto nella griglia va al Principato.
        "nome": "Circolo NOI",
        "sottotitolo": "Il bar del oratorio",
        "descrizione_breve": "Il bar del oratorio, la sala per le feste, il tesseramento e i tornei di carte.",
        "identita": Identita.NEUTRO,
        "icona": Icona.CASA,
        "tono": Tono.NEUTRAL_700,
        "collegamento": "",
        "etichetta_collegamento": "canizzano.it/noi",
        "ordine": 6,
        "in_home": False,
    },
    {
        "nome": "Principato di Canizzano",
        "sottotitolo": "Il canneto sullo stemma",
        "descrizione_breve": "Il soprannome del paese diventato insegna: lo stemma del canneto, le sue ricorrenze e il suo orgoglio.",
        "descrizione": (
            "«Principato di Canizzano» nasce come sfotto' cittadino e il quartiere "
            "se l'e' tenuto stretto: da qui lo stemma con le tre canne del "
            "cannetum e l'onda del Sile, lo stesso segno che porta il sito.\n\n"
            "E' una realta' a se': tiene vivo il modo di dire, la memoria del "
            "mezzo secolo da comune autonomo e le ricorrenze che ci girano attorno."
        ),
        "identita": Identita.SALVIA,
        "icona": Icona.CANNETO,
        "tono": Tono.ACCENT_2_600,
        "collegamento": "/storia#principato",
        "etichetta_collegamento": "la storia del Principato",
        "ordine": 5,
    },
    {
        "nome": "Coro, chierichetti e gli altri",
        "sottotitolo": "I gruppi piu' piccoli",
        "descrizione_breve": "Coro, chierichetti, Circolo NOI e gli altri gruppi: un referente e un numero di telefono ciascuno.",
        "identita": Identita.TERRACOTTA,
        "icona": Icona.PERSONE,
        "tono": Tono.ACCENT_200,
        "sfondo_caldo": True,
        "collegamento": "",
        "etichetta_collegamento": "canizzano.it/gruppi",
        "ordine": 7,
    },
    {
        "nome": "Sagra",
        "sottotitolo": "Canizzano in Festa",
        "descrizione_breve": "Dieci giorni di cucina, musica, giochi e momenti di comunita'.",
        "identita": Identita.TERRACOTTA,
        "icona": Icona.STELLA,
        "tono": Tono.ACCENT,
        "collegamento": "/sagra",
        "etichetta_collegamento": "canizzano.it/sagra",
        "telefono": "328 2143250",
        "ordine": 8,
        "in_home": False,
    },
]

LUOGHI = [
    {"nome": "Tendone della sagra", "indirizzo": "Via Canizzano 110, 31100 Treviso"},
    {"nome": "Chiesa della Visitazione", "indirizzo": "Via Canizzano, 31100 Treviso"},
    {"nome": "Oratorio di Canizzano", "indirizzo": "Via Canizzano, 31100 Treviso"},
    {"nome": "Sala del Circolo NOI", "indirizzo": "Via Canizzano, 31100 Treviso"},
    {"nome": "Riva del Sile", "indirizzo": "Parco naturale del fiume Sile, Treviso"},
]

# Programma reale di «Canizzano in Festa» 2026, dalla locandina.
# (giorno, ora, titolo, nota, categoria, icona, piatto, risalto, prenota entro, tono)
SAGRA = [
    (2, "19:00", "Apertura degli stand", "", "Cucina", Icona.POSATE, "", False, None, ""),
    (2, "20:45", "«Sulle orme di San Francesco»",
     "Rappresentazione degli animatori del Grest, poi proiezione dei video dei campi estivi e del Grest.",
     "Spettacolo", Icona.VIDEO, "", True, None, Tono.BLU_600),
    (3, "19:30", "Stand gastronomici", "Su prenotazione.", "Cucina", Icona.POSATE,
     "Tagliata di manzo con rucola", False, 1, ""),
    (3, "21:30", "Concerto degli Onde Beat", "", "Musica", Icona.MUSICA, "", False, None, ""),
    (4, "11:00", "«Pimpa e la ricetta golosa: a scuola di tiramisu'»",
     "Laboratorio per famiglie, gratuito su iscrizione.", "Bambini", Icona.PIMPA, "", False, None, ""),
    (4, "12:00", "Pranzo rustico", "Solo su prenotazione.", "Cucina", Icona.POSATE,
     "Pranzo rustico, ore 12.00", False, 2, ""),
    (4, "14:00", "Mostra di trattori d'epoca", "", "Mostra", Icona.STELLA, "", False, None, ""),
    (4, "19:30", "Stand gastronomici", "", "Cucina", Icona.POSATE,
     "Seppie in umido con polenta", False, 2, ""),
    (4, "20:00", "Flame SSDaRL & DanceEmotion",
     "Con N. Zuccarello e S. Bruttomesso. Ballo liscio e la novita' «Cumbia Step!».",
     "Spettacolo", Icona.MUSICA, "", False, None, ""),
    (9, "18:30", "Aperitivo dello sportivo", "", "Sport", Icona.PALLONE, "", False, None, ""),
    (9, "19:30", "Stand gastronomici", "", "Cucina", Icona.POSATE,
     "Panino caldo col pastin", False, None, ""),
    (9, "20:30", "Premiazione dei gruppi sportivi",
     "Con le Autorita', a seguire partita amichevole.", "Sport", Icona.PALLONE, "", False, None, ""),
    (9, "21:00", "Concerto dei Four Roxx Down", "«The first acoustic party band».",
     "Musica", Icona.MUSICA, "", False, None, ""),
    (10, "16:30", "«Pimpa e Olivia scoprono il Sile»",
     "Lettura in riva al Sile, merenda offerta.", "Bambini", Icona.PIMPA, "", False, None, ""),
    (10, "19:30", "Stand gastronomici", "", "Cucina", Icona.POSATE,
     "Paella alla Valenciana", False, 8, ""),
    (10, "21:00", "Giochi a quiz «Il Cervellone»", "A cura di Animarca Events.",
     "Giochi", Icona.GIOCO, "", False, None, ""),
    (11, "10:00", "Santa messa", "", "Comunita'", Icona.CROCE, "", False, None, ""),
    (11, "11:00", "Processione con la statua della Madonna", "", "Comunita'", Icona.CROCE, "", False, None, ""),
    (11, "12:00", "Pranzo comunitario", "Su prenotazione.", "Cucina", Icona.POSATE,
     "Pranzo comunitario, ore 12.00", False, 8, ""),
    (11, "18:00", "«Pimpa incontra El Massariol»",
     "Leggende trevigiane, gratuito, aperitivo offerto.", "Bambini", Icona.PIMPA, "", False, None, ""),
    (11, "19:30", "Stand gastronomici e giochi per tutte le eta'", "", "Cucina", Icona.POSATE, "", False, None, ""),
    (11, "21:00", "Concerto dei Rockin Riders", "Cover di Eagles e Creedence.",
     "Musica", Icona.MUSICA, "", False, None, ""),
    (11, "22:30", "Cerimonia di chiusura", "", "Comunita'", Icona.STELLA, "", False, None, ""),
]

# Le sei giornate della sagra: come si presenta la card di ogni giorno.
# (giorno di ottobre, occhiello, tono della pastiglia, fondo chiaro)
GIORNATE = [
    (2, "si apre il tendone", Tono.ACCENT, False),
    (3, "la prima serata di musica", Tono.ACCENT, False),
    (4, "la domenica dei bambini", Tono.ACCENT, False),
    (9, "il secondo weekend", Tono.ACCENT, False),
    (10, "sagra e giochi", Tono.ACCENT, False),
    (11, "la chiusura, con la processione", Tono.ACCENT_2_600, True),
]

# Appuntamenti della Pro Loco lungo l'anno.
# (mese, giorno, ora, titolo, sommario, categoria, icona, in_evidenza, etichetta, tono)
ANNO_PROLOCO = [
    (1, 6, "15:00", "Befana in piazza", "Calze per tutti i bambini e vin brule' per i grandi.",
     "Inverno", Icona.REGALO, False, "6 gennaio", ""),
    (2, 14, "20:30", "Carnevale del quartiere", "Sfilata di maschere e frittelle in oratorio.",
     "Inverno", Icona.STELLA, False, "febbraio", ""),
    (3, 14, "20:30", "Processo alla Vecchia",
     "Processo recitato in dialetto, sentenza, falo', vin brule' e frittelle.",
     "Inverno", Icona.FUOCO, True, "meta' quaresima", Tono.ACCENT_2_700),
    (5, 16, "15:00", "Sportizzando",
     "Tutti gli sport del quartiere da provare, con le societa' sportive presenti e la merenda.",
     "Primavera", Icona.PALLONE, True, "un sabato di maggio", Tono.ACCENT_2_600),
    (4, 25, "09:30", "Ama il tuo quartiere — iscrizioni",
     "Concorso per giardini, balconi e angoli curati: manda la foto entro fine aprile.",
     "Primavera", Icona.FOGLIA, False, "aprile → settembre", ""),
    (5, 30, "09:00", "Camminata lungo il Sile", "Sei chilometri fra golene e mulini, per tutti.",
     "Primavera", Icona.BICI, False, "maggio", ""),
    (6, 20, "21:15", "Cinema sotto le stelle", "Proiezione all'aperto nel campo del oratorio.",
     "Estate", Icona.STELLA, False, "giugno", ""),
    (7, 11, "19:00", "Gita fuori porta", "Una giornata in pullman, aperta a soci e famiglie.",
     "Estate", Icona.BICI, False, "luglio", ""),
    (9, 12, "18:00", "Ama il tuo quartiere — premiazione",
     "La giuria in bici ha finito il giro: premi sotto il tendone.",
     "Estate", Icona.FOGLIA, False, "settembre", ""),
    (11, 8, "15:00", "Castagnata", "Caldarroste e vin brule' davanti al oratorio.",
     "Autunno", Icona.FUOCO, False, "novembre", ""),
    (12, 5, "20:00", "Cena dei volontari", "Il grazie di fine anno a chi ha dato una mano.",
     "Autunno", Icona.PERSONE, False, "dicembre", ""),
]


# ── Le pagine di approfondimento ──────────────────────────────────────────
#
# Sono facoltative: un evento ne ha una solo quando c'e' qualcosa da
# spiegare. «Apertura degli stand» sta benissimo in una riga di programma;
# la gita e il concorso dei giardini no.
#
# `cerca` trova l'evento gia' in archivio (anche se in redazione e' stato
# scritto con un titolo un po' diverso); `evento` lo crea solo se manca.
ARTICOLI = [
    {
        "cerca": "cansiglio",
        "evento": {
            "titolo": "Gita sul Cansiglio",
            "sommario": "Un pullman, le faggete d’autunno e il pranzo in malga. Aperta a soci e famiglie.",
            "mese": 10, "giorno": 18, "ora": "07:00",
            "stagione": "autunno",
            "icona": Icona.MONTAGNA,
            "etichetta_data": "una domenica d’ottobre",
            "tono": Tono.ACCENT_2_600,
            "in_evidenza": True,
        },
        "occhiello": "La gita d’autunno",
        "titolo": "Una domenica sul Cansiglio",
        "sottotitolo": (
            "Il pullman parte dal piazzale della chiesa quando è ancora buio e "
            "torna che è ora di cena: in mezzo, la faggeta rossa, le malghe e "
            "una camminata che possono fare tutti."
        ),
        "corpo": (
            "Il Cansiglio è l’altopiano dietro le Prealpi trevigiane, un’ora e "
            "mezza di pullman da Canizzano. In ottobre la faggeta cambia colore "
            "tutta insieme: è il motivo per cui la gita si fa in questa "
            "domenica e non in un’altra.\n\n"
            "## Dove si va\n"
            "Si parte dal piazzale della chiesa, si sale per Vittorio Veneto e "
            "si lascia il pullman alla Pian Cansiglio. Da lì in poi si va a "
            "piedi: il giro del bosco del Cansiglio è un anello pianeggiante "
            "di circa sei chilometri, senza tratti esposti.\n\n"
            "## Come si cammina\n"
            "Con calma, e nessuno resta indietro: davanti c’è chi conosce il "
            "sentiero, in coda c’è sempre un volontario. Chi non se la sente "
            "di fare tutto l’anello può fermarsi al Museo dell’Uomo in "
            "Cansiglio e aspettare lì il gruppo.\n\n"
            "- il giro completo: sei chilometri, tre ore con le soste\n"
            "- il giro corto: due chilometri fino alle casere e ritorno\n"
            "- passeggini: solo sul tratto asfaltato vicino al piazzale\n\n"
            "## Il pranzo\n"
            "In malga, seduti, tutti insieme: formaggi dell’altopiano, un "
            "primo, un secondo e il dolce. Chi ha intolleranze o mangia "
            "vegetariano lo dice quando si iscrive, non il giorno prima.\n\n"
            "> Il posto in malga si tiene solo con l’iscrizione pagata: la "
            "malga vuole i numeri una settimana prima.\n\n"
            "## Cosa portare\n"
            "Scarpe chiuse con la suola scolpita — in ottobre il bosco è "
            "bagnato anche col sole — una giacca a vento, il cambio per i "
            "bambini e una borraccia. In quota ci sono sei o sette gradi meno "
            "che a Treviso: la felpa serve anche se qui si parte in maglietta.\n\n"
            "## Come ci si iscrive\n"
            "Al bar del oratorio nelle sere di apertura, oppure telefonando "
            "alla Pro Loco. I posti sono quelli del pullman: quando finiscono "
            "si apre la lista d’attesa, e negli ultimi anni è servita."
        ),
        "firma": "la Pro Loco Cannetum",
        "identita": Identita.SALVIA,
        "tono": Tono.ACCENT_2_700,
        "copertina_alt": "La faggeta del Cansiglio in autunno",
        "dettagli": [
            ("Quando", "una domenica d’ottobre, tutto il giorno"),
            ("Ritrovo", "ore 7.00, piazzale della chiesa"),
            ("Rientro", "verso le 19.00, stesso posto"),
            ("Camminata", "anello di 6 km, senza dislivelli"),
            ("Quota", "pullman + pranzo in malga, ridotta per i bambini"),
            ("Iscrizioni", "al bar del oratorio o al 328 2143250"),
        ],
    },
    {
        "cerca": "ama il tuo quartiere",
        "occhiello": "Il concorso dei giardini",
        "titolo": "Ama il tuo quartiere",
        "sottotitolo": (
            "Da aprile a settembre: mandi la foto del tuo balcone, la giuria "
            "gira Canizzano in bicicletta e la premiazione si fa sotto il "
            "tendone della sagra."
        ),
        "corpo": (
            "Non è un concorso di giardinaggio: è un modo per accorgersi di "
            "quanta cura c’è già in giro per Canizzano. Un davanzale tenuto "
            "bene conta quanto un giardino grande.\n\n"
            "## Chi può partecipare\n"
            "Chiunque abiti a Canizzano, socio o no, gratis. Partecipano anche "
            "i condomini, con l’accordo dell’amministratore, e gli angoli di "
            "strada adottati da chi ci passa davanti tutti i giorni.\n\n"
            "## Le categorie\n"
            "- balconi e davanzali\n"
            "- giardini e cortili\n"
            "- angoli comuni: aiuole di strada, ingressi di condominio, capitelli\n\n"
            "## Come si manda la foto\n"
            "Una foto sola, fatta col telefono, con nome e indirizzo. Si manda "
            "per email alla Pro Loco entro fine aprile. La foto serve a "
            "iscriversi, non a vincere: la giuria guarda dal vivo.\n\n"
            "## La giuria in bicicletta\n"
            "Fra fine agosto e i primi di settembre tre giurati fanno il giro "
            "del quartiere in bici, con la lista in mano. Guardano da fuori, "
            "dalla strada, senza entrare in casa di nessuno e senza "
            "avvisare — così si vede come sta un giardino in un giorno "
            "qualsiasi, non nel giorno della visita.\n\n"
            "> Chi vince un anno resta fuori concorso quello dopo: è un modo "
            "per far girare i premi.\n\n"
            "## I premi\n"
            "Una targa e le piante offerte dai vivai della zona, consegnate "
            "sotto il tendone durante la sagra d’ottobre, davanti a tutti."
        ),
        "firma": "la Pro Loco Cannetum",
        "identita": Identita.SALVIA,
        "tono": Tono.ACCENT_2_600,
        "copertina_alt": "Un balcone fiorito a Canizzano",
        "dettagli": [
            ("Iscrizioni", "entro fine aprile, gratuite"),
            ("Come", "una foto per email a proloco@canizzano.it"),
            ("Categorie", "balconi, giardini, angoli comuni"),
            ("Giuria", "in bicicletta, fra fine agosto e settembre"),
            ("Premiazione", "sotto il tendone della sagra"),
        ],
    },
]

# ── L’archivio storico ────────────────────────────────────────────────────
#
# Bozza: gli album ci sono, le foto no. Sull’hosting condiviso lo spazio e'
# poco, quindi le foto d’archivio non si caricano qui: si mettono su un
# servizio esterno e in redazione si incolla il link (Foto.url_esterna) o
# l’indirizzo dell’album intero (Album.album_url).
ALBUM = [
    {
        "titolo": "Le sagre di una volta",
        "periodo": "anni ’70 e ’80",
        "anno": 1978,
        "descrizione": (
            "Il tendone montato a mano, le pentole grandi come vasche, i "
            "tavoli di legno prestati dalle famiglie. Le foto arrivano dai "
            "cassetti del quartiere: se ne hai altre, portale in sala NOI."
        ),
        "ordine": 1,
    },
    {
        "titolo": "I mulini sul Sile",
        "periodo": "primo Novecento",
        "anno": 1930,
        "descrizione": (
            "Il Granello e gli altri mulini prima che si fermassero: ruote, "
            "chiuse, carri di sacchi. Immagini raccolte con la parrocchia."
        ),
        "ordine": 2,
    },
    {
        "titolo": "La squadra e il campo",
        "periodo": "anni ’60 → oggi",
        "anno": 1962,
        "descrizione": (
            "Dalla palude bonificata alle formazioni in posa: mezzo secolo di "
            "domeniche sul campo dietro l’abside."
        ),
        "ordine": 3,
    },
]


def istante(anno: int, mese: int, giorno: int, ora: str):
    """Datetime consapevole del fuso, dall'ora in formato «HH:MM»."""
    ore, minuti = (int(parte) for parte in ora.split(":"))
    return timezone.make_aware(datetime(anno, mese, giorno, ore, minuti))


class Command(BaseCommand):
    help = "Inserisce le realta' del quartiere e il programma reale 2026 (idempotente)."

    def handle(self, *args, **options):
        for dati in ATTIVITA:
            Attivita.objects.update_or_create(nome=dati["nome"], defaults=dati)
        for dati in LUOGHI:
            Luogo.objects.update_or_create(nome=dati["nome"], defaults=dati)

        proloco = Attivita.objects.get(nome="Pro Loco Cannetum")
        sagra = Attivita.objects.get(nome="Sagra")
        tendone = Luogo.objects.get(nome="Tendone della sagra")

        edizione_sagra, _ = Edizione.objects.update_or_create(
            attivita=sagra,
            anno=ANNO,
            defaults={
                "titolo": "Canizzano in Festa 2026",
                "descrizione": "Dieci giorni di cucina, musica e comunita' sotto il tendone.",
            },
        )
        edizione_proloco, _ = Edizione.objects.update_or_create(
            attivita=proloco,
            anno=ANNO,
            defaults={"titolo": f"Pro Loco Cannetum {ANNO}"},
        )

        for giorno, occhiello, tono, chiaro in GIORNATE:
            Giornata.objects.update_or_create(
                edizione=edizione_sagra,
                data=date(ANNO, 10, giorno),
                defaults={"occhiello": occhiello, "tono": tono, "sfondo_chiaro": chiaro},
            )

        for indice, (giorno, ora, titolo, nota, categoria, icona,
                     piatto, risalto, prenota, tono) in enumerate(SAGRA):
            Evento.objects.update_or_create(
                titolo=titolo,
                attivita=sagra,
                inizio=istante(ANNO, 10, giorno, ora),
                defaults={
                    "edizione": edizione_sagra,
                    "sommario": nota,
                    "categoria": categoria,
                    "icona": icona,
                    "tono": tono,
                    "piatto_del_giorno": piatto,
                    "risalto": risalto,
                    "prenotazione_entro": date(ANNO, 10, prenota) if prenota else None,
                    "luogo": tendone,
                    "ingresso": "Ingresso libero",
                    "ordine": indice,
                },
            )

        for (mese, giorno, ora, titolo, sommario, stagione, icona,
             evidenza, etichetta, tono) in ANNO_PROLOCO:
            Evento.objects.update_or_create(
                titolo=titolo,
                attivita=proloco,
                defaults={
                    "edizione": edizione_proloco,
                    "sommario": sommario,
                    "categoria": "",
                    "stagione_scelta": stagione.lower(),
                    "icona": icona,
                    "inizio": istante(ANNO, mese, giorno, ora),
                    "in_evidenza": evidenza,
                    "etichetta_data": etichetta,
                    "tono": tono,
                    "luogo": Luogo.objects.get(nome="Sala del Circolo NOI"),
                },
            )

        # L'apertura della sagra e' anche l'appuntamento in evidenza in home.
        Evento.objects.filter(attivita=sagra, titolo="Apertura degli stand").update(in_evidenza=True)

        self.crea_articoli(proloco, edizione_proloco)
        self.crea_album()

        impostazioni = ImpostazioniSito.caricate()
        impostazioni.data_inizio_sagra = istante(ANNO, 10, 2, "19:00")
        impostazioni.banner_testo = (
            "Dieci giorni di cucina, musica, giochi e momenti di comunita'. "
            "Prenotazioni cene dal 20 settembre."
        )
        impostazioni.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Inseriti: {Attivita.objects.count()} realta', "
                f"{Evento.objects.count()} eventi, {Luogo.objects.count()} luoghi, "
                f"{Articolo.objects.count()} articoli, {Album.objects.count()} album."
            )
        )

    def crea_articoli(self, proloco: Attivita, edizione: Edizione) -> None:
        """
        Attacca le pagine di approfondimento agli eventi che le meritano.

        L'evento viene prima cercato fra quelli gia' in archivio — anche se
        in redazione e' stato scritto con un titolo leggermente diverso — e
        creato solo se non c'e': cosi' il comando non duplica il lavoro
        fatto a mano nell'admin.
        """
        for dati in ARTICOLI:
            evento = Evento.objects.filter(titolo__icontains=dati["cerca"]).first()

            if evento is None:
                nuovo = dati.get("evento")
                if nuovo is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  · nessun evento per «{dati['cerca']}»: articolo saltato."
                        )
                    )
                    continue
                evento = Evento.objects.create(
                    attivita=proloco,
                    edizione=edizione,
                    titolo=nuovo["titolo"],
                    sommario=nuovo["sommario"],
                    inizio=istante(ANNO, nuovo["mese"], nuovo["giorno"], nuovo["ora"]),
                    stagione_scelta=nuovo["stagione"],
                    icona=nuovo["icona"],
                    etichetta_data=nuovo["etichetta_data"],
                    tono=nuovo["tono"],
                    in_evidenza=nuovo["in_evidenza"],
                )

            articolo, _ = Articolo.objects.update_or_create(
                evento=evento,
                defaults={
                    "occhiello": dati["occhiello"],
                    "titolo": dati["titolo"],
                    "sottotitolo": dati["sottotitolo"],
                    "corpo": dati["corpo"],
                    "firma": dati["firma"],
                    "identita": dati["identita"],
                    "tono": dati["tono"],
                    "copertina_alt": dati["copertina_alt"],
                    "data_pubblicazione": date(ANNO, 1, 15),
                },
            )
            articolo.dettagli.all().delete()
            DettaglioArticolo.objects.bulk_create(
                DettaglioArticolo(articolo=articolo, etichetta=etichetta, valore=valore, ordine=indice)
                for indice, (etichetta, valore) in enumerate(dati["dettagli"])
            )

    def crea_album(self) -> None:
        """
        Le raccolte dell'archivio storico, ancora senza foto.

        Le immagini d'archivio non stanno sull'hosting: si caricano su un
        servizio esterno e in redazione si incolla il link. Finche' non
        arrivano, la pagina mostra gli album come «in preparazione».
        """
        for dati in ALBUM:
            Album.objects.update_or_create(titolo=dati["titolo"], defaults=dati)
