import { useState, type FormEvent } from "react";
import { ArrowUp } from "lucide-react";

interface ComposerProps {
  onSubmit: (question: string) => void;
  disabled: boolean;
}

export function Composer({ onSubmit, disabled }: ComposerProps) {
  const [value, setValue] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <span className="prompt-marker mono composer-marker">&gt;</span>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="e.g. What was the Fed's latest rate decision and what is the sentiment?"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        <ArrowUp size={14} strokeWidth={2.25} />
      </button>
    </form>
  );
}
