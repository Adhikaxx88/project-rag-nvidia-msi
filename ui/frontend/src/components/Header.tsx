import { useEffect, useState } from "react";

function clockLabel(): string {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function Header() {
  const [time, setTime] = useState(clockLabel);

  useEffect(() => {
    const id = setInterval(() => setTime(clockLabel()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="top-header">
      <div>
        <span className="top-header-kicker">Research Terminal</span>
        <h1>Fed Rate &amp; Macro News</h1>
        <p>
          Query the Fed policy / global macro news corpus. Answers are generated via
          hybrid retrieval (dense + BM25) over ingested articles, with inline source
          citations.
        </p>
      </div>
      <div className="top-header-meta">
        <span className="header-clock mono">{time}</span>
        <div className="status-pill">
          <span className="status-dot" />
          Hybrid RAG · Qdrant + Ollama
        </div>
      </div>
    </header>
  );
}
