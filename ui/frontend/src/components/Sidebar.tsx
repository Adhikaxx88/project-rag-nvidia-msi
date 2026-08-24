import { RotateCcw } from "lucide-react";
import type { TopicFilter } from "../types";

interface SidebarProps {
  topicFilter: TopicFilter;
  onTopicFilterChange: (value: TopicFilter) => void;
  onReset: () => void;
  disabled: boolean;
}

export function Sidebar({ topicFilter, onTopicFilterChange, onReset, disabled }: SidebarProps) {
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
