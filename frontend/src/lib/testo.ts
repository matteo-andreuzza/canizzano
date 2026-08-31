/**
 * La marcatura minima dei testi lunghi del CMS.
 *
 * Gli articoli si scrivono in una textarea dell'admin: niente editor
 * ricco, niente HTML incollato dentro al database. Bastano quattro segni,
 * gli stessi che si userebbero in un messaggio:
 *
 *     ## Un sottotitolo
 *     Un paragrafo qualsiasi. Una riga vuota separa i paragrafi.
 *     - una voce di elenco
 *     > una nota da mettere in evidenza
 *
 * Tutto il resto e' testo, e testo resta: quello che esce di qui va nei
 * componenti come contenuto, mai come `set:html`, quindi non c'e' modo di
 * iniettare marcatura dall'admin.
 */

export type Blocco =
  | { tipo: 'titolo'; testo: string }
  | { tipo: 'paragrafo'; testo: string }
  | { tipo: 'elenco'; voci: string[] }
  | { tipo: 'nota'; testo: string };

/** Da testo grezzo del CMS ai blocchi da impaginare. */
export function blocchi(corpo: string): Blocco[] {
  const risultato: Blocco[] = [];
  let paragrafo: string[] = [];
  let elenco: string[] = [];

  const chiudiParagrafo = () => {
    if (paragrafo.length) {
      risultato.push({ tipo: 'paragrafo', testo: paragrafo.join(' ') });
      paragrafo = [];
    }
  };
  const chiudiElenco = () => {
    if (elenco.length) {
      risultato.push({ tipo: 'elenco', voci: elenco });
      elenco = [];
    }
  };
  const chiudiTutto = () => {
    chiudiParagrafo();
    chiudiElenco();
  };

  for (const riga of (corpo ?? '').split(/\r?\n/)) {
    const testo = riga.trim();

    if (!testo) {
      chiudiTutto();
      continue;
    }
    if (testo.startsWith('## ')) {
      chiudiTutto();
      risultato.push({ tipo: 'titolo', testo: testo.slice(3).trim() });
      continue;
    }
    if (testo.startsWith('> ')) {
      chiudiTutto();
      risultato.push({ tipo: 'nota', testo: testo.slice(2).trim() });
      continue;
    }
    if (testo.startsWith('- ')) {
      chiudiParagrafo();
      elenco.push(testo.slice(2).trim());
      continue;
    }
    // Riga di testo normale: si attacca al paragrafo in costruzione.
    chiudiElenco();
    paragrafo.push(testo);
  }

  chiudiTutto();
  return risultato;
}

/** I paragrafi di un testo semplice (descrizioni di attivita' ed edizioni). */
export function paragrafi(testo: string): string[] {
  return (testo ?? '')
    .split(/\n\s*\n/)
    .map((pezzo) => pezzo.trim().replace(/\s*\n\s*/g, ' '))
    .filter(Boolean);
}
