import { RotateCcw } from "lucide-react";
import type { TopicFilter } from "../types";

interface SidebarProps {
  topicFilter: TopicFilter;
  onTopicFilterChange: (value: TopicFilter) => void;
  topK: number;
  onTopKChange: (value: number) => void;
  model: string;
  onModelChange: (value: string) => void;
  onReset: () => void;
  disabled: boolean;
}

export function Sidebar({
  topicFilter,
  onTopicFilterChange,
  topK,
  onTopKChange,
  model,
  onModelChange,
  onReset,
  disabled,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <h2 className="sidebar-title">Parameters</h2>

      <div className="field">
        <label htmlFor="topic-filter">Topic filter</label>
        <select
          id="topic-filter"
          value={topicFilter}
          onChange={(e) => onTopicFilterChange(e.target.value as TopicFilter)}
        >
          <option value="">All topics</option>
          <option value="fed_specific">Fed-specific (rates, FOMC, Powell, CPI/PCE)</option>
          <option value="global_macro">Global macro (ECB, China, oil, EM FX)</option>
        </select>
      </div>

      <div className="field">
        <label htmlFor="top-k">
          Context chunks (top-k) <span className="mono field-value">{topK}</span>
        </label>
        <input
          id="top-k"
          type="range"
          min={2}
          max={15}
          value={topK}
          onChange={(e) => onTopKChange(Number(e.target.value))}
        />
      </div>

      <div className="field">
        <label htmlFor="model-name">Ollama model</label>
        <input
          id="model-name"
          type="text"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          spellCheck={false}
        />
      </div>

      <button className="reset-btn" onClick={onReset} disabled={disabled} type="button">
        <RotateCcw size={13} strokeWidth={2} />
        Reset session
      </button>

      <div className="sidebar-note">
        Answers are generated only from news already ingested into Qdrant via the
        Airflow pipeline. Every claim is cited to its source article.
      </div>
    </aside>
  );
}
