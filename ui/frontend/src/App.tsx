import { useEffect, useRef, useState } from "react";
import { TerminalSquare } from "lucide-react";
import "./App.css";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { Composer } from "./components/Composer";
import { ResultEntry } from "./components/ResultEntry";
import { askQuestion } from "./api";
import type { QueryEntry, TopicFilter } from "./types";

const QUICK_PROMPTS = [
  "What was the Fed's latest interest rate decision?",
  "Is recent FOMC commentary hawkish or dovish?",
  "What's the latest on U.S. inflation (CPI/PCE)?",
  "How are global macro conditions (ECB, China, oil) affecting markets?",
];

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function nowLabel(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function App() {
  const [entries, setEntries] = useState<QueryEntry[]>([]);
  const [topicFilter, setTopicFilter] = useState<TopicFilter>("");
  const [pending, setPending] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight });
  }, [entries]);

  async function handleAsk(question: string) {
    const id = makeId();
    setEntries((prev) => [
      ...prev,
      { id, question, status: "loading", answer: "", sources: [], askedAt: nowLabel() },
    ]);
    setPending(true);

    try {
      const data = await askQuestion({
        question,
        topic_filter: topicFilter || null,
      });
      setEntries((prev) =>
        prev.map((e) =>
          e.id === id ? { ...e, status: "done", answer: data.answer, sources: data.sources } : e
        )
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setEntries((prev) =>
        prev.map((e) =>
          e.id === id
            ? { ...e, status: "error", answer: `Request failed: ${message}` }
            : e
        )
      );
    } finally {
      setPending(false);
    }
  }

  const lastEntry = entries[entries.length - 1];
  const pipelineStatus = pending ? "pending" : lastEntry?.status === "error" ? "error" : "idle";

  return (
    <div className="layout">
      <Sidebar
        topicFilter={topicFilter}
        onTopicFilterChange={setTopicFilter}
        onReset={() => setEntries([])}
        disabled={pending}
        queryCount={entries.length}
        lastQueryAt={lastEntry?.askedAt ?? null}
        status={pipelineStatus}
      />

      <main className="main">
        <Header />

        <div className="terminal" ref={terminalRef}>
          {entries.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-heading">
                <TerminalSquare size={16} strokeWidth={2} />
                <p>No queries yet in this session.</p>
              </div>
              <p className="empty-state-hint">
                Ask about Fed rate decisions, FOMC statements, inflation data, or global
                macro conditions. Every answer is grounded in ingested source articles.
              </p>
              <div className="quick-prompts-label">Quick start</div>
              <div className="quick-prompts">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="quick-prompt-btn"
                    onClick={() => handleAsk(prompt)}
                    disabled={pending}
                  >
                    <span className="prompt-marker mono">&gt;</span>
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            entries.map((entry) => <ResultEntry key={entry.id} entry={entry} />)
          )}
        </div>

        <Composer onSubmit={handleAsk} disabled={pending} />
      </main>
    </div>
  );
}

export default App;
