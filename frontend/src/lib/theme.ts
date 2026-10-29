/** Light / dark theme. Light is the default; the choice is remembered per browser. */
const KEY = "foliolens.theme";
export type Theme = "light" | "dark";

export function getTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function applyTheme(t: Theme) {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(KEY, t);
  } catch {
    /* storage unavailable: the theme just won't be remembered */
  }
}
