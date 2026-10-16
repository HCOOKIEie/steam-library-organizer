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
  let appearance = 'p3r';
  let motion = '';
  try {
    const savedAppearance = window.localStorage.getItem('steam-organizer-appearance');
    if (['calm', 'p3r', 'traces'].includes(savedAppearance)) appearance = savedAppearance;
    motion = window.localStorage.getItem('steam-organizer-motion') || '';
  } catch (_) {}
  document.documentElement.dataset.appearance = appearance;
  document.documentElement.dataset.motion = motion === 'reduced' || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'full';
  document.documentElement.style.colorScheme = theme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = appearance === 'p3r' ? '#0654e8' : appearance === 'traces' ? (theme === 'light' ? '#eaf1ef' : '#101f27') : (theme === 'light' ? '#f8f9fb' : '#181a20');
})();
