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
| `./canizzano.sh avvia` | Avvia PostgreSQL + CMS Django — redazione su <http://localhost:8000/admin/>, dashboard su <http://localhost:8000/riservata/> |
| `./canizzano.sh dev` | Anteprima del sito con ricarica automatica su <http://localhost:4321> |
| `./canizzano.sh dev-sfondo` | Come `dev`, ma senza restare in primo piano (è la forma che usa la dashboard) |
| `./canizzano.sh build` | Genera il sito statico in `./dist` |
| `./canizzano.sh pubblica` | Carica `./dist` sull'hosting via FTP (fa il build se manca) |
| `./canizzano.sh tutto` | `build` + `pubblica` |
| `./canizzano.sh prova-ftp` | Simula il caricamento FTP **senza scrivere nulla** sul server |
| `./canizzano.sh stato` / `log` | Container attivi / log in tempo reale |
| `./canizzano.sh mcp` | Indirizzo e chiave per collegare un **assistente AI** al CMS |
| `./canizzano.sh gestisci …` | Un comando `manage.py` dentro al container (es. `gestisci createsuperuser`) |
| `./canizzano.sh esempi` | Popola il CMS con i contenuti reali 2026 |
| `./canizzano.sh backup` | Esporta il database in `./backup` |
| `./canizzano.sh chiave` | Genera e scrive una nuova `DJANGO_SECRET_KEY` nel `.env` |
| `./canizzano.sh pulisci` | Ferma tutto ed elimina volumi e build — **cancella i dati** |

> Se Docker richiede i privilegi lo script usa `sudo docker` da solo. Per
> evitarlo: `sudo usermod -aG docker $USER`, poi rifai il login.

---

## La dashboard della redazione

Gli stessi comandi hanno un bottone su <http://localhost:8000/riservata/>,
dietro il login dell'admin. È pensata per non dover mai aprire il terminale:
un collegamento all'admin, uno alle chiavi dell'assistente AI, i bottoni
**Avvia** / **Anteprima** / **Ferma anteprima**, **Elabora il foglietto**, e
— staccato dagli altri, rosso, con conferma — **Pubblica tutto**, l'unico che
tocca il sito pubblico. Sotto, la cronologia delle ultime attività con il
dettaglio espandibile.

### Chi esegue i comandi

Django gira dentro un container costruito dalla sola cartella `backend/`: non
ha `canizzano.sh`, non ha la CLI di Docker, e soprattutto `avvia` e `tutto`
ricreano il container del CMS — cioè ucciderebbero il processo che sta
servendo la richiesta. Per questo l'esecuzione sta altrove:

```
browser ──POST──▶ Django          scrive coda/<id>.json
                                        │
                                        ▼
                                     coda/           bind mount condiviso
                                        │
                            esecutore (container)    legge, esegue lo script
                                        │            sull'host via docker.sock
                                        ▼
                              logs/attivita.log      l'esito, in JSON Lines
                                        │
browser ◀──polling── Django rilegge il registro
```

Il container `esecutore` si accende insieme al resto con `./canizzano.sh
avvia` e riparte da solo al riavvio della macchina (`restart: always`).
Nessun comando della dashboard lo tocca: è per questo che sopravvive al
riavvio del CMS e può raccontare com'è finita.

È l'unico container con accesso a `/var/run/docker.sock` — cioè, di fatto,
ai privilegi di root sulla macchina. Django quell'accesso non ce l'ha e non
deve averlo. La lista dei comandi eseguibili è fissa nel codice (in
`backend/canizzano_cms/views.py` e ripetuta in `esecutore/esecutore.py`): il
nome passato allo script esce sempre da lì, mai dal contenuto della
richiesta.

### Elabora il foglietto: il bot che sta in un altro repository

Il bot che scarica il foglietto parrocchiale, lo legge con Gemini e ne scrive
eventi e articoli nel CMS **non sta qui dentro**: ha un repository suo
(`canizzano-mcp`), il suo container Docker, sempre acceso, con uno scheduler
interno che lo fa partire da solo ogni sabato mattina e un controllo ogni
mezz'ora. Il bottone serve al caso «serve adesso»: il foglietto è uscito prima
del solito, o qualcosa non è partito.

Non ha la conferma rossa perché non tocca il sito pubblico: scrive nel CMS, e
quello che scrive resta in redazione finché non lo pubblichi tu — l'assistente
non pubblica mai.

**Questo comando non esegue niente**, ed è l'unica eccezione al giro qui
sopra: invece di lanciare `canizzano.sh`, l'esecutore fa una richiesta HTTP al
container del bot, sulla rete Docker condivisa fra i due stack.

```
dashboard ──▶ coda/<id>.json ──▶ esecutore ──POST /attiva──▶ container del bot
                                  (rete Docker condivisa)    prova stato/bot.lock
                                                                      │
                                                    ┌─────────────────┴─────────────────┐
                                               è occupato                          è libero
                                                    │                                   │
                                   registro: «errore,                    202, e in un thread:
                              esecuzione già in corso»               scraper, poi «scansiona»
                                                                                     │
                                                                     logs/attivita.log ◀── ci
                                                                    scrive il bot, col suo nome
```

Il lucchetto è quello che il bot **già** usa per non pestarsi i piedi da solo
(vedi `pipeline.lucchetto()` nel suo repository): l'endpoint lo *guarda* prima
di rispondere, per dare un esito subito in dashboard, ma l'esclusione vera
resta lì — se un giro programmato e uno chiesto a mano si accavallano, è
quello arrivato secondo a fermarsi.

La dashboard non aspetta: la riga che compare subito dice «richiesta
consegnata» (o perché non lo è stata: bot spento, rete condivisa non ancora
creata, token sbagliato — l'esecutore distingue i casi, non un timeout muto),
non «foglietto elaborato». L'esito vero arriva dopo, sotto `scraper_foglietto`
e `ocr_redazione_foglietto`, distinti a colpo d'occhio da
`avvio_manuale_foglietto` che è l'atto di aver premuto il bottone.

Il tetto di tempo per la *richiesta* è `TIMEOUT_FOGLIETTO` (10 secondi:
l'endpoint risponde subito, non aspetta l'elaborazione). Il tetto per
l'elaborazione vera lo tiene il bot stesso, nel suo repository.

Servono due righe nel `.env`:

```
BOT_FOGLIETTO_URL=http://bot:8088/attiva
BOT_FOGLIETTO_TOKEN=<la stessa stringa che nel .env del bot si chiama ATTIVA_TOKEN>
```

`bot` è il nome del servizio nel `compose.yaml` di quel repository — non
"localhost": i due stack sono due progetti `docker compose` separati, e si
raggiungono solo perché condividono la rete esterna `NOME_RETE_CONDIVISA`
(vedi «La rete condivisa» più sotto). Lasciale vuote se il bot non c'è: il
bottone semplicemente non compare, e il resto funziona come prima.

`FILE_ATTIVITA` in questo `.env` resta quello che è già: il bot scrive nello
stesso `logs/attivita.log` montandolo lui come bind mount dal proprio
`compose.yaml` (variabile `CARTELLA_LOG_SITO` nel suo `.env`, puntata
all'assoluto di questa cartella `logs/`) — non c'è niente da configurare qui
oltre a quello che già serve alla dashboard.

### La rete condivisa fra i due stack

```bash
docker network create canizzano_rete   # una tantum, prima del primo avvio
```

Lo stesso nome deve comparire, identico, in `NOME_RETE_CONDIVISA` in
**entrambi** i `.env` (questo repository e `canizzano-mcp`). `compose.yaml` la
referenzia come rete esterna sui servizi `backend` (così il bot può chiamare
`http://backend:8000/mcp/`) ed `esecutore` (così può chiamare
`http://bot:8088/attiva`); se la rete non esiste, `docker compose up` si
ferma con un errore che lo dice, non con un avvio a metà.

### Su un'altra macchina (Raspberry Pi, server, un altro portatile)

Non c'è niente da configurare: **si clona e si lancia `./canizzano.sh avvia`**.
Il percorso del progetto, l'utente proprietario dei file e il gruppo del
socket Docker si ricavano a ogni avvio, quindi lo stesso repo funziona da
`/home/matte/…` come da `/opt/canizzano` o `/home/pi/canizzano`, e continua a
funzionare se sposti la cartella.

Tutte le immagini di base sono multi-architettura (`amd64`, `arm64`,
`arm/v7`), quindi il Raspberry Pi va — anche il `docker:cli` dell'esecutore,
che porta con sé il plugin `compose`. Due avvertenze pratiche:

- **Prendi un sistema a 64 bit.** Su Raspberry Pi OS a 32 bit alcune immagini
  esistono ma il build di Astro è al limite della memoria indirizzabile.
- **Il primo `avvia` è lento** (build di quattro immagini). I tetti di tempo
  dei comandi sono larghi apposta — mezz'ora per `avvia`, due ore per
  `tutto` — e si alzano dal `.env` se non bastassero.

Per le macchine fuori standard il `.env` ha un blocco di scavalcamenti, tutto
commentato perché di norma non serve: `DOCKER_SOCKET` (Docker rootless tiene
il socket in `/run/user/<uid>/`), `UID_HOST` / `GID_HOST`, e i `TIMEOUT_*`.
L'ordine di precedenza è **ambiente → `.env` → rilevamento automatico**.

> Il percorso dello script **non** è una variabile di configurazione, ed è
> voluto: una copia scritta a mano nel `.env` sarebbe una cosa in più da
> tenere allineata e si romperebbe al primo spostamento della cartella.
> `canizzano.sh` sa già dove si trova e lo comunica a compose.

Se lanci con `sudo` (macchina dove non sei ancora nel gruppo `docker`) i file
generati restano comunque intestati a te, non a root: lo script legge
`SUDO_UID`.

### Cosa succede se la macchina si spegne di colpo

`db`, `backend` ed `esecutore` hanno `restart: always`: tornano su da soli,
senza che nessuno tocchi il terminale. L'anteprima (`dev`) no, ed è voluto —
non ha senso riaccenderla da sola. Un lavoro che era **in corso** quando è
mancata la corrente viene chiuso come errore al riavvio («esito
sconosciuto»), così la dashboard non resta ad aspettare per sempre. Un lavoro
che era ancora **in coda** e non è mai partito viene **rifiutato** se nel
frattempo sono passati più di dieci minuti: nessuno si aspetta che il sito
venga pubblicato da solo al ritorno della corrente, ore dopo.

> **Da verificare una volta sola su ogni macchina nuova:** che Docker riparta
> al boot, con `systemctl is-enabled docker.service`. Se risponde `disabled`
> (succede quando è attiva solo `docker.socket`), il demone parte solo al
> primo comando e i container **non** tornano su da soli dopo un riavvio.
> Si sistema con `sudo systemctl enable docker.service`.

C'è un solo caso che il riavvio non può salvare: se la corrente manca **a
metà del caricamento FTP**, sull'hosting resta un sito a metà. Basta premere
di nuovo «Pubblica tutto».

### Il registro delle attività

`logs/attivita.log`, formato **JSON Lines** — una riga per evento:

```json
{"timestamp": "2026-09-05T13:47:03+02:00", "processo": "canizzano.sh tutto", "stato": "ok", "dettaglio": "…"}
```

`stato` è `ok` oppure `errore`; `dettaglio` è testo libero (l'output del
comando, o il messaggio d'errore). Chi legge non sa quali processi esistano:
prende le ultime righe, scarta quelle malformate e ordina per data. Per
aggiungerne uno basta appendere una riga in quel formato.

Oggi ci scrivono:

| `processo` | Chi lo scrive |
| --- | --- |
| `canizzano.sh <comando>` | Lo script, o l'esecutore per conto della dashboard |
| `avvio_manuale_foglietto` | L'esecutore, quando premi «Elabora il foglietto» |
| `scraper_foglietto` | Il bot, quando scarica il PDF dal sito della parrocchia |
| `ocr_redazione_foglietto` | Il bot, quando ha letto un foglietto e scritto nel CMS |

Le ultime due arrivano dall'altro repository, che scrive in questo stesso file
(`FILE_ATTIVITA` nel suo `.env`). L'OCR del libretto si aggiungerà allo stesso
modo, senza che qui cambi niente.

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

Due sono facoltative, per il bottone «Elabora il foglietto» (vedi sopra) —
tutti gli altri percorsi si ricavano da soli:

| Variabile | A cosa serve |
| --- | --- |
| `BOT_FOGLIETTO_URL` | Indirizzo dell'endpoint `/attiva` del bot, sulla rete Docker condivisa. Senza, il bottone non compare |
| `BOT_FOGLIETTO_TOKEN` | Token condiviso col bot — deve combaciare col suo `ATTIVA_TOKEN` |

Prima della prima pubblicazione conviene sempre `./canizzano.sh prova-ftp`:
elenca i file che verrebbero caricati e cancellati, senza toccare il server.

---

## Struttura

```
canizzano/
├── canizzano.sh              un comando per tutto
├── compose.yaml              lo stack: db, cms, esecutore, build, dev, deploy
├── .env.example              modello di configurazione
│
├── backend/                  CMS Django 6 + DRF — gira solo in locale
│   ├── canizzano_cms/        impostazioni, rotte, wsgi, dashboard riservata
│   ├── templates/            riservata.html: la dashboard della redazione
│   ├── eventi/               modelli, admin in italiano, API
│   └── assistente/           il server MCP: il CMS parlato con un agente AI
│
├── frontend/                 sito Astro 7, output statico
│   ├── src/components/       la libreria di componenti (vedi sotto)
│   ├── src/layouts/Base.astro  testata + contenuto + footer comuni
│   ├── src/pages/            le pagine (`eventi/[slug]` e' generata dal CMS)
│   ├── src/lib/              contenuti dal CMS, date, toni, testi, configurazione
│   └── src/styles/           il design system Organic + le primitive di pagina
│
├── esecutore/                esegue i comandi premuti sulla dashboard
├── deploy/                   container usa e getta che carica via FTP (lftp)
├── logs/                     registro delle attività (non versionato)
├── coda/                     lavori in attesa per l'esecutore (non versionato)
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

## L'assistente AI: cambiare il sito parlando

Il CMS espone un **server MCP** (Model Context Protocol) su `/mcp/`. È la
stessa redazione dell'admin, ma invece dei moduli c'è un agente: gli si
chiede a parole di aggiungere un evento, cambiare il menù di una serata
della sagra o scrivere un articolo, e lui lo fa nel database.

```
      tu ─parli─▶ il tuo agente AI ─MCP─▶ CMS Django ─▶ build ─▶ sito
```

L'agente non è al buio: prima di scrivere legge la **guida della redazione**
che il server gli serve — quando un evento merita una pagina di
approfondimento, come è fatta la sagra, quale icona sta bene a una folpata,
come si scrive il corpo di un articolo. Gli elenchi (attività, icone, tinte,
campi) li legge dai modelli del CMS, quindi non può proporre un'icona che non
esiste o un'attività che non c'è.

### Dove si prende la chiave

Il «login» dell'assistente è una **chiave**, e sta nell'admin:

> <http://localhost:8000/admin/> → **Assistente AI** → **chiavi
> dell'assistente** → apri *«Il mio assistente»*

Una chiave viene creata da sola al primo avvio: nella sua pagina trovi
l'indirizzo, la chiave e i comandi già pronti da copiare. Le stesse
istruzioni, senza aprire il browser:

```bash
./canizzano.sh mcp                          # mostra la chiave che c'è
./canizzano.sh mcp --nuova --nome "Cursor"  # ne aggiunge un'altra
```

**La chiave vale come una password**: chi ce l'ha può cambiare il sito. Se ne
dai una a ogni agente puoi revocarne una senza spegnere le altre — basta
togliere la spunta *attiva*. La spunta *sola lettura* fa una chiave che
guarda e basta: comoda per provare un assistente nuovo.

### Come si collega

Il CMS deve essere acceso (`./canizzano.sh avvia`). Poi, a seconda del client:

```bash
# Claude Code, dal terminale
claude mcp add --transport http canizzano http://localhost:8000/mcp/ \
  --header "Authorization: Bearer LA-TUA-CHIAVE"
```

```jsonc
// Claude Desktop, Cursor e gli altri che si configurano a file
{
  "mcpServers": {
    "canizzano": {
      "type": "http",
      "url": "http://localhost:8000/mcp/",
      "headers": { "Authorization": "Bearer LA-TUA-CHIAVE" }
    }
  }
}
```

I client che accettano solo un indirizzo possono usare
`http://localhost:8000/mcp/?chiave=LA-TUA-CHIAVE`, ma così la chiave finisce
nei log del server: meglio l'intestazione, quando si può.

Se l'agente gira su un'altra macchina, il CMS di casa dev'essere
raggiungibile da lì (un tunnel, un dominio): metti l'indirizzo pubblico in
`MCP_URL_PUBBLICO` e aggiungi l'host a `DJANGO_ALLOWED_HOSTS` nel `.env`.

### Che cosa dirgli all'inizio

Come è fatto il sito non serve spiegarglielo: glielo racconta il server al
collegamento, e il resto sta in `guida_del_sito`. Serve invece dirgli **come
vuoi lavorare** — quanto può fare da solo, che cosa deve chiederti prima, che
tono usare. C'è un prompt già scritto da incollare nelle istruzioni di
sistema del tuo agente, con segnate le righe da riadattare:
[`backend/assistente/PROMPT.md`](backend/assistente/PROMPT.md).

### Che cosa gli si può chiedere

> «Il Principato organizza la folpata il 13 dicembre alle 19.30 in piazza:
> crea l'evento, mettilo in evidenza in home e scrivimi anche l'articolo con
> ritrovo e quota.»

> «Fammi vedere il programma della sagra. Sabato 3 cambia il piatto del
> giorno: non tagliata, ma sarde in saor.»

> «Questa è la locandina del Grest: caricala e mettila come copertina
> dell'articolo.» *(l'immagine viaggia dentro la richiesta)*

> «Controlla il sito prima che pubblichi: eventi passati ancora in evidenza,
> articoli senza copertina, foto senza testo alternativo.»

Gli strumenti sono venticinque: `panoramica`, `cerca_contenuti`,
`leggi_contenuto`, `programma_sagra` e `guida_del_sito` per guardare;
`crea_…` e `aggiorna_…` per ognuno degli otto tipi di contenuto (evento,
articolo, giornata, foto, attività, edizione, luogo, album);
`imposta_dettagli_articolo`, `aggiorna_impostazioni`, `carica_immagine` e
`elimina_contenuto` per il resto. Cancellare chiede sempre conferma e prima
mostra che cosa si porterebbe dietro — eliminare un evento porta via il suo
articolo, i dettagli e le foto.

### Quello che l'assistente NON fa

**Non pubblica.** Il sito è statico: quello che l'agente scrive sta nel CMS e
va online solo al build successivo. Il server glielo ricorda a ogni
modifica, e a te resta l'ultima parola:

```bash
./canizzano.sh dev      # per vedere com'è venuto, su localhost:4321
./canizzano.sh tutto    # quando sei contento: build + pubblicazione
```

Se il tuo agente ha un terminale sulla cartella del progetto (Claude Code, per
esempio), puoi chiedergli di lanciarlo lui — ma è una cosa che fa da fuori,
non attraverso il CMS.

### Com'è fatto

Sta tutto in `backend/assistente/`, senza dipendenze in più: il protocollo
MCP che serve qui sono otto metodi JSON-RPC su una rotta POST
(`protocollo.py`), e una libreria in più sarebbe una cosa da aggiornare al
posto di una cosa che funziona. Gli strumenti `crea_…` e `aggiorna_…` non
sono scritti a mano: `schemi.py` li genera dai modelli di `eventi/models.py`
— tipo, obbligatorietà, valori ammessi, testo d'aiuto. Aggiungere un'icona
resta una riga in `models.py` e l'assistente la sa al riavvio, come
aggiungere una tinta è una riga in `toni.ts`. In `guida.py` c'è invece
quello che dai modelli non si legge: il mestiere della redazione.

Il server non tiene sessioni: ogni richiesta è completa in sé, così i tre
worker di gunicorn si equivalgono e non c'è stato da sincronizzare.

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

**L'assistente AI risponde «401» o non vede nessuno strumento**

Nell'ordine: il CMS è acceso (`./canizzano.sh stato`)? L'indirizzo è
`http://localhost:8000/mcp/`, con la barra finale? La chiave è quella giusta
e ha ancora la spunta *attiva*? Le trovi tutte con `./canizzano.sh mcp`, e
per provare il server senza scomodare l'agente:

```bash
curl -sS http://localhost:8000/mcp/ -H 'Authorization: Bearer LA-TUA-CHIAVE' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | head -c 300
```

Se hai cambiato i modelli in `eventi/models.py`, l'assistente se ne accorge
solo al riavvio del CMS: `./canizzano.sh avvia`.

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
