export type TopicFilter = "" | "fed_specific" | "global_macro";

export interface Source {
  index: number;
  title: string;
  url: string;
  published: string | null;
  source: string | null;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
}

export interface AskRequestBody {
  question: string;
  top_k: number;
  topic_filter: string | null;
  model: string;
}

export type EntryStatus = "loading" | "done" | "error";

export interface QueryEntry {
  id: string;
  question: string;
  status: EntryStatus;
  answer: string;
  sources: Source[];
  askedAt: string;
}
