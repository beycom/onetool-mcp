import { createContext, useContext } from "react";

export interface DisplaySettings {
  wrapText: boolean;
  hideWhitespace: boolean;
  codeTheme: "light" | "dark";
}

const DisplaySettingsContext = createContext<DisplaySettings>({
  wrapText: false,
  hideWhitespace: true,
  codeTheme: "dark",
});

export const DisplaySettingsProvider = DisplaySettingsContext.Provider;

export function useDisplaySettings(): DisplaySettings {
  return useContext(DisplaySettingsContext);
}
