/**
 * Configurazione del sito: le cose che si ripetono su ogni pagina.
 *
 * Navigazione, contatti e footer vivono qui e non nei componenti, cosi'
 * cambiare un numero di telefono e' una riga sola per tutto il sito.
 */

export type ChiavePagina =
  | 'home'
  | 'calendario'
  | 'proloco'
  | 'sagra'
  | 'grest'
  | 'storia'
  | 'archivio'
  /** Coro, chierichetti, Circolo NOI: i gruppi senza una pagina tutta loro. */
  | 'gruppi'
  | 'pastoria'
  /** Le pagine di approfondimento degli eventi: `/eventi/<slug>`. */
  | 'evento';

export interface VoceMenu {
  testo: string;
  href: string;
  /** Presente solo sulle voci che puntano a una pagina del sito. */
  chiave?: ChiavePagina;
  esterno?: boolean;
}

export interface Azione {
  testo: string;
  href: string;
  esterno?: boolean;
  /** Sfondo del bottone: le pagine verdi non usano la terracotta. */
  sfondo?: string;
}

export const SITO = {
  nome: 'canizzano.it',
  titolo: 'Canizzano',
  descrizione:
    'Il sito del quartiere di Canizzano, a Treviso: sagra, Pro Loco, Grest, parrocchia e storia del paese dei canneti.',
} as const;

export const CONTATTI = {
  indirizzo: 'Via Canizzano, 31100 Treviso',
  email: 'info@canizzano.it',
  proLocoTelefono: '328 2143250',
  proLocoEmail: 'proloco@canizzano.it',
  proLocoTel: 'tel:+393282143250',
  parrocchiaTelefono: '0422 379269',
  redazioneTelefono:'3801510324',
  redazioneEmail:'canizzano@altervista.org',
  parrocchiaTel: 'tel:+390422379269',
  parrocchiaSito: 'https://www.parrocchiacanizzano.it',
  parrocchiaEmail: 'canizzano@diocesitv.it',
  grestEmail: 'canizzano.grest2021@gmail.com',
  parcoSile: 'https://www.parcosile.it',
  // Recapiti pubblicati dalla Federazione Italiana Tradizioni Popolari.
  pastoriaTelefono: '347 2119331',
  pastoriaTel: 'tel:+393472119331',
  pastoriaEmail: 'pastoriaborgofuro@libero.it',
  pastoriaFacebook: 'https://www.facebook.com/pastoriaborgofuro/',
  pastoriaInstagram: 'https://www.instagram.com/pastoriadelborgofuro/',
  pastoriaYoutube: 'https://www.youtube.com/channel/UC3coKr0ssD6G1svY36UvPCg',
} as const;

/** Le rotte del sito: un solo posto da cambiare se un indirizzo si sposta. */
export const ROTTE: Record<ChiavePagina, string> = {
  home: '/',
  calendario: '/calendario',
  proloco: '/proloco',
  sagra: '/sagra',
  grest: '/grest',
  storia: '/storia',
  archivio: '/archivio',
  gruppi: '/gruppi',
  pastoria: '/pastoria',
  evento: '/eventi',
};

/**
 * Il menu di ogni pagina.
 *
 * Le ancore (`#…`) restano interne alla pagina; le voci con `chiave`
 * puntano a un'altra pagina e diventano non-link quando sono la corrente.
 */
export const MENU: Record<ChiavePagina, VoceMenu[]> = {
  home: [
    { testo: 'Calendario', href: ROTTE.calendario, chiave: 'calendario' },
    { testo: 'Pro Loco', href: ROTTE.proloco, chiave: 'proloco' },
    { testo: 'Parrocchia', href: '#parrocchia' },
    { testo: 'Grest', href: ROTTE.grest, chiave: 'grest' },
    { testo: 'Il quartiere', href: '#quartiere' },
  ],
  calendario: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Cosa c’è adesso', href: '#prossimi' },
    { testo: 'Tutto l’anno', href: '#anno' },
    { testo: 'Sagra', href: ROTTE.sagra, chiave: 'sagra' },
    { testo: 'Pro Loco', href: ROTTE.proloco, chiave: 'proloco' },
  ],
  proloco: [
    { testo: 'Pro Loco', href: ROTTE.proloco, chiave: 'proloco' },
    { testo: "L'anno", href: '#anno' },
    { testo: 'I nostri eventi', href: '#eventi' },
    { testo: 'Foto', href: '#foto' },
    { testo: 'Sagra', href: ROTTE.sagra, chiave: 'sagra' },
  ],
  sagra: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Programma', href: '#programma' },
    { testo: 'Cucina', href: '#cucina' },
    { testo: 'Come arrivare', href: '#come-arrivare' },
    { testo: 'Pro Loco', href: ROTTE.proloco, chiave: 'proloco' },
  ],
  grest: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Cosa si fa', href: '#cosa-si-fa' },
    { testo: 'La giornata', href: '#giornata' },
    { testo: 'Animatori', href: '#animatori' },
    { testo: 'Pro Loco', href: ROTTE.proloco, chiave: 'proloco' },
  ],
  storia: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Linea del tempo', href: '#tempo' },
    { testo: 'La chiesa', href: '#chiesa' },
    { testo: 'Archivio', href: ROTTE.archivio, chiave: 'archivio' },
    { testo: 'Pro Loco', href: ROTTE.proloco, chiave: 'proloco' },
  ],
  archivio: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Le raccolte', href: '#raccolte' },
    { testo: 'Come funziona', href: '#come-funziona' },
    { testo: 'Storia', href: ROTTE.storia, chiave: 'storia' },
    { testo: 'Calendario', href: ROTTE.calendario, chiave: 'calendario' },
  ],
  gruppi: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Coro', href: '#coro' },
    { testo: 'Chierichetti', href: '#chierichetti' },
    { testo: 'Circolo NOI', href: '#noi' },
    { testo: 'Calendario', href: ROTTE.calendario, chiave: 'calendario' },
  ],
  pastoria: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Il nome', href: '#nome' },
    { testo: 'L’anno', href: '#anno' },
    { testo: 'Il casone', href: '#casone' },
    { testo: 'Storia', href: ROTTE.storia, chiave: 'storia' },
  ],
  evento: [
    { testo: 'Home', href: ROTTE.home, chiave: 'home' },
    { testo: 'Calendario', href: ROTTE.calendario, chiave: 'calendario' },
    { testo: 'Pro Loco', href: ROTTE.proloco, chiave: 'proloco' },
    { testo: 'Sagra', href: ROTTE.sagra, chiave: 'sagra' },
    { testo: 'Il quartiere', href: ROTTE.storia, chiave: 'storia' },
  ],
};

/** Il bottone di chiamata all'azione in testata, uno per pagina. */
export const AZIONE_TESTATA: Record<ChiavePagina, Azione> = {
  home: { testo: 'Calendario', href: ROTTE.calendario },
  calendario: { testo: 'Segnala un evento', href: 'mailto:info@canizzano.it' },
  proloco: { testo: 'Diventa socio', href: '#socio', sfondo: 'var(--color-accent-2-700)' },
  sagra: { testo: 'Prenota la cena', href: '#cucina' },
  grest: { testo: 'Iscriviti', href: '#iscrizioni', sfondo: 'var(--color-accent-2-600)' },
  storia: { testo: 'Porta le tue foto', href: ROTTE.archivio },
  archivio: { testo: 'Manda le tue foto', href: 'mailto:proloco@canizzano.it' },
  gruppi: { testo: 'Tutto il calendario', href: ROTTE.calendario },
  pastoria: { testo: 'Scrivi alla Pastoria', href: 'mailto:pastoriaborgofuro@libero.it' },
  evento: { testo: 'Tutto il calendario', href: ROTTE.calendario },
};

/** Il footer, identico su tutte le pagine (handoff: «IDENTICO su tutte»). */
export const PIE_PAGINA = {
  intro:
    'Il sito del quartiere, mantenuto da volontari: Pro Loco Cannetum, parrocchia della Visitazione e Circolo NOI. Se manca qualcosa, segnalalo: si aggiunge.',
  colonne: [
    {
      titolo: 'Le pagine',
      voci: [
        { testo: 'Home', href: ROTTE.home },
        { testo: 'Il calendario del quartiere', href: ROTTE.calendario },
        { testo: "Pro Loco tutto l'anno", href: ROTTE.proloco },
        { testo: "La sagra d'ottobre", href: ROTTE.sagra },
        { testo: 'Grest', href: ROTTE.grest },
        { testo: 'Storia di Canizzano', href: ROTTE.storia },
        { testo: 'Archivio fotografico', href: ROTTE.archivio },
        { testo: 'Coro, chierichetti e NOI', href: ROTTE.gruppi },
      ],
    },
    {
      titolo: 'Chi organizza',
      voci: [
        { testo: 'Parrocchia della Visitazione', href: CONTATTI.parrocchiaSito, esterno: true },
        { testo: 'A.R.C. Cannetum · Pro Loco', href: ROTTE.proloco },
        { testo: 'Circolo NOI di Canizzano', href: ROTTE.gruppi + '#noi' },
        { testo: 'Pastoria del Borgo Furo', href: ROTTE.pastoria },
        { testo: 'Principato di Canizzano', href: ROTTE.storia + '#principato' },
      ],
    },
    {
      titolo: 'Contatti',
      voci: [
        { testo: CONTATTI.indirizzo, href: '' },
        { testo: `Pro Loco · ${CONTATTI.proLocoTelefono}`, href: CONTATTI.proLocoTel },
        { testo: `Parrocchia · ${CONTATTI.parrocchiaTelefono}`, href: CONTATTI.parrocchiaTel },
        { testo: `Redazione · ${CONTATTI.redazioneTelefono}`, href: CONTATTI.parrocchiaTel },
        { testo: CONTATTI.email, href: `mailto:${CONTATTI.email}` },
      ],
    },
  ],
  chiusura: 'canizzano.it — made with ❤️ by',
  chiusuraAutore: { testo: 'Matteo', href: 'https://github.com/matteo-andreuzza' },
  social: 'Instagram · Facebook · WhatsApp',
} as const;
