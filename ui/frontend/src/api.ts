import type { AskRequestBody, AskResponse } from "./types";

export async function askQuestion(body: AskRequestBody): Promise<AskResponse> {
  const resp = await fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }

  return resp.json();
}
