import './components/lit-app.ts';
import { Theme, DEFAULT_THEME } from './theme';

function applyTheme(theme: Theme) {
  const darkTheme = 'sl-theme-dark';
  const lightTheme = 'sl-theme-light';

  if (theme === 'system') {
    const prefersDark = window.matchMedia(
      '(prefers-color-scheme: dark)'
    ).matches;
    document.documentElement.classList.toggle(darkTheme, prefersDark);
    document.documentElement.classList.toggle(lightTheme, !prefersDark);
  } else {
    document.documentElement.classList.toggle(darkTheme, theme === 'dark');
    document.documentElement.classList.toggle(lightTheme, theme === 'light');
  }
}

// Apply theme on initial load
const storedTheme = (localStorage.getItem('theme') as Theme) || DEFAULT_THEME;
applyTheme(storedTheme);

// Listen for theme changes from the settings view
window.addEventListener('theme-change', (e: CustomEvent) => {
  applyTheme(e.detail.theme);
});

// Listen for system theme changes
window
  .matchMedia('(prefers-color-scheme: dark)')
  .addEventListener('change', () => {
    const currentTheme =
      (localStorage.getItem('theme') as Theme) || DEFAULT_THEME;
    if (currentTheme === 'system') {
      applyTheme('system');
    }
  });
