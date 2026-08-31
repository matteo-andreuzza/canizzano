// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

/**
 * Sito statico: `astro build` produce HTML puro in `dist/`, che viene poi
 * caricato via FTP su hosting condiviso. Nessun runtime lato server.
 */
export default defineConfig({
  site: process.env.SITE_BASE_URL ?? 'https://canizzano.it',
  output: 'static',
  trailingSlash: 'ignore',
  integrations: [sitemap()],
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
