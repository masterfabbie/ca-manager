import { create } from "zustand";

type Theme = "dark" | "light";

interface AppState {
  selectedCAId: string | null;
  setSelectedCAId: (id: string | null) => void;
  theme: Theme;
  toggleTheme: () => void;
}

const storedTheme = (localStorage.getItem("theme") as Theme | null) ?? "dark";

export const useAppStore = create<AppState>((set) => ({
  selectedCAId: null,
  setSelectedCAId: (id) => set({ selectedCAId: id }),
  theme: storedTheme,
  toggleTheme: () =>
    set((s) => {
      const next: Theme = s.theme === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      document.documentElement.setAttribute("data-theme", next);
      return { theme: next };
    }),
}));
