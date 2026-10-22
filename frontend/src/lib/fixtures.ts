import type { Conversation, LanguageProfile, Message } from "./types";

/**
 * Datos de ejemplo de F1 — no vienen de ninguna API.
 * `EXAMPLE_DATA` se muestra en la interfaz para que nadie confunda esto con datos reales
 * (desing.md §15: «datos de ejemplo claramente identificados»).
 */
export const EXAMPLE_DATA = true;

export const LANGUAGES: LanguageProfile[] = [
  { code: "en", name: "Inglés", level: "B1", conversationCount: 4 },
  { code: "fr", name: "Francés", level: "A1", conversationCount: 2 },
  { code: "de", name: "Alemán", level: "B2", conversationCount: 0 },
];

const FRENCH_CAFE: Message[] = [
  {
    id: "m1",
    author: "tutor",
    content:
      "¡Hola! Soy tu tutor de idiomas. Podemos conversar, practicar vocabulario, corregir tus frases o simular situaciones de la vida real.\n\n¿Qué te gustaría hacer hoy?",
    timeLabel: "10:24",
  },
  {
    id: "m2",
    author: "user",
    content: "Me gustaría practicar una conversación en un café en francés.",
    timeLabel: "10:25",
  },
  {
    id: "m3",
    author: "tutor",
    content:
      "¡Perfecto! Vamos a practicar una conversación en un café. Te hablaré en francés y te ayudaré con correcciones y sugerencias.\n\n¿Estás listo? ☕",
    timeLabel: "10:25",
  },
  {
    id: "m4",
    author: "tutor",
    content: "Bonjour ! Qu'est-ce que vous aimeriez prendre ?",
    translation: "¡Buenos días! ¿Qué le gustaría tomar?",
    timeLabel: "10:26",
    hasAudio: true,
  },
];

const ENGLISH_COFFEE: Message[] = [
  {
    id: "e1",
    author: "tutor",
    content: "Hi! Ready to practise? Tell me about your day so far.",
    timeLabel: "09:12",
    hasAudio: true,
  },
  {
    id: "e2",
    author: "user",
    content: "I woke up early and went for a run before work.",
    timeLabel: "09:14",
  },
  {
    id: "e3",
    author: "tutor",
    content: "Nice. Small fix: “I woke up early and went for a run before work” is correct — try adding why you ran.",
    timeLabel: "09:14",
    hasAudio: true,
  },
];

export const CONVERSATIONS: Conversation[] = [
  { id: "c-fr-1", languageCode: "fr", title: "En un café", messages: FRENCH_CAFE },
  { id: "c-en-1", languageCode: "en", title: "Rutina diaria", messages: ENGLISH_COFFEE },
];

export const QUICK_ACTIONS = [
  "Practicar una conversación",
  "Repasar vocabulario",
  "Simular una situación",
  "Pedir una explicación",
];

export function findConversation(languageCode: string): Conversation | null {
  return CONVERSATIONS.find((conversation) => conversation.languageCode === languageCode) ?? null;
}
