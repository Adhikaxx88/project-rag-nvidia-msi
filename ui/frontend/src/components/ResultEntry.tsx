import { AlertTriangle } from "lucide-react";
import type { QueryEntry } from "../types";
import { highlightSentiment } from "../lib/highlightSentiment";
import { SourceList } from "./SourceList";
import { Skeleton } from "./Skeleton";

export function ResultEntry({ entry }: { entry: QueryEntry }) {
  return (
    <div className="entry">
      <div className="entry-query">
        <span className="prompt-marker mono">&gt;</span>
        <span className="entry-question">{entry.question}</span>
        <span className="mono entry-time">{entry.askedAt}</span>
      </div>

      <div className={`entry-answer ${entry.status === "error" ? "is-error" : ""}`}>
        {entry.status === "loading" ? (
          <Skeleton />
        ) : entry.status === "error" ? (
          <div className="answer-error">
            <AlertTriangle size={14} strokeWidth={2} />
            <span>{entry.answer}</span>
          </div>
        ) : (
          <>
            <p className="answer-text">{highlightSentiment(entry.answer)}</p>
            <SourceList sources={entry.sources} />
          </>
        )}
      </div>
    </div>
  );
}
