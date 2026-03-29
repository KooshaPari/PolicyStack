import { defineConfig } from 'vitepress'
import { createSiteMeta } from './site-meta.mjs'

const siteMeta = createSiteMeta()

export default defineConfig({
  title: 'Policy Contract',
  description: 'Documentation',
  lang: 'en-US',
  srcDir: '.',
  outDir: '../.vitepress-dist',
  themeConfig: {
    nav: [
      { text: 'Home', link: siteMeta.base || '/' },
    ],
    sidebar: [],
    socialLinks: [],
    search: { provider: 'local' },
  },
  markdown: { lineNumbers: true },
  ignoreDeadLinks: true,
})
