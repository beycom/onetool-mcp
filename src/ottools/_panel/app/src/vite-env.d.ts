/// <reference types="vite/client" />

// Allow CSS module imports
declare module "*.css" {
  const content: Record<string, string>;
  export default content;
}

// Global injected by vite.config.ts define
declare const __PANEL_PORT__: string;
