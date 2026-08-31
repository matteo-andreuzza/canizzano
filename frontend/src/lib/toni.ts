/**
 * I toni del CMS tradotti in colori.
 *
 * In redazione il tono di una card e' un nome di token («accent-2-700»,
 * «blu-600»). Prima ogni componente si portava dietro la sua tabellina, e
 * aggiungere una tinta voleva dire ritoccarne quattro: adesso la coppia
 * sfondo/inchiostro sta qui e basta.
 *
 * L'inchiostro non e' dedotto: e' scelto perche' resti leggibile su quel
 * fondo, come nei prototipi.
 */

export interface Tono {
  /** Il fondo pieno della card, del disco o della pastiglia. */
  sfondo: string;
  /** Il testo sopra quel fondo. */
  inchiostro: string;
  /** L'occhiello e i testi secondari: un gradino piu' tenue. */
  tenue: string;
}

export const TONO_PREDEFINITO = 'accent-2-700';

export const TONI: Record<string, Tono> = {
  accent: { sfondo: 'var(--color-accent)', inchiostro: '#fff2eb', tenue: 'var(--color-accent-200)' },
  'accent-100': {
    sfondo: 'var(--color-accent-100)',
    inchiostro: 'var(--color-accent-800)',
    tenue: 'var(--color-accent-700)',
  },
  'accent-200': {
    sfondo: 'var(--color-accent-200)',
    inchiostro: 'var(--color-accent-700)',
    tenue: 'var(--color-accent-600)',
  },
  'accent-300': {
    sfondo: 'var(--color-accent-300)',
    inchiostro: 'var(--color-accent-800)',
    tenue: 'var(--color-accent-700)',
  },
  'accent-400': {
    sfondo: 'var(--color-accent-400)',
    inchiostro: 'var(--color-accent-900)',
    tenue: 'var(--color-accent-800)',
  },
  'accent-600': {
    sfondo: 'var(--color-accent-600)',
    inchiostro: '#fff2eb',
    tenue: 'var(--color-accent-200)',
  },
  'accent-700': {
    sfondo: 'var(--color-accent-700)',
    inchiostro: '#fff2eb',
    tenue: 'var(--color-accent-200)',
  },
  'accent-2-100': {
    sfondo: 'var(--color-accent-2-100)',
    inchiostro: 'var(--color-accent-2-800)',
    tenue: 'var(--color-accent-2-700)',
  },
  'accent-2-200': {
    sfondo: 'var(--color-accent-2-200)',
    inchiostro: 'var(--color-accent-2-800)',
    tenue: 'var(--color-accent-2-700)',
  },
  'accent-2-300': {
    sfondo: 'var(--color-accent-2-300)',
    inchiostro: 'var(--color-accent-2-900)',
    tenue: 'var(--color-accent-2-800)',
  },
  'accent-2-500': {
    sfondo: 'var(--color-accent-2-500)',
    inchiostro: 'var(--color-accent-2-900)',
    tenue: 'var(--color-accent-2-800)',
  },
  'accent-2-600': {
    sfondo: 'var(--color-accent-2-600)',
    inchiostro: 'var(--color-accent-2-100)',
    tenue: 'var(--color-accent-2-200)',
  },
  'accent-2-700': {
    sfondo: 'var(--color-accent-2-700)',
    inchiostro: 'var(--color-accent-2-100)',
    tenue: 'var(--color-accent-300)',
  },
  // L'azzurro-blu: la terza voce cromatica del sistema.
  'blu-200': {
    sfondo: 'var(--color-blu-200)',
    inchiostro: 'var(--color-blu-800)',
    tenue: 'var(--color-blu-700)',
  },
  'blu-300': {
    sfondo: 'var(--color-blu-300)',
    inchiostro: 'var(--color-blu-900)',
    tenue: 'var(--color-blu-800)',
  },
  'blu-600': {
    sfondo: 'var(--color-blu-600)',
    inchiostro: 'var(--color-blu-100)',
    tenue: 'var(--color-blu-200)',
  },
  'blu-700': {
    sfondo: 'var(--color-blu-700)',
    inchiostro: 'var(--color-blu-100)',
    tenue: 'var(--color-blu-200)',
  },
  'neutral-100': {
    sfondo: 'var(--color-neutral-100)',
    inchiostro: 'var(--color-neutral-800)',
    tenue: 'var(--color-neutral-700)',
  },
  'neutral-700': {
    sfondo: 'var(--color-neutral-700)',
    inchiostro: 'var(--color-neutral-100)',
    tenue: 'var(--color-neutral-300)',
  },
  crema: { sfondo: '#f5ead8', inchiostro: 'var(--color-accent-700)', tenue: 'var(--color-accent-600)' },
};

/** Il tono chiesto, o quello di ripiego se il nome non esiste (piu'). */
export function tono(nome: string | undefined | null): Tono {
  return (nome && TONI[nome]) || TONI[TONO_PREDEFINITO];
}

/** Come `tono`, ma restituisce `undefined` quando il nome non e' un tono. */
export function tonoOpzionale(nome: string | undefined | null): Tono | undefined {
  return nome ? TONI[nome] : undefined;
}
