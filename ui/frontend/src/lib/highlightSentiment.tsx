import type { ReactNode } from "react";

const SENTIMENT_PATTERN = /\b(Hawkish|Dovish|Neutral|Mixed)\b/g;

const CLASS_BY_WORD: Record<string, string> = {
  hawkish: "tag-hawkish",
  dovish: "tag-dovish",
  neutral: "tag-neutral",
  mixed: "tag-mixed",
};

/** Wrap sentiment keywords (Hawkish/Dovish/Neutral/Mixed) in a colored inline tag. */
export function highlightSentiment(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  SENTIMENT_PATTERN.lastIndex = 0;
  while ((match = SENTIMENT_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const word = match[0];
    const cls = CLASS_BY_WORD[word.toLowerCase()] ?? "";
    parts.push(
      <span key={`s-${key++}`} className={`sentiment-tag ${cls}`}>
        {word}
      </span>
    );
    lastIndex = SENTIMENT_PATTERN.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}
