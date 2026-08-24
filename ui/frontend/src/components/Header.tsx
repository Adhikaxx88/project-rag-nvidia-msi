export function Header() {
  return (
    <header className="top-header">
      <div>
        <h1>Fed Rate &amp; Macro News Research Terminal</h1>
        <p>
          Query the Fed policy / global macro news corpus. Answers are generated via
          hybrid retrieval (dense + BM25) over ingested articles, with inline source
          citations.
        </p>
      </div>
      <div className="status-pill">
        <span className="status-dot" />
        Hybrid RAG · Qdrant + Ollama
      </div>
    </header>
  );
}
