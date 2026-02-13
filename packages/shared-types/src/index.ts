export type Locale = "ru" | "kz" | "en";

export interface ChatSessionCreate {
  user_id: string;
  locale: Locale;
}

export interface ChatMessageCreate {
  session_id: string;
  text: string;
  locale: Locale;
}

