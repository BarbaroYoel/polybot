export type Level = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface LanguageProfile {
  code: string;
  name: string;
  level: Level;
  conversationCount: number;
}

export type Author = "tutor" | "user";

export interface Message {
  id: string;
  author: Author;
  content: string;
  timeLabel: string;
  translation?: string;
  hasAudio?: boolean;
}

export interface Conversation {
  id: string;
  languageCode: string;
  title: string;
  messages: Message[];
}
