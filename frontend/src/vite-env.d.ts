/// <reference types="vite/client" />

/** Build-time configuration read by the API client (`src/lib/api/client.ts`). */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}
