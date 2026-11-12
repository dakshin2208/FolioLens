/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Banner text for a public demo deployment; unset in development. */
  readonly VITE_DEMO_NOTICE?: string;
}
