(() => {
  const key = 'steam-organizer-theme';
  let theme = '';
  try {
    const saved = window.localStorage.getItem(key);
    if (saved === 'dark' || saved === 'light') theme = saved;
  } catch (_) {}
  if (!theme) {
    theme = window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  document.documentElement.dataset.theme = theme;
  let appearance = 'vault';
  let motion = '';
  try {
    const savedAppearance = window.localStorage.getItem('steam-organizer-appearance');
    if (savedAppearance === 'traces') {
      appearance = 'p5r';
      window.localStorage.setItem('steam-organizer-appearance', 'p5r');
    } else if (['vault', 'calm', 'p3r', 'p5r'].includes(savedAppearance)) appearance = savedAppearance;
    motion = window.localStorage.getItem('steam-organizer-motion') || '';
  } catch (_) {}
  document.documentElement.dataset.appearance = appearance;
  document.documentElement.dataset.motion = motion === 'reduced' || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'full';
  document.documentElement.style.colorScheme = theme;
  document.documentElement.dataset.vaultView = 'collection';
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = appearance === 'vault' ? (theme === 'light' ? '#eef2f1' : '#090d10') : appearance === 'p3r' ? '#0654e8' : appearance === 'p5r' ? (theme === 'light' ? '#e21d30' : '#c90d25') : (theme === 'light' ? '#f5f5f7' : '#161618');
})();
