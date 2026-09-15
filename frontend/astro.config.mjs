// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

const CMS_URL = (process.env.CMS_URL ?? 'http://backend:8000').replace(/\/$/, '');

/**
 * Solo in anteprima (`astro dev`): la pagina si ricarica da sola quando
 * cambia qualcosa nell'admin. Il browser chiede ogni 3 secondi un'impronta
 * dello snapshot del CMS a /__cms-versione; se cambia, ricarica. Il build
 * non ne sa nulla: niente di questo finisce nel sito pubblicato.
 */
function ricaricaDaCms() {
  return {
    name: 'ricarica-da-cms',
    hooks: {
      'astro:config:setup': ({ command, injectScript, updateConfig }) => {
        if (command !== 'dev') return;
        updateConfig({
          vite: {
            plugins: [
              {
                name: 'ricarica-da-cms',
                configureServer(server) {
                  let ultimaImpronta = null;
                  server.middlewares.use('/__cms-versione', async (_req, res) => {
                    try {
                      const risposta = await fetch(`${CMS_URL}/api/snapshot/`);
                      const dati = await risposta.json();
                      // «generato_il» cambia a ogni richiesta: non e' una modifica.
                      delete dati.generato_il;
                      const { createHash } = await import('node:crypto');
                      const impronta = createHash('sha1').update(JSON.stringify(dati)).digest('hex');
                      // Astro tiene in memoria gli indirizzi di getStaticPaths
                      // (es. /eventi/[slug]): senza svuotarla, un articolo nuovo
                      // darebbe 404 fino al riavvio dell'anteprima.
                      if (ultimaImpronta && impronta !== ultimaImpronta) {
                        for (const ambiente of Object.values(server.environments)) {
                          ambiente.hot.send({ type: 'custom', event: 'astro:content-changed' });
                        }
                      }
                      ultimaImpronta = impronta;
                      res.setHeader('Content-Type', 'text/plain');
                      res.end(impronta);
                    } catch {
                      res.statusCode = 503;
                      res.end('');
                    }
                  });
                },
              },
            ],
          },
        });
        injectScript(
          'page',
          `let impronta = null;
          setInterval(async () => {
            try {
              const r = await fetch('/__cms-versione', { cache: 'no-store' });
              if (!r.ok) return;
              const nuova = await r.text();
              if (impronta && nuova !== impronta) location.reload();
              impronta = nuova;
            } catch {}
          }, 3000);`,
        );
      },
    },
  };
}

/**
 * Sito statico: `astro build` produce HTML puro in `dist/`, che viene poi
 * caricato via FTP su hosting condiviso. Nessun runtime lato server.
 */
export default defineConfig({
  site: process.env.SITE_BASE_URL ?? 'https://canizzano.it',
  output: 'static',
  trailingSlash: 'ignore',
  integrations: [sitemap(), ricaricaDaCms()],
  build: {
    // `directory` genera /grest/index.html: URL pulite anche su hosting FTP.
    format: 'directory',
    inlineStylesheets: 'auto',
  },
  vite: {
    resolve: {
      alias: {
        '@components': new URL('./src/components', import.meta.url).pathname,
        '@layouts': new URL('./src/layouts', import.meta.url).pathname,
        '@lib': new URL('./src/lib', import.meta.url).pathname,
        '@styles': new URL('./src/styles', import.meta.url).pathname,
      },
    },
  },
});
