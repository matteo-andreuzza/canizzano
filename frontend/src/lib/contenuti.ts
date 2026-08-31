/**
 * Ponte fra il CMS Django e le pagine Astro.
 *
 * Lo snapshot viene letto UNA volta per build (`/api/snapshot/`) e messo in
 * cache in memoria: tutte le pagine generate leggono lo stesso stato
 * coerente, senza una richiesta per pagina.
 *
 * Se il CMS non risponde il build non si interrompe: il sito viene generato
 * con le sole sezioni statiche, cosi' un CMS spento non blocca il deploy.
 */

export interface Luogo {
  id: number;
  nome: string;
  indirizzo: string;
  mappa_url: string;
}

export interface Attivita {
  id: number;
  slug: string;
  nome: string;
  sottotitolo: string;
  descrizione: string;
  descrizione_breve: string;
  identita: 'terracotta' | 'salvia' | 'neutro';
  icona: string;
  tono: string;
  sfondo_caldo: boolean;
  collegamento: string;
  etichetta_collegamento: string;
  esterno: boolean;
  immagine: string | null;
  immagine_alt: string;
  email: string;
  telefono: string;
  ordine: number;
  in_menu: boolean;
  in_home: boolean;
}

export interface Edizione {
  id: number;
  slug: string;
  anno: number;
  titolo: string;
  etichetta: string;
  descrizione: string;
  attivita: string;
  immagine: string | null;
  immagine_alt: string;
}

export interface Evento {
  id: number;
  slug: string;
  titolo: string;
  sommario: string;
  descrizione: string;
  categoria: string;
  icona: string;
  inizio: string;
  fine: string | null;
  tutto_il_giorno: boolean;
  etichetta_data: string;
  tono: string;
  stagione_scelta: string;
  stagione: 'inverno' | 'primavera' | 'estate' | 'autunno';
  attivita: string;
  edizione: string | null;
  luogo: Luogo | null;
  luogo_libero: string;
  dove: string;
  immagine: string | null;
  immagine_alt: string;
  piatto_del_giorno: string;
  ingresso: string;
  prenotazione_entro: string | null;
  link: string;
  link_etichetta: string;
  in_evidenza: boolean;
  risalto: boolean;
  ordine: number;
  /** Slug della pagina di approfondimento, `null` se l'evento non ne ha. */
  articolo: string | null;
}

export interface Giornata {
  id: number;
  edizione: string | null;
  data: string;
  titolo: string;
  etichetta: string;
  occhiello: string;
  tono: string;
  sfondo_chiaro: boolean;
}

export interface Foto {
  id: number;
  raccolta: string;
  attivita: string | null;
  articolo: string | null;
  album: string | null;
  anno: number | null;
  /** L'indirizzo da mettere nel `src`: file caricato o link esterno. */
  immagine: string | null;
  url_esterna: string;
  didascalia: string;
  testo_alternativo: string;
  ordine: number;
}

/** Una riga della scheda pratica di un articolo: «Ritrovo · ore 7.00». */
export interface DettaglioArticolo {
  id: number;
  etichetta: string;
  valore: string;
  ordine: number;
}

/**
 * La pagina di approfondimento di un evento — facoltativa.
 *
 * Il `corpo` usa una marcatura minima, la stessa che si scrive in admin:
 * riga vuota = paragrafo, «## » = sottotitolo, «- » = elenco, «> » = nota.
 */
export interface Articolo {
  id: number;
  slug: string;
  evento: string | null;
  occhiello: string;
  titolo: string;
  intestazione: string;
  sottotitolo: string;
  corpo: string;
  copertina: string | null;
  copertina_url: string;
  copertina_alt: string;
  identita: 'terracotta' | 'salvia' | 'neutro';
  tono: string;
  firma: string;
  data_pubblicazione: string | null;
  dettagli: DettaglioArticolo[];
  foto: Foto[];
}

/** Una raccolta dell'archivio storico: le foto stanno su un servizio esterno. */
export interface Album {
  id: number;
  slug: string;
  titolo: string;
  etichetta: string;
  anno: number | null;
  periodo: string;
  descrizione: string;
  copertina: string | null;
  copertina_url: string;
  copertina_alt: string;
  attivita: string | null;
  album_url: string;
  ordine: number;
  foto: Foto[];
}

/** Gli interruttori delle sezioni condizionali, redatti nell'admin. */
export interface Impostazioni {
  mostra_banner_sagra: boolean;
  banner_occhiello: string;
  banner_titolo: string;
  banner_testo: string;
  banner_collegamento: string;
  banner_etichetta_bottone: string;
  modalita_sagra: boolean;
  data_inizio_sagra: string | null;
  mostra_conto_rovescia: boolean;
  mostra_sponsor: boolean;
  mostra_galleria_proloco: boolean;
  iscrizioni_grest_aperte: boolean;
  mostra_foto_grest: boolean;
}

export interface Snapshot {
  generato_il: string;
  impostazioni: Impostazioni;
  attivita: Attivita[];
  edizioni: Edizione[];
  eventi: Evento[];
  articoli: Articolo[];
  album: Album[];
  giornate: Giornata[];
  foto: Foto[];
  luoghi: Luogo[];
}

/** Valori di ripiego quando il CMS non risponde: il build non si ferma. */
const IMPOSTAZIONI_PREDEFINITE: Impostazioni = {
  mostra_banner_sagra: false,
  banner_occhiello: '',
  banner_titolo: '',
  banner_testo: '',
  banner_collegamento: '',
  banner_etichetta_bottone: '',
  modalita_sagra: false,
  data_inizio_sagra: null,
  mostra_conto_rovescia: false,
  mostra_sponsor: false,
  mostra_galleria_proloco: false,
  iscrizioni_grest_aperte: false,
  mostra_foto_grest: false,
};

const SNAPSHOT_VUOTO: Snapshot = {
  generato_il: new Date().toISOString(),
  impostazioni: IMPOSTAZIONI_PREDEFINITE,
  attivita: [],
  edizioni: [],
  eventi: [],
  articoli: [],
  album: [],
  giornate: [],
  foto: [],
  luoghi: [],
};

const BASE_CMS = (import.meta.env.CMS_URL ?? process.env.CMS_URL ?? 'http://backend:8000').replace(
  /\/$/,
  '',
);

let inCache: Promise<Snapshot> | null = null;
let scadenzaCache = 0;

/**
 * Quanto vale la cache in sviluppo.
 *
 * Un secondo: abbastanza perche' le sei chiamate di una stessa pagina
 * condividano una sola richiesta, troppo poco perche' una modifica fatta
 * in redazione resti nascosta. In build la cache non scade mai.
 */
const DURATA_CACHE_DEV = 1000;

async function scarica(): Promise<Snapshot> {
  const url = `${BASE_CMS}/api/snapshot/`;
  try {
    const risposta = await fetch(url, { signal: AbortSignal.timeout(15_000) });
    if (!risposta.ok) throw new Error(`HTTP ${risposta.status}`);
    const dati = (await risposta.json()) as Snapshot;
    console.log(
      `[contenuti] CMS letto da ${url}: ` +
        `${dati.attivita.length} attivita', ${dati.eventi.length} eventi.`,
    );
    return {
      ...SNAPSHOT_VUOTO,
      ...dati,
      impostazioni: { ...IMPOSTAZIONI_PREDEFINITE, ...dati.impostazioni },
    };
  } catch (errore) {
    console.warn(
      `[contenuti] CMS non raggiungibile su ${url} (${errore}). ` +
        `Il sito viene generato senza le sezioni dinamiche.`,
    );
    return SNAPSHOT_VUOTO;
  }
}

export function snapshot(): Promise<Snapshot> {
  // In sviluppo basta ricaricare il browser per vedere le modifiche fatte
  // nell'admin: senza questa scadenza il server di anteprima terrebbe in
  // memoria la prima lettura finche' non lo si riavvia.
  if (import.meta.env.DEV) {
    const adesso = Date.now();
    if (!inCache || adesso > scadenzaCache) {
      scadenzaCache = adesso + DURATA_CACHE_DEV;
      inCache = scarica();
    }
    return inCache;
  }

  // In build una lettura sola: tutte le pagine generate vedono lo stesso stato.
  inCache ??= scarica();
  return inCache;
}

/** Eventi di un'attivita', dal piu' vicino nel tempo. */
export async function eventiDi(slugAttivita: string): Promise<Evento[]> {
  const { eventi } = await snapshot();
  return eventi
    .filter((e) => e.attivita === slugAttivita)
    .sort((a, b) => a.inizio.localeCompare(b.inizio));
}

/** Eventi non ancora conclusi, in ordine cronologico. */
export async function prossimiEventi(limite?: number): Promise<Evento[]> {
  const { eventi } = await snapshot();
  const adesso = Date.now();
  const futuri = eventi
    .filter((e) => new Date(e.fine ?? e.inizio).getTime() >= adesso)
    .sort((a, b) => a.inizio.localeCompare(b.inizio));
  return limite ? futuri.slice(0, limite) : futuri;
}

/** Eventi marcati «in evidenza» in redazione, i piu' imminenti per primi. */
export async function eventiInEvidenza(limite = 3): Promise<Evento[]> {
  return (await prossimiEventi()).filter((e) => e.in_evidenza).slice(0, limite);
}

/** Le attivita' da mostrare nel menu, nell'ordine deciso in redazione. */
export async function attivitaInMenu(): Promise<Attivita[]> {
  const { attivita } = await snapshot();
  return attivita.filter((a) => a.in_menu).sort((a, b) => a.ordine - b.ordine);
}

export async function attivitaPerSlug(slug: string): Promise<Attivita | undefined> {
  const { attivita } = await snapshot();
  return attivita.find((a) => a.slug === slug);
}

/** Edizioni di un'attivita', dall'annata piu' recente. */
export async function edizioniDi(slugAttivita: string): Promise<Edizione[]> {
  const { edizioni } = await snapshot();
  return edizioni.filter((e) => e.attivita === slugAttivita).sort((a, b) => b.anno - a.anno);
}

/** Gli interruttori delle sezioni condizionali. */
export async function impostazioni(): Promise<Impostazioni> {
  return (await snapshot()).impostazioni;
}

/** Le realta' da mostrare in «Chi tiene in piedi il quartiere». */
export async function attivitaInHome(): Promise<Attivita[]> {
  const { attivita } = await snapshot();
  return attivita.filter((a) => a.in_home).sort((a, b) => a.ordine - b.ordine);
}

/** Le foto di una raccolta, nell'ordine deciso in redazione. */
export async function fotoDi(raccolta: string): Promise<Foto[]> {
  const { foto } = await snapshot();
  return foto.filter((f) => f.raccolta === raccolta).sort((a, b) => a.ordine - b.ordine);
}

/**
 * Gli eventi di un'attivita' raggruppati per giorno.
 * E' la forma che serve al programma della sagra: una card per giornata.
 */
export function perGiorno(eventi: Evento[]): { giorno: string; eventi: Evento[] }[] {
  const gruppi = new Map<string, Evento[]>();
  for (const evento of eventi) {
    const chiave = evento.inizio.slice(0, 10);
    (gruppi.get(chiave) ?? gruppi.set(chiave, []).get(chiave)!).push(evento);
  }
  return [...gruppi.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([giorno, elenco]) => ({
      giorno,
      eventi: elenco.sort(
        (a, b) => a.inizio.localeCompare(b.inizio) || a.ordine - b.ordine,
      ),
    }));
}

/** Gli eventi di un'attivita' divisi nelle quattro colonne stagionali. */
export function perStagione(eventi: Evento[]) {
  const stagioni = ['inverno', 'primavera', 'estate', 'autunno'] as const;
  return stagioni.map((stagione) => ({
    stagione,
    eventi: eventi
      .filter((e) => e.stagione === stagione)
      .sort((a, b) => a.inizio.localeCompare(b.inizio)),
  }));
}

/**
 * Il programma della sagra: ogni giornata con i suoi orari.
 *
 * Le giornate danno la presentazione (titolo, occhiello, colore), gli
 * eventi dello stesso giorno ne riempiono le righe.
 */
export async function programma(slugAttivita: string) {
  const { giornate } = await snapshot();
  const eventi = await eventiDi(slugAttivita);
  return giornate
    .slice()
    .sort((a, b) => a.data.localeCompare(b.data))
    .map((giornata) => ({
      giornata,
      eventi: eventi
        .filter((evento) => evento.inizio.slice(0, 10) === giornata.data)
        .sort((a, b) => a.inizio.localeCompare(b.inizio) || a.ordine - b.ordine),
    }))
    .filter((voce) => voce.eventi.length > 0);
}

/** Le sere con un piatto del giorno o una prenotazione: la tabella cucina. */
export async function menuDellaSagra(slugAttivita: string) {
  return (await eventiDi(slugAttivita)).filter(
    (evento) => evento.piatto_del_giorno || evento.prenotazione_entro,
  );
}

/* ── Le pagine di approfondimento ─────────────────────────────────────── */

/**
 * L'indirizzo di un evento sul sito.
 *
 * Nell'ordine: la pagina dedicata se la redazione l'ha scritta, altrimenti
 * il link esterno (locandina, iscrizioni), altrimenti niente — e la card
 * resta un blocco di testo, che va benissimo per «Apertura degli stand».
 */
export function percorsoEvento(evento: Evento): string | undefined {
  if (evento.articolo) return `/eventi/${evento.articolo}`;
  return evento.link || undefined;
}

/** Vero quando il link dell'evento porta fuori dal sito. */
export function eventoEsterno(evento: Evento): boolean {
  return !evento.articolo && Boolean(evento.link);
}

export async function articoli(): Promise<Articolo[]> {
  return (await snapshot()).articoli;
}

export async function articoloPerSlug(slug: string): Promise<Articolo | undefined> {
  return (await articoli()).find((voce) => voce.slug === slug);
}

/** L'evento raccontato da un articolo, se e' ancora pubblicato. */
export async function eventoDellArticolo(articolo: Articolo): Promise<Evento | undefined> {
  const { eventi } = await snapshot();
  return eventi.find((evento) => evento.slug === articolo.evento);
}

/* ── Il calendario di tutto il quartiere ──────────────────────────────── */

export interface Mese {
  /** «2026-10»: la chiave di ordinamento. */
  chiave: string;
  /** «ottobre 2026», gia' pronto per il titolo della colonna. */
  etichetta: string;
  anno: number;
  eventi: Evento[];
}

const NOMI_MESE = [
  'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
  'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre',
];

/**
 * Gli eventi raggruppati per mese, in ordine di calendario.
 *
 * E' la forma che serve alla vista «tutto il calendario»: una fascia per
 * mese, con dentro gli appuntamenti di tutte le realta' del quartiere —
 * non solo quelli della Pro Loco.
 */
export function perMese(eventi: Evento[]): Mese[] {
  const gruppi = new Map<string, Evento[]>();
  for (const evento of eventi) {
    const chiave = evento.inizio.slice(0, 7);
    const elenco = gruppi.get(chiave) ?? [];
    elenco.push(evento);
    gruppi.set(chiave, elenco);
  }
  return [...gruppi.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([chiave, elenco]) => {
      const [anno, mese] = chiave.split('-').map(Number);
      return {
        chiave,
        etichetta: `${NOMI_MESE[mese - 1]} ${anno}`,
        anno,
        eventi: elenco.sort(
          (a, b) => a.inizio.localeCompare(b.inizio) || a.ordine - b.ordine,
        ),
      };
    });
}

/**
 * Tutti gli eventi del quartiere, in ordine cronologico.
 *
 * `soloFuturi` tiene solo quelli non ancora conclusi: e' quello che serve
 * alla vista calendario, dove le date passate confondono e basta.
 */
export async function tuttiGliEventi(soloFuturi = false): Promise<Evento[]> {
  const { eventi } = await snapshot();
  const adesso = Date.now();
  return eventi
    .filter((e) => !soloFuturi || new Date(e.fine ?? e.inizio).getTime() >= adesso)
    .sort((a, b) => a.inizio.localeCompare(b.inizio) || a.ordine - b.ordine);
}

/* ── L'archivio ───────────────────────────────────────────────────────── */

/** Gli album d'archivio, dal piu' recente. */
export async function album(): Promise<Album[]> {
  const { album: raccolte } = await snapshot();
  return raccolte
    .slice()
    .sort((a, b) => (b.anno ?? 0) - (a.anno ?? 0) || a.ordine - b.ordine);
}
