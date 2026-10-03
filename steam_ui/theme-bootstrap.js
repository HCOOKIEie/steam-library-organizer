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
  document.documentElement.style.colorScheme = theme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = theme === 'light' ? '#eef4fa' : '#0b1118';
})();
