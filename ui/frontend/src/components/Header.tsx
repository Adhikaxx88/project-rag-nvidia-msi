import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

function clockLabel(): string {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

interface HeaderProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export function Header({ theme, onToggleTheme }: HeaderProps) {
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
          Ask questions about Fed policy and global macroeconomic news. Every answer is
          backed by real news articles, with sources cited inline.
        </p>
      </div>
      <div className="top-header-meta">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="header-clock mono">{time}</span>
          <button
            type="button"
            className="theme-toggle"
            onClick={onToggleTheme}
            aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
          >
            {theme === "light" ? <Moon size={14} strokeWidth={2} /> : <Sun size={14} strokeWidth={2} />}
          </button>
        </div>
        <div className="status-pill">
          <span className="status-dot" />
          Live · AI-Powered
        </div>
      </div>
    </header>
  );
}
