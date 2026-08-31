# canizzano.it

Il sito del quartiere di **Canizzano** (Treviso): home, il calendario di
tutto il quartiere, Pro Loco tutto l'anno, la sagra d'ottobre, il Grest, la
storia, l'archivio fotografico e una pagina di approfondimento per ogni
evento che ne merita una — generate come **HTML statico** e caricate via FTP
su un hosting condiviso, senza bisogno di un VPS.

I contenuti che cambiano (eventi, programma della sagra, foto, interruttori
delle sezioni) si redigono in un **CMS Django** che gira solo sul server di
casa: Astro lo interroga una volta a ogni build e produce pagine statiche.

```
   redazione                build                    pubblicazione
┌──────────────┐      ┌──────────────┐          ┌──────────────────┐
│ Django admin │─API─▶│ Astro build  │──dist/──▶│ hosting via FTP  │
│  + Postgres  │      │  (statico)   │          │ (nessun runtime) │
└──────────────┘      └──────────────┘          └──────────────────┘
      locale                locale                     remoto
```

---

## Un comando per tutto

```bash
cp .env.example .env      # poi compila i valori (vedi sotto)
./canizzano.sh tutto      # avvia il CMS, genera il sito, lo pubblica via FTP
```

| Comando | Cosa fa |
| --- | --- |
| `./canizzano.sh avvia` | Avvia PostgreSQL + CMS Django — redazione su <http://localhost:8000/admin/> |
| `./canizzano.sh dev` | Anteprima del sito con ricarica automatica su <http://localhost:4321> |
| `./canizzano.sh build` | Genera il sito statico in `./dist` |
| `./canizzano.sh pubblica` | Carica `./dist` sull'hosting via FTP (fa il build se manca) |
| `./canizzano.sh tutto` | `build` + `pubblica` |
| `./canizzano.sh prova-ftp` | Simula il caricamento FTP **senza scrivere nulla** sul server |
| `./canizzano.sh stato` / `log` | Container attivi / log in tempo reale |
| `./canizzano.sh gestisci …` | Un comando `manage.py` dentro al container (es. `gestisci createsuperuser`) |
| `./canizzano.sh esempi` | Popola il CMS con i contenuti reali 2026 |
| `./canizzano.sh backup` | Esporta il database in `./backup` |
| `./canizzano.sh chiave` | Genera e scrive una nuova `DJANGO_SECRET_KEY` nel `.env` |
| `./canizzano.sh pulisci` | Ferma tutto ed elimina volumi e build — **cancella i dati** |

> Se Docker richiede i privilegi lo script usa `sudo docker` da solo. Per
> evitarlo: `sudo usermod -aG docker $USER`, poi rifai il login.

---

## Configurazione

Tutte le variabili sensibili stanno nel `.env`, che **non va su git**.
Parti da `.env.example`; i valori da compilare per forza sono:

| Variabile | A cosa serve |
| --- | --- |
| `DJANGO_SECRET_KEY` | Chiave di Django — generala con `./canizzano.sh chiave` |
| `POSTGRES_PASSWORD` | Password del database |
| `DJANGO_SUPERUSER_USERNAME` / `_PASSWORD` | L'utenza di redazione, creata al primo avvio |
| `FTP_HOST` / `FTP_USER` / `FTP_PASSWORD` | Credenziali dell'hosting |
| `FTP_REMOTE_DIR` | Cartella pubblica dell'hosting (spesso `/public_html` o `/htdocs`) |

Prima della prima pubblicazione conviene sempre `./canizzano.sh prova-ftp`:
elenca i file che verrebbero caricati e cancellati, senza toccare il server.

---

## Struttura

```
canizzano/
├── canizzano.sh              un comando per tutto
├── compose.yaml              lo stack: db, cms, build, dev, deploy (a profili)
├── .env.example              modello di configurazione
│
├── backend/                  CMS Django 6 + DRF — gira solo in locale
│   ├── canizzano_cms/        impostazioni, rotte, wsgi
│   └── eventi/               modelli, admin in italiano, API
│
├── frontend/                 sito Astro 7, output statico
│   ├── src/components/       la libreria di componenti (vedi sotto)
│   ├── src/layouts/Base.astro  testata + contenuto + footer comuni
│   ├── src/pages/            le pagine (`eventi/[slug]` e' generata dal CMS)
│   ├── src/lib/              contenuti dal CMS, date, toni, testi, configurazione
│   └── src/styles/           il design system Organic + le primitive di pagina
│
├── deploy/                   container usa e getta che carica via FTP (lftp)
└── dist/                     il sito generato (non versionato)
```

### Le pagine

| Indirizzo | Cosa c'e' |
| --- | --- |
| `/` | La home: cosa si muove a Canizzano, in trenta secondi |
| `/calendario` | **Tutti** gli appuntamenti del quartiere, mese per mese |
| `/proloco` | La Pro Loco Cannetum tutto l'anno |
| `/sagra` | «Canizzano in Festa», il programma giorno per giorno |
| `/grest` | Il Grest dei ragazzi |
| `/storia` | La storia del quartiere, dalle paludi a oggi |
| `/archivio` | L'archivio fotografico (bozza: le foto stanno su cloud) |
| `/eventi/<slug>` | L'approfondimento di un evento — una pagina per articolo |

`/calendario` e `/eventi/<slug>` sono generate interamente dal CMS: la prima
mette in fila gli eventi di tutte le realta', la seconda esiste solo per gli
eventi a cui la redazione ha attaccato un **articolo**.

### I componenti

Ogni elemento visivo è definito **una volta sola** e riusato. Le pagine
compongono, non ridisegnano.

**Fondamentali** — `Bottone`, `Etichetta` (tag), `Icona` (il set Lucide del
sistema), `DiscoIcona`, `Foto` (trattamento `.washed` + segnaposto quando la
foto manca), `Scheda`, `Sezione`, `Fascia`.

**Composti** — `Intestazione` e `PiePagina` (comuni a tutte le pagine),
`Marchio` e `Lockup` (i cinque marchi), `TestataSezione`, `BloccoAzione`,
`BarraCifre`, `Cifra`, `MosaicoFoto`.

**Di contenuto** — `CardEvento`, `SezioneEventi`, `CardGiornata`,
`SchedaCalendario`, `RigaCalendario`, `ColonnaStagione`, `RigaOrario`,
`RigaGiornata`, `PastigliaData`, `CardCollegamento`, `SchedaRitratto`,
`SchedaNota`, `SchedaTesto`, `SchedaAlbum`, `CorpoArticolo`, `VoceTempo`,
`RigaElenco`, `CardContatto`, `PassoNumerato`, `ContoRovescia`,
`ModuloPrenotazione`.

I colori che la redazione sceglie («tono» di una card, di un disco, di una
pastiglia) stanno **una volta sola** in `src/lib/toni.ts`: aggiungere una
tinta e' una riga li', non quattro tabelle sparse nei componenti.

### Il design system

`frontend/src/styles/organic.css` è la copia fedele dei token consegnati da
Claude Design: colori, rampe tonali, tipografia (Caprasimo + Figtree),
spaziature, raggi, ombre e le classi componente (`.btn`, `.tag`, `.card`,
`.table`, `.input`, `.washed`). **I valori si ritoccano lì, mai nelle pagine.**
`sito.css` aggiunge solo la griglia di pagina, gli stacchi fra sezioni e le
regole responsive che i prototipi desktop non coprivano.

---

## Cosa si cambia dall'admin

Su <http://localhost:8000/admin/>:

- **Impostazioni del sito** — gli interruttori delle sezioni condizionali:
  banner della sagra in home, conto alla rovescia, sponsor, galleria della
  Pro Loco, iscrizioni al Grest aperte, foto del Grest, modalità sagra.
- **Attività** — le realtà del quartiere: nome, testo, icona, tinta del disco
  e destinazione delle card della home.
- **Eventi** — l'appuntamento singolo. Lo stesso record alimenta quattro
  viste: la card dei «prossimi appuntamenti» in home, la riga del calendario
  di quartiere, la riga oraria del programma della sagra (con piatto del
  giorno e prenotazioni) e la colonna stagionale dell'anno Pro Loco.
- **Articoli** — la pagina di approfondimento di un evento, **facoltativa**:
  vedi sotto.
- **Giornate** — come si presenta la card di ogni giorno della sagra: titolo,
  riga di richiamo, colore della pastiglia.
- **Album d'archivio** — le raccolte di `/archivio`: vedi sotto.
- **Edizioni**, **Luoghi**, **Foto** — annate, sedi ricorrenti e raccolte
  fotografiche delle pagine.

### Quando un evento merita la sua pagina

Quasi nessun evento ne ha bisogno: «Apertura degli stand» si esaurisce in una
riga di programma. Ma «Gita sul Cansiglio» ha un ritrovo, una quota, un
percorso e un pranzo da spiegare — e allora si apre **Articoli → aggiungi**,
si sceglie l'evento e si scrive.

Da quel momento *tutte* le card di quell'evento — home, calendario, colonna
stagionale, riga della sagra — diventano un link a `/eventi/<slug>`, e la
pagina viene generata al build successivo. Senza articolo non cambia niente:
la card resta un blocco di testo, che va benissimo.

Il corpo si scrive in una textarea, con quattro segni:

```
## Un sottotitolo
Un paragrafo qualsiasi. Una riga vuota separa i paragrafi.
- una voce di elenco
> una nota da mettere in evidenza
```

Sotto il titolo compare la **scheda pratica**: le righe «Dettagli
dell'articolo» (`Ritrovo · ore 7.00 in piazza`). Se non ne scrivi nessuna, la
pagina ripiega su data, luogo e ingresso dell'evento.

### L'archivio: le foto stanno fuori

Lo spazio sull'hosting condiviso è poco, e un archivio di scansioni lo
riempirebbe in un pomeriggio. Quindi le foto d'archivio **non si caricano nel
CMS**: si mettono su un servizio cloud (Google Foto, Flickr, Immich…) e in
admin si incolla il link.

1. **Album d'archivio → aggiungi**: titolo, anno o epoca («anni '70»),
   descrizione. `Album completo` è il link alla raccolta sul servizio esterno.
2. Nelle foto dell'album si compila **`url esterna`** — l'indirizzo diretto
   dell'immagine — invece di caricare il file.
3. Finché un album non ha foto collegate, `/archivio` lo mostra come «in
   preparazione»: la pagina resta impaginata, senza buchi.

Il campo `url esterna` c'è su **tutte** le foto, non solo quelle d'archivio:
funziona ovunque, e l'immagine caricata ha comunque la precedenza sul link.
`/archivio` è al momento una **bozza**: la struttura è quella definitiva, i
contenuti no.

### Il giro di lavoro

```
1. ./canizzano.sh dev          l'anteprima resta accesa su :4321
2. modifichi in admin          su :8000/admin/
3. ricarichi il browser        ← basta questo, niente riavvii
4. ./canizzano.sh tutto        quando sei contento: build + pubblicazione
```

In **anteprima** i contenuti vengono riletti a ogni caricamento di pagina:
una modifica fatta in admin si vede ricaricando il browser, senza riavviare
niente. In **build** invece il CMS viene letto una volta sola per tutte e
le pagine, cosi' il sito pubblicato e' uno stato coerente.

Le modifiche finiscono online **al build successivo**: `./canizzano.sh tutto`.

Se il CMS è spento il build non si interrompe: le pagine vengono generate
senza le sezioni dinamiche, così un CMS fermo non blocca una pubblicazione.

---

## Se qualcosa non va

**`relation "eventi_..." does not exist` nell'admin**

Il database e' rimasto indietro rispetto ai modelli: succede se il volume di
PostgreSQL e' stato creato con una versione precedente delle migrazioni.
Django registra le migrazioni per nome, quindi `migrate` le considera gia'
applicate e non crea le tabelle nuove.

```bash
./canizzano.sh verifica-db    # cosa c'e' davvero: tabelle e migrazioni (non tocca nulla)
./canizzano.sh backup         # solo se hai contenuti da salvare
./canizzano.sh ripristina-db  # ricrea il database, tiene le foto caricate
```

`ripristina-db` a fine corsa controlla da solo che tutte le tabelle esistano:
se qualcosa non ha funzionato te lo dice, invece di lasciartelo scoprire
aprendo l'admin.

**«Another astro dev server is already running» quando riavvii l'anteprima**

Astro segna il server di sviluppo con un lock in `.astro/dev.json` e lo
cancella solo se lo spegni con garbo; un container fermato di colpo lo lascia
li'. Il controllo si basa sul PID, che dentro a un container riparte da zero:
al riavvio Astro crede che ci sia gia' un server acceso. L'entrypoint ora
rimuove il lock a ogni avvio, e `dev` ricrea il container da capo.

Se ricapita basta:

```bash
./canizzano.sh ferma-dev   # ferma solo l'anteprima
./canizzano.sh dev
```

**Non serve mai toccare il database per un problema dell'anteprima.**
`ferma`, `ferma-dev` e `down` non cancellano nulla: i dati spariscono solo
con `pulisci` o `ripristina-db`, che lo dicono chiaramente prima di agire.

**Il build non trova il CMS**

Il messaggio `CMS non raggiungibile` non blocca il build: le pagine escono
senza le sezioni dinamiche. Controlla che il CMS sia su con
`./canizzano.sh stato` e guarda i log con `./canizzano.sh log backend`.

---

## Da fare prima del go-live

- **Le due foto reali del Grest** (`grest-locandina.jpg` e `grest-gruppo.jpg`)
  vanno scaricate dal progetto Claude Design e caricate in admin →
  *Foto*, raccolte `grest-locandina` e `grest`.
- Tutte le altre foto sono segnaposto: finché mancano, il sito mostra un
  riquadro con la descrizione della foto attesa, senza rompere l'impaginazione.
- Contenuti ancora in bozza (segnalati nell'handoff di design): quota del
  Grest, orari della giornata tipo, date degli eventi Pro Loco minori, i
  numeri della barra Pro Loco, la nota storica sul «Principato di Canizzano».
- Attivare le caselle `info@canizzano.it` e `proloco@canizzano.it`.
- **Scegliere il servizio cloud per l'archivio** e cominciare a incollare i
  link nelle tre raccolte gia' aperte (sagre di una volta, mulini, squadra).
- Il **Principato di Canizzano** ha la sua card in home e punta a
  `/storia#principato`: se diventa una realta' con una sua pagina, basta
  cambiare il collegamento in admin → *Attivita*.
