import { useState } from "react";
import { ExternalLink } from "lucide-react";
import type { Source } from "../types";

function formatDate(published: string | null): string {
  if (!published) return "date unknown";
  const d = new Date(published);
  if (Number.isNaN(d.getTime())) return published;
  return d.toISOString().slice(0, 10);
}

export function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;

  return (
    <div className="source-list">
      <button className="source-toggle" onClick={() => setOpen((v) => !v)} type="button">
        {open ? "Hide" : "Show"} {sources.length} source{sources.length !== 1 ? "s" : ""}
      </button>

      {open && (
        <table className="source-table">
          <thead>
            <tr>
              <th style={{ width: 28 }}>#</th>
              <th>Title</th>
              <th style={{ width: 150 }}>Source</th>
              <th style={{ width: 100 }}>Published</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((src) => (
              <tr key={src.index}>
                <td className="mono source-index">[{src.index}]</td>
                <td>
                  <a href={src.url} target="_blank" rel="noopener noreferrer" className="source-link">
                    {src.title}
                    <ExternalLink size={11} strokeWidth={2} />
                  </a>
                </td>
                <td className="source-name">{src.source ?? "Unknown"}</td>
                <td className="mono source-date">{formatDate(src.published)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
