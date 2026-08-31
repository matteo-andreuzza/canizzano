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
    Attivita, Edizione, Evento, Giornata, Icona, Identita, ImpostazioniSito, Luogo, Tono,
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
        "nome": "Circolo NOI",
        "sottotitolo": "Il bar del patronato",
        "descrizione_breve": "Il bar del patronato, la sala per le feste, il tesseramento e i tornei di carte.",
        "identita": Identita.NEUTRO,
        "icona": Icona.CASA,
        "tono": Tono.NEUTRAL_700,
        "collegamento": "",
        "etichetta_collegamento": "canizzano.it/noi",
        "ordine": 5,
    },
    {
        "nome": "Coro, chierichetti e gli altri",
        "sottotitolo": "I gruppi piu' piccoli",
        "descrizione_breve": "I gruppi piu' piccoli, con un referente e un numero di telefono ciascuno.",
        "identita": Identita.TERRACOTTA,
        "icona": Icona.PERSONE,
        "tono": Tono.ACCENT_200,
        "sfondo_caldo": True,
        "collegamento": "",
        "etichetta_collegamento": "canizzano.it/gruppi",
        "ordine": 6,
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
        "ordine": 7,
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
# (giorno, ora, titolo, nota, categoria, icona, piatto, risalto, prenota entro)
SAGRA = [
    (2, "19:00", "Apertura degli stand", "", "Cucina", Icona.CUCINA, "", False, None),
    (2, "20:45", "«Sulle orme di San Francesco»",
     "Rappresentazione degli animatori del Grest, poi proiezione dei video dei campi estivi e del Grest.",
     "Spettacolo", Icona.STELLA, "", True, None),
    (3, "19:30", "Stand gastronomici", "Su prenotazione.", "Cucina", Icona.CUCINA,
     "Tagliata di manzo con rucola", False, 1),
    (3, "21:30", "Concerto degli Onde Beat", "", "Musica", Icona.MUSICA, "", False, None),
    (4, "11:00", "«Pimpa e la ricetta golosa: a scuola di tiramisu'»",
     "Laboratorio per famiglie, gratuito su iscrizione.", "Bambini", Icona.PENNELLO, "", False, None),
    (4, "12:00", "Pranzo rustico", "Solo su prenotazione.", "Cucina", Icona.CUCINA,
     "Pranzo rustico, ore 12.00", False, 2),
    (4, "14:00", "Mostra di trattori d'epoca", "", "Mostra", Icona.STELLA, "", False, None),
    (4, "19:30", "Stand gastronomici", "", "Cucina", Icona.CUCINA,
     "Seppie in umido con polenta", False, 2),
    (4, "20:00", "Flame SSDaRL & DanceEmotion",
     "Con N. Zuccarello e S. Bruttomesso. Ballo liscio e la novita' «Cumbia Step!».",
     "Spettacolo", Icona.MUSICA, "", False, None),
    (9, "18:30", "Aperitivo dello sportivo", "", "Sport", Icona.PALLONE, "", False, None),
    (9, "19:30", "Stand gastronomici", "", "Cucina", Icona.CUCINA,
     "Panino caldo col pastin", False, None),
    (9, "20:30", "Premiazione dei gruppi sportivi",
     "Con le Autorita', a seguire partita amichevole.", "Sport", Icona.PALLONE, "", False, None),
    (9, "21:00", "Concerto dei Four Roxx Down", "«The first acoustic party band».",
     "Musica", Icona.MUSICA, "", False, None),
    (10, "16:30", "«Pimpa e Olivia scoprono il Sile»",
     "Lettura in riva al Sile, merenda offerta.", "Bambini", Icona.FIUME, "", False, None),
    (10, "19:30", "Stand gastronomici", "", "Cucina", Icona.CUCINA,
     "Paella alla Valenciana", False, 8),
    (10, "21:00", "Giochi a quiz «Il Cervellone»", "A cura di Animarca Events.",
     "Giochi", Icona.GIOCO, "", False, None),
    (11, "10:00", "Santa messa", "", "Comunita'", Icona.CHIESA, "", False, None),
    (11, "11:00", "Processione con la statua della Madonna", "", "Comunita'", Icona.CHIESA, "", False, None),
    (11, "12:00", "Pranzo comunitario", "Su prenotazione.", "Cucina", Icona.CUCINA,
     "Pranzo comunitario, ore 12.00", False, 8),
    (11, "18:00", "«Pimpa incontra El Massariol»",
     "Leggende trevigiane, gratuito, aperitivo offerto.", "Bambini", Icona.LIBRO, "", False, None),
    (11, "19:30", "Stand gastronomici e giochi per tutte le eta'", "", "Cucina", Icona.CUCINA, "", False, None),
    (11, "21:00", "Concerto dei Rockin Riders", "Cover di Eagles e Creedence.",
     "Musica", Icona.MUSICA, "", False, None),
    (11, "22:30", "Cerimonia di chiusura", "", "Comunita'", Icona.STELLA, "", False, None),
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
    (2, 14, "20:30", "Carnevale del quartiere", "Sfilata di maschere e frittelle in patronato.",
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
    (6, 20, "21:15", "Cinema sotto le stelle", "Proiezione all'aperto nel campo del patronato.",
     "Estate", Icona.STELLA, False, "giugno", ""),
    (7, 11, "19:00", "Gita fuori porta", "Una giornata in pullman, aperta a soci e famiglie.",
     "Estate", Icona.BICI, False, "luglio", ""),
    (9, 12, "18:00", "Ama il tuo quartiere — premiazione",
     "La giuria in bici ha finito il giro: premi sotto il tendone.",
     "Estate", Icona.FOGLIA, False, "settembre", ""),
    (11, 8, "15:00", "Castagnata", "Caldarroste e vin brule' davanti al patronato.",
     "Autunno", Icona.FUOCO, False, "novembre", ""),
    (12, 5, "20:00", "Cena dei volontari", "Il grazie di fine anno a chi ha dato una mano.",
     "Autunno", Icona.PERSONE, False, "dicembre", ""),
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
                     piatto, risalto, prenota) in enumerate(SAGRA):
            Evento.objects.update_or_create(
                titolo=titolo,
                attivita=sagra,
                inizio=istante(ANNO, 10, giorno, ora),
                defaults={
                    "edizione": edizione_sagra,
                    "sommario": nota,
                    "categoria": categoria,
                    "icona": icona,
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
                f"{Evento.objects.count()} eventi, {Luogo.objects.count()} luoghi."
            )
        )
