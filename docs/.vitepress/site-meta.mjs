export function createSiteMeta({ base = '/' } = {}) {
  return {
    base,
    title: 'Policy Contract',
    description: 'Documentation',
    themeConfig: {
      nav: [
        { text: 'Home', link: base || '/' },
      ],
    },
  }
}
