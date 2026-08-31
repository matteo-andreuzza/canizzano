/**
 * Formattazione delle date in italiano, condivisa da tutti i componenti:
 * un evento si scrive allo stesso modo in home, nelle card e nel dettaglio.
 */

const FUSO = 'Europe/Rome';

const giornoLungo = new Intl.DateTimeFormat('it-IT', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  timeZone: FUSO,
});

const giornoCorto = new Intl.DateTimeFormat('it-IT', {
  day: 'numeric',
  month: 'short',
  timeZone: FUSO,
});

const soloOra = new Intl.DateTimeFormat('it-IT', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: FUSO,
});

const soloMese = new Intl.DateTimeFormat('it-IT', { month: 'short', timeZone: FUSO });
const soloNumeroGiorno = new Intl.DateTimeFormat('it-IT', { day: 'numeric', timeZone: FUSO });

const stessoGiorno = (a: Date, b: Date) =>
  a.toLocaleDateString('it-IT', { timeZone: FUSO }) === b.toLocaleDateString('it-IT', { timeZone: FUSO });

export interface Quando {
  inizio: string;
  fine?: string | null;
  tutto_il_giorno?: boolean;
}

/** Etichetta completa: «sabato 12 luglio, 20:30 — 23:30». */
export function quandoEsteso({ inizio, fine, tutto_il_giorno }: Quando): string {
  const da = new Date(inizio);
  const a = fine ? new Date(fine) : null;

  if (tutto_il_giorno) {
    if (a && !stessoGiorno(da, a)) return `${giornoLungo.format(da)} — ${giornoLungo.format(a)}`;
    return giornoLungo.format(da);
  }

  if (a && !stessoGiorno(da, a)) {
    return `${giornoLungo.format(da)}, ${soloOra.format(da)} — ${giornoLungo.format(a)}, ${soloOra.format(a)}`;
  }
  if (a) return `${giornoLungo.format(da)}, ${soloOra.format(da)} — ${soloOra.format(a)}`;
  return `${giornoLungo.format(da)}, ${soloOra.format(da)}`;
}

/** Etichetta compatta per le card: «12 lug · 20:30». */
export function quandoBreve({ inizio, tutto_il_giorno }: Quando): string {
  const da = new Date(inizio);
  return tutto_il_giorno ? giornoCorto.format(da) : `${giornoCorto.format(da)} · ${soloOra.format(da)}`;
}

/** Le due righe del «francobollo» data: numero del giorno e mese abbreviato. */
export function francobollo(inizio: string): { giorno: string; mese: string } {
  const da = new Date(inizio);
  return {
    giorno: soloNumeroGiorno.format(da),
    mese: soloMese.format(da).replace('.', '').toUpperCase(),
  };
}

/** Valore per l'attributo `datetime` di <time>. */
export function iso(inizio: string): string {
  return new Date(inizio).toISOString();
}

export function anno(inizio: string): number {
  return new Date(inizio).getFullYear();
}
