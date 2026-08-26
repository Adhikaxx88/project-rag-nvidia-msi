import { RotateCcw } from "lucide-react";
import type { TopicFilter } from "../types";

export type PipelineStatus = "idle" | "pending" | "error";

interface SidebarProps {
  topicFilter: TopicFilter;
  onTopicFilterChange: (value: TopicFilter) => void;
  onReset: () => void;
  disabled: boolean;
  queryCount: number;
  lastQueryAt: string | null;
  status: PipelineStatus;
}

const STATUS_LABEL: Record<PipelineStatus, string> = {
  idle: "Ready",
  pending: "Querying…",
  error: "Last query failed",
};

export function Sidebar({
  topicFilter,
  onTopicFilterChange,
  onReset,
  disabled,
  queryCount,
  lastQueryAt,
  status,
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

      <button className="reset-btn" onClick={onReset} disabled={disabled} type="button">
        <RotateCcw size={13} strokeWidth={2} />
        Reset session
      </button>

      <div className="sidebar-section">
        <h3 className="sidebar-section-title">Session</h3>
        <div className="stat-row">
          <span className="stat-label">Queries asked</span>
          <span className="stat-value mono">{queryCount}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Last query</span>
          <span className="stat-value mono">{lastQueryAt ?? "—"}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Status</span>
          <span className="stat-value">
            <span className={`status-dot-inline dot-${status}`} />
            {STATUS_LABEL[status]}
          </span>
        </div>
      </div>

      <div className="sidebar-note">
        Answers are generated only from news articles already collected by our
        automated pipeline. Every claim is cited to its source article.
      </div>
    </aside>
  );
}
