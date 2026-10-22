/**
 * UI view types. They stay camelCase and independent from the API: the mapping from the contract
 * types (`src/lib/api/types.ts`) happens in the feature that consumes the data.
 */

export type Author = "tutor" | "user";

export interface Message {
  id: string;
  author: Author;
  content: string;
  timeLabel: string;
  translation?: string;
  hasAudio?: boolean;
}
