"""
Modello dei contenuti dinamici di canizzano.it.

Tutto cio' che il quartiere deve poter cambiare senza toccare il codice:

* ``ImpostazioniSito`` — gli interruttori delle sezioni (banner sagra,
  conto alla rovescia, iscrizioni al Grest aperte…).
* ``Attivita``  — la realta' del quartiere (Pro Loco, Sagra, Parrocchia,
  Grest, Calcio, Circolo NOI): guida colori, icona e card della home.
* ``Edizione``  — l'annata di un'attivita' (es. «Pro Loco 2026»).
* ``Evento``    — il singolo appuntamento: alimenta i «prossimi
  appuntamenti» della home, il programma della sagra e l'anno Pro Loco.
* ``Articolo``  — la pagina di approfondimento di un evento, facoltativa:
  l'«articolo di giornale» con corpo, dettagli pratici e foto.
* ``Album``     — una raccolta dell'archivio storico del quartiere.
* ``Foto``      — le raccolte fotografiche delle pagine, degli articoli e
  dell'archivio; l'immagine può stare qui o su un servizio esterno.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Identita(models.TextChoices):
    """Le due voci cromatiche del sistema Organic, piu' il neutro."""

    TERRACOTTA = "terracotta", "Terracotta (sagra)"
    SALVIA = "salvia", "Salvia (Pro Loco, quartiere)"
    NEUTRO = "neutro", "Neutro"


class Tono(models.TextChoices):
    """
    Tinta del disco che porta l'icona di una realta'.

    Sono i token del sistema Organic: la home alterna volutamente tinte
    diverse fra le sei card, quindi il tono e' scelto in redazione e non
    dedotto dall'identita' cromatica.
    """

    ACCENT = "accent", "Terracotta piena"
    ACCENT_200 = "accent-200", "Terracotta chiarissima"
    ACCENT_300 = "accent-300", "Terracotta chiara"
    ACCENT_400 = "accent-400", "Terracotta media"
    ACCENT_2_100 = "accent-2-100", "Salvia chiarissima"
    ACCENT_2_500 = "accent-2-500", "Salvia media"
    ACCENT_2_600 = "accent-2-600", "Salvia"
    ACCENT_2_700 = "accent-2-700", "Salvia scura"
    BLU_200 = "blu-200", "Azzurrino chiarissimo"
    BLU_300 = "blu-300", "Azzurrino chiaro"
    BLU_600 = "blu-600", "Azzurro-blu"
    BLU_700 = "blu-700", "Blu scuro"
    NEUTRAL_100 = "neutral-100", "Neutro chiaro"
    NEUTRAL_700 = "neutral-700", "Neutro scuro"


class Stagione(models.TextChoices):
    """Le quattro colonne del calendario della Pro Loco."""

    INVERNO = "inverno", "Inverno"
    PRIMAVERA = "primavera", "Primavera"
    ESTATE = "estate", "Estate"
    AUTUNNO = "autunno", "Autunno"


class Icona(models.TextChoices):
    """Icone Lucide disponibili nel sito (vedi ``components/Icona.astro``)."""

    TENDONE = "tendone", "Tendone / sagra"
    CHIESA = "chiesa", "Chiesa"
    BAMBINI = "bambini", "Bambini / Grest"
    PALLONE = "pallone", "Pallone / sport"
    CASA = "casa", "Casa / circolo"
    PERSONE = "persone", "Persone / gruppi"
    MUSICA = "musica", "Musica"
    CUCINA = "cucina", "Cucina / piatto"
    CALENDARIO = "calendario", "Calendario"
    OROLOGIO = "orologio", "Orologio"
    LUOGO = "luogo", "Luogo / mappa"
    FOGLIA = "foglia", "Foglia / natura"
    FIUME = "fiume", "Fiume / Sile"
    STELLA = "stella", "Stella / festa"
    REGALO = "regalo", "Regalo / premi"
    FUOCO = "fuoco", "Fuoco / falo'"
    LIBRO = "libro", "Libro / racconto"
    PENNELLO = "pennello", "Pennello / laboratori"
    GIOCO = "gioco", "Gioco"
    BICI = "bici", "Bici / gite"
    POSATE = "posate", "Posate / stand gastronomico"
    VIDEO = "video", "Video / cinema / proiezione"
    PIMPA = "pimpa", "Pimpa / il cagnolino a pois"
    CROCE = "croce", "Croce cristiana / messa"
    CANNETO = "canneto", "Canneto / Principato di Canizzano"
    MONTAGNA = "montagna", "Montagna / gita fuori porta"
    FOTOGRAFIA = "fotografia", "Fotografia / archivio"


class Pubblicati(models.Manager):
    """Restituisce solo i record visibili sul sito pubblico."""

    def get_queryset(self):
        return super().get_queryset().filter(pubblicato=True)


class ModelloConSlug(models.Model):
    """Base per i modelli che espongono uno slug stabile alle rotte Astro."""

    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        help_text="Lasciare vuoto per generarlo dal nome.",
    )
    pubblicato = models.BooleanField(
        default=True,
        help_text="Se disattivato il contenuto sparisce dal prossimo build del sito.",
    )
    creato_il = models.DateTimeField(auto_now_add=True)
    aggiornato_il = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    visibili = Pubblicati()

    class Meta:
        abstract = True

    def campo_sorgente_slug(self) -> str:
        raise NotImplementedError

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.campo_sorgente_slug())[:110] or "voce"
            candidato, contatore = base, 2
            esistenti = type(self).objects.exclude(pk=self.pk)
            while esistenti.filter(slug=candidato).exists():
                candidato = f"{base}-{contatore}"
                contatore += 1
            self.slug = candidato
        super().save(*args, **kwargs)


class ImpostazioniSito(models.Model):
    """
    Gli interruttori delle sezioni condizionali del sito.

    E' un record unico (singleton): l'admin non permette di crearne altri.
    Ogni campo corrisponde a una prop dei prototipi di design.
    """

    # --- Home ---------------------------------------------------------------
    # La fascia terracotta in cima alla home: non e' legata alla sagra, e' lo
    # spazio dell'appuntamento piu' imminente (sagra, iscrizioni al Grest, al
    # catechismo...). La redazione ne scrive testo e destinazione.
    mostra_banner_sagra = models.BooleanField(
        default=True, verbose_name="mostra il banner in home"
    )
    banner_occhiello = models.CharField(
        max_length=60,
        default="Sta arrivando",
        blank=True,
        verbose_name="occhiello",
        help_text="La riga piccola sopra il titolo: «Sta arrivando», «Iscrizioni aperte»…",
    )
    banner_titolo = models.CharField(
        max_length=160,
        default="Canizzano in Festa · 2 → 11 ottobre",
        blank=True,
        verbose_name="titolo",
        help_text="Se resta vuoto il banner non compare, anche se acceso.",
    )
    banner_testo = models.CharField(
        max_length=280,
        blank=True,
        verbose_name="testo",
        help_text="Una riga di dettaglio sotto il titolo. Facoltativa.",
    )
    banner_collegamento = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="collegamento del bottone",
        help_text=(
            "Dove porta il bottone: un indirizzo del sito (/grest, /calendario, "
            "/eventi/<slug>) oppure un link esterno completo di https://. "
            "Se resta vuoto porta alla pagina della sagra."
        ),
    )
    banner_etichetta_bottone = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="testo del bottone",
        help_text="Se resta vuoto il bottone dice «Vai al programma».",
    )

    # --- Sagra --------------------------------------------------------------
    modalita_sagra = models.BooleanField(
        default=False,
        verbose_name="modalita' sagra",
        help_text="Da settembre a fine ottobre: /proloco rimanda alla pagina della sagra.",
    )
    data_inizio_sagra = models.DateTimeField(
        null=True, blank=True, help_text="Usata dal conto alla rovescia."
    )
    mostra_conto_rovescia = models.BooleanField(default=True)
    mostra_sponsor = models.BooleanField(default=True)

    # --- Pro Loco -----------------------------------------------------------
    mostra_galleria_proloco = models.BooleanField(default=True)

    # --- Grest --------------------------------------------------------------
    iscrizioni_grest_aperte = models.BooleanField(default=True)
    mostra_foto_grest = models.BooleanField(default=True)

    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "impostazioni del sito"
        verbose_name_plural = "impostazioni del sito"

    def __str__(self) -> str:
        return "Impostazioni del sito"

    def clean(self):
        if not self.pk and ImpostazioniSito.objects.exists():
            raise ValidationError("Esiste gia' un record di impostazioni: modifica quello.")

    def save(self, *args, **kwargs):
        # Un solo record, sempre con la stessa chiave primaria.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def caricate(cls) -> "ImpostazioniSito":
        record, _ = cls.objects.get_or_create(pk=1)
        return record


class Attivita(ModelloConSlug):
    """Una realta' del quartiere: pagina dedicata e card in home."""

    nome = models.CharField(max_length=120)
    sottotitolo = models.CharField(max_length=200, blank=True)
    descrizione = models.TextField(
        blank=True, help_text="Testo introduttivo. Una riga vuota separa i paragrafi."
    )
    descrizione_breve = models.CharField(
        max_length=280, blank=True, help_text="Riga mostrata nella card della home."
    )
    identita = models.CharField(
        max_length=12,
        choices=Identita.choices,
        default=Identita.SALVIA,
        help_text="Colore con cui la realta' compare in tag, pastiglie e dischi.",
    )
    icona = models.CharField(max_length=20, choices=Icona.choices, default=Icona.PERSONE)
    tono = models.CharField(
        max_length=14,
        choices=Tono.choices,
        default=Tono.ACCENT_2_700,
        help_text="Tinta del disco che porta l'icona nella card della home.",
    )
    sfondo_caldo = models.BooleanField(
        default=False,
        help_text="Card su fondo crema («surface») invece del neutro chiaro.",
    )
    collegamento = models.CharField(
        max_length=200,
        blank=True,
        help_text="Pagina interna (es. «/proloco») o indirizzo esterno completo.",
    )
    etichetta_collegamento = models.CharField(
        max_length=80, blank=True, help_text="Testo della freccia, es. «canizzano.it/proloco»."
    )
    immagine = models.ImageField(upload_to="attivita/", blank=True)
    immagine_alt = models.CharField(
        max_length=200, blank=True, help_text="Descrizione dell'immagine per screen reader."
    )
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    ordine = models.PositiveSmallIntegerField(
        default=0, help_text="Ordine di comparsa in home e nel menu (crescente)."
    )
    in_menu = models.BooleanField(default=False, help_text="Mostra la voce nel menu di navigazione.")
    in_home = models.BooleanField(
        default=True, help_text="Mostra la card in «Chi tiene in piedi il quartiere»."
    )

    class Meta:
        verbose_name = "attivita"
        verbose_name_plural = "attivita"
        ordering = ("ordine", "nome")

    def __str__(self) -> str:
        return self.nome

    def campo_sorgente_slug(self) -> str:
        return self.nome

    @property
    def esterno(self) -> bool:
        return self.collegamento.startswith("http")


class Luogo(models.Model):
    """Sede ricorrente degli eventi, cosi' non va riscritta ogni volta."""

    nome = models.CharField(max_length=120, unique=True)
    indirizzo = models.CharField(max_length=200, blank=True)
    mappa_url = models.URLField(blank=True, help_text="Link a Google Maps o OpenStreetMap.")

    class Meta:
        verbose_name = "luogo"
        verbose_name_plural = "luoghi"
        ordering = ("nome",)

    def __str__(self) -> str:
        return self.nome


class Edizione(ModelloConSlug):
    """Annata di un'attivita': raccoglie il programma di un anno."""

    attivita = models.ForeignKey(Attivita, on_delete=models.CASCADE, related_name="edizioni")
    anno = models.PositiveSmallIntegerField()
    titolo = models.CharField(
        max_length=160, blank=True, help_text="Se vuoto viene usato «Nome attivita' + anno»."
    )
    descrizione = models.TextField(blank=True)
    immagine = models.ImageField(upload_to="edizioni/", blank=True)
    immagine_alt = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "edizione"
        verbose_name_plural = "edizioni"
        ordering = ("-anno", "attivita__nome")
        unique_together = ("attivita", "anno")

    def __str__(self) -> str:
        return self.etichetta

    @property
    def etichetta(self) -> str:
        return self.titolo or f"{self.attivita.nome} {self.anno}"

    def campo_sorgente_slug(self) -> str:
        return f"{self.attivita.nome}-{self.anno}"


class Evento(ModelloConSlug):
    """
    Un appuntamento del quartiere.

    Lo stesso record serve tre viste diverse: la card dei «prossimi
    appuntamenti» in home, la riga oraria del programma della sagra e la
    colonna stagionale dell'anno Pro Loco.
    """

    attivita = models.ForeignKey(Attivita, on_delete=models.CASCADE, related_name="eventi")
    edizione = models.ForeignKey(
        Edizione,
        on_delete=models.SET_NULL,
        related_name="eventi",
        null=True,
        blank=True,
        help_text="Facoltativo: lega l'evento al programma di un'annata.",
    )
    titolo = models.CharField(max_length=160)
    sommario = models.CharField(
        max_length=280, blank=True, help_text="Una o due righe, usate nelle card di anteprima."
    )
    descrizione = models.TextField(blank=True)
    categoria = models.CharField(
        max_length=60, blank=True, help_text="Etichetta breve: «Musica», «Cucina», «Bambini»…"
    )
    icona = models.CharField(max_length=20, choices=Icona.choices, blank=True)

    inizio = models.DateTimeField()
    fine = models.DateTimeField(null=True, blank=True)
    tutto_il_giorno = models.BooleanField(
        default=False, help_text="Nasconde l'orario nelle date mostrate sul sito."
    )
    etichetta_data = models.CharField(
        max_length=60,
        blank=True,
        help_text=(
            "Come si scrive la data sul sito quando non e' un giorno preciso: "
            "«meta' quaresima», «aprile → settembre», «un sabato di maggio». "
            "Se vuoto viene composta dalla data qui sopra."
        ),
    )
    tono = models.CharField(
        max_length=14,
        choices=Tono.choices,
        blank=True,
        help_text="Tinta della card nel calendario stagionale. Vuoto = card crema.",
    )
    stagione_scelta = models.CharField(
        max_length=10,
        choices=Stagione.choices,
        blank=True,
        verbose_name="stagione",
        help_text=(
            "In quale colonna del calendario finisce. Se vuoto viene dedotta dal "
            "mese: serve quando la festa sta in un'altra stagione di quella del "
            "calendario (il Processo alla Vecchia e' di marzo ma e' d'inverno)."
        ),
    )

    luogo = models.ForeignKey(
        Luogo, on_delete=models.SET_NULL, related_name="eventi", null=True, blank=True
    )
    luogo_libero = models.CharField(
        max_length=160, blank=True, help_text="Sede occasionale, se non presente fra i luoghi."
    )

    immagine = models.ImageField(upload_to="eventi/", blank=True)
    immagine_alt = models.CharField(max_length=200, blank=True)

    piatto_del_giorno = models.CharField(
        max_length=160,
        blank=True,
        help_text="Il piatto messo in risalto nel programma della sagra.",
    )
    ingresso = models.CharField(
        max_length=120, blank=True, help_text="Es. «Ingresso libero», «Offerta libera», «5 €»."
    )
    prenotazione_entro = models.DateField(
        null=True, blank=True, help_text="Termine per le prenotazioni, se previste."
    )
    link = models.URLField(blank=True, help_text="Locandina, iscrizioni o pagina esterna.")
    link_etichetta = models.CharField(max_length=60, blank=True, default="Scopri di più")

    in_evidenza = models.BooleanField(
        default=False, help_text="Compare fra i «prossimi appuntamenti» in home."
    )
    risalto = models.BooleanField(
        default=False,
        help_text="Nel programma della sagra diventa un blocco colorato a tutta larghezza.",
    )
    ordine = models.SmallIntegerField(
        default=0, help_text="A parita' di orario decide chi viene prima."
    )

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventi"
        ordering = ("inizio", "ordine", "titolo")
        indexes = [
            models.Index(fields=("inizio",)),
            models.Index(fields=("pubblicato", "inizio")),
        ]

    def __str__(self) -> str:
        return f"{self.titolo} — {timezone.localtime(self.inizio):%d/%m/%Y}"

    def campo_sorgente_slug(self) -> str:
        return f"{self.titolo}-{timezone.localtime(self.inizio):%Y-%m-%d}"

    @property
    def dove(self) -> str:
        return self.luogo_libero or (self.luogo.nome if self.luogo else "")

    @property
    def concluso(self) -> bool:
        return (self.fine or self.inizio) < timezone.now()

    @property
    def stagione(self) -> str:
        """Colonna stagionale della pagina «Pro Loco tutto l'anno»."""
        if self.stagione_scelta:
            return self.stagione_scelta
        mese = timezone.localtime(self.inizio).month
        if mese in (12, 1, 2):
            return "inverno"
        if mese in (3, 4, 5):
            return "primavera"
        if mese in (6, 7, 8):
            return "estate"
        return "autunno"


class Giornata(models.Model):
    """
    Una giornata del programma della sagra.

    Gli orari stanno gia' negli eventi: qui si decide come si presenta la
    card del giorno — il titolo, la riga di richiamo e il colore della
    pastiglia (l'ultima domenica, per esempio, e' salvia e non terracotta).
    """

    edizione = models.ForeignKey(Edizione, on_delete=models.CASCADE, related_name="giornate")
    data = models.DateField()
    titolo = models.CharField(
        max_length=120, blank=True, help_text="Se vuoto viene composto dalla data («Venerdì 2 ottobre»)."
    )
    occhiello = models.CharField(
        max_length=80, blank=True, help_text="La riga sopra il titolo: «si apre il tendone»."
    )
    tono = models.CharField(
        max_length=14,
        choices=Tono.choices,
        default=Tono.ACCENT,
        help_text="Tinta della pastiglia con la data.",
    )
    sfondo_chiaro = models.BooleanField(
        default=False, help_text="Card su fondo neutro chiaro invece che crema."
    )
    pubblicato = models.BooleanField(default=True)

    objects = models.Manager()
    visibili = Pubblicati()

    class Meta:
        verbose_name = "giornata"
        verbose_name_plural = "giornate"
        ordering = ("data",)
        unique_together = ("edizione", "data")

    def __str__(self) -> str:
        return self.etichetta

    @property
    def etichetta(self) -> str:
        if self.titolo:
            return self.titolo
        giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        mesi = [
            "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
            "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
        ]
        return f"{giorni[self.data.weekday()]} {self.data.day} {mesi[self.data.month - 1]}"


class Articolo(ModelloConSlug):
    """
    La pagina di approfondimento di un evento — facoltativa.

    Non tutti gli appuntamenti ne hanno bisogno: «Apertura degli stand» si
    esaurisce in una riga di programma, mentre «Gita sul Cansiglio» o «Ama
    il tuo quartiere» hanno un luogo, un ritrovo, una quota e una storia da
    raccontare. Quando un evento ha un articolo, tutte le sue card sul sito
    diventano un link a `/eventi/<slug>`.

    Il corpo si scrive con una marcatura minima, pensata per l'admin:

        ## Un sottotitolo
        Un paragrafo qualsiasi. Una riga vuota separa i paragrafi.
        - una voce di elenco
        > una citazione o una nota in evidenza
    """

    evento = models.OneToOneField(
        Evento,
        on_delete=models.CASCADE,
        related_name="articolo",
        help_text="L'appuntamento raccontato da questa pagina.",
    )
    occhiello = models.CharField(
        max_length=80,
        blank=True,
        help_text="La riga sopra il titolo: «La proposta d'autunno».",
    )
    titolo = models.CharField(
        max_length=160, blank=True, help_text="Se vuoto viene usato il titolo dell'evento."
    )
    sottotitolo = models.CharField(
        max_length=280, blank=True, help_text="Il sommario in apertura, una o due righe."
    )
    corpo = models.TextField(
        blank=True,
        help_text=(
            "Il testo dell'articolo. Riga vuota = nuovo paragrafo; «## » = "
            "sottotitolo; «- » = voce di elenco; «> » = nota in evidenza."
        ),
    )
    copertina = models.ImageField(upload_to="articoli/", blank=True, help_text="immagine grande nel corpo dell'articolo")
    copertina_url = models.URLField(
        blank=True,
        help_text=(
            "In alternativa al file: indirizzo dell'immagine su un servizio "
            "esterno. Lo spazio sull'hosting e' poco, meglio i link."
        ),
    )
    copertina_alt = models.CharField(max_length=200, blank=True)
    identita = models.CharField(
        max_length=12,
        choices=Identita.choices,
        default=Identita.SALVIA,
        help_text="Colore dell'apertura e dei richiami della pagina.",
    )
    tono = models.CharField(
        max_length=14,
        choices=Tono.choices,
        blank=True,
        help_text="Tinta della fascia d'apertura. Vuoto = tinta dell'identita'.",
    )
    firma = models.CharField(
        max_length=120, blank=True, help_text="Chi l'ha scritto: «la Pro Loco», un nome."
    )
    data_pubblicazione = models.DateField(
        null=True, blank=True, help_text="La data in testa all'articolo. Vuoto = non si mostra."
    )

    class Meta:
        verbose_name = "articolo"
        verbose_name_plural = "articoli"
        ordering = ("-data_pubblicazione", "-creato_il")

    def __str__(self) -> str:
        return self.intestazione

    def campo_sorgente_slug(self) -> str:
        return self.titolo or self.evento.titolo

    @property
    def intestazione(self) -> str:
        return self.titolo or self.evento.titolo

    @property
    def copertina_sorgente(self) -> str:
        """L'immagine da mostrare: il file caricato, o il link esterno."""
        if self.copertina:
            return self.copertina.url
        return self.copertina_url


class DettaglioArticolo(models.Model):
    """
    Una riga della scheda pratica di un articolo: «Ritrovo · ore 7.00 in
    piazza». Sono le informazioni che la gente cerca prima del testo.
    """

    articolo = models.ForeignKey(Articolo, on_delete=models.CASCADE, related_name="dettagli")
    etichetta = models.CharField(max_length=60, help_text="«Quando», «Dove», «Quota», «Ritrovo»…")
    valore = models.CharField(max_length=200)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "dettaglio dell'articolo"
        verbose_name_plural = "dettagli dell'articolo"
        ordering = ("ordine", "id")

    def __str__(self) -> str:
        return f"{self.etichetta}: {self.valore}"


class Album(ModelloConSlug):
    """
    Una raccolta dell'archivio storico: «Le sagre degli anni Settanta».

    Le foto d'archivio sono tante e pesanti, e lo spazio sull'hosting e'
    poco: stanno su un servizio esterno (Google Foto, Flickr, Immich…) e
    qui se ne tiene solo il link. Vedi ``Foto.url_esterna``.
    """

    titolo = models.CharField(max_length=160)
    anno = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="L'anno degli scatti, se si conosce."
    )
    periodo = models.CharField(
        max_length=60,
        blank=True,
        help_text="Come si scrive l'epoca quando l'anno non e' certo: «anni '70».",
    )
    descrizione = models.TextField(blank=True)
    copertina_url = models.URLField(
        blank=True, help_text="Immagine di copertina ospitata su un servizio esterno."
    )
    copertina = models.ImageField(upload_to="album/", blank=True)
    copertina_alt = models.CharField(max_length=200, blank=True)
    attivita = models.ForeignKey(
        Attivita, on_delete=models.SET_NULL, related_name="album", null=True, blank=True
    )
    album_url = models.URLField(
        blank=True, help_text="L'album completo sul servizio esterno, se c'e'."
    )
    ordine = models.SmallIntegerField(
        default=0, help_text="A parita' di anno decide chi viene prima."
    )

    class Meta:
        verbose_name = "album d'archivio"
        verbose_name_plural = "album d'archivio"
        ordering = ("-anno", "ordine", "titolo")

    def __str__(self) -> str:
        return self.etichetta

    def campo_sorgente_slug(self) -> str:
        return f"{self.titolo}-{self.anno}" if self.anno else self.titolo

    @property
    def etichetta(self) -> str:
        epoca = self.periodo or (str(self.anno) if self.anno else "")
        return f"{self.titolo} ({epoca})" if epoca else self.titolo

    @property
    def copertina_sorgente(self) -> str:
        if self.copertina:
            return self.copertina.url
        return self.copertina_url


class Foto(models.Model):
    """
    Una foto del sito: raccolte di pagina, gallerie degli articoli, archivio.

    L'immagine puo' stare **qui** (file caricato in admin, finisce sul
    volume dei media e poi sull'hosting) oppure **fuori** (``url_esterna``:
    un link a un servizio cloud). Lo spazio sull'hosting condiviso e' poco:
    per l'archivio storico si usa sempre il link esterno.
    """

    attivita = models.ForeignKey(
        Attivita, on_delete=models.CASCADE, related_name="foto", null=True, blank=True
    )
    articolo = models.ForeignKey(
        Articolo,
        on_delete=models.CASCADE,
        related_name="foto",
        null=True,
        blank=True,
        help_text="Se valorizzato la foto compare nella galleria dell'articolo.",
    )
    album = models.ForeignKey(
        Album,
        on_delete=models.CASCADE,
        related_name="foto",
        null=True,
        blank=True,
        help_text="Se valorizzato la foto compare nell'album d'archivio.",
    )
    raccolta = models.SlugField(
        max_length=60,
        blank=True,
        help_text="Nome della galleria usata dalla pagina: «proloco», «grest», «storia».",
    )
    immagine = models.ImageField(upload_to="foto/", blank=True)
    url_esterna = models.URLField(
        blank=True,
        help_text=(
            "In alternativa al file: indirizzo diretto dell'immagine su un "
            "servizio esterno. Obbligatorio per l'archivio, dove lo spazio "
            "sull'hosting non basterebbe."
        ),
    )
    anno = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Anno dello scatto, per le foto d'archivio."
    )
    didascalia = models.CharField(max_length=200, blank=True)
    testo_alternativo = models.CharField(
        max_length=200, blank=True, help_text="Descrizione per screen reader."
    )
    ordine = models.PositiveSmallIntegerField(default=0)
    pubblicato = models.BooleanField(default=True)

    objects = models.Manager()
    visibili = Pubblicati()

    class Meta:
        verbose_name = "foto"
        verbose_name_plural = "foto"
        ordering = ("raccolta", "ordine", "id")

    def __str__(self) -> str:
        return self.didascalia or f"{self.raccolta or 'foto'} #{self.pk}"

    def clean(self):
        if not self.immagine and not self.url_esterna:
            raise ValidationError(
                "Serve un'immagine: carica il file oppure incolla l'indirizzo esterno."
            )

    @property
    def sorgente(self) -> str:
        """L'indirizzo da mettere nel `src`: il file caricato, o il link."""
        if self.immagine:
            return self.immagine.url
        return self.url_esterna
