export function createSiteMeta({ base = '/' } = {}) {
  return {
    base,
    title: 'policy-contract',
    description: 'Documentation',
    themeConfig: {
      nav: [
        { text: 'Home', link: base || '/' },
      ],
    },
  }
}
