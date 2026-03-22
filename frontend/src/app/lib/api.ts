import type {
  CreatePersonaRequest,
  Persona,
  PanelRecommendationResponse,
  SessionSnapshot,
  UploadedDocument,
} from "./types";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...options, credentials: "include" });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail ?? message;
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function getPersonas(): Promise<Persona[]> {
  return req<Persona[]>("/api/personas");
}

export interface RuntimeConfigPayload {
  provider: string;
  model: string;
  selector_model: string | null;
  summary_model: string | null;
  base_url: string | null;
}

export interface RuntimeConfig extends RuntimeConfigPayload {
  api_key_set: boolean;
  source: "default" | "session";
}

export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  return req<RuntimeConfig>("/api/runtime/config");
}

export async function setRuntimeConfig(payload: RuntimeConfigPayload & { api_key?: string }): Promise<RuntimeConfig> {
  return req<RuntimeConfig>("/api/runtime/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function clearRuntimeConfig(): Promise<void> {
  await req("/api/runtime/config", { method: "DELETE" });
}

export async function uploadDocument(file: File): Promise<UploadedDocument> {
  const form = new FormData();
  form.append("file", file);
  return req<UploadedDocument>("/api/documents", { method: "POST", body: form });
}

export async function deleteDocument(id: string): Promise<void> {
  await req(`/api/documents/${id}`, { method: "DELETE" });
}

export async function deletePersona(id: string): Promise<void> {
  await req(`/api/personas/${id}`, { method: "DELETE" });
}

export async function randomPersona(): Promise<Partial<Persona> & { seed_description: string }> {
  return req<Partial<Persona> & { seed_description: string }>("/api/personas/random", { method: "POST" });
}

export async function expandPersona(description: string): Promise<Partial<Persona>> {
  return req<Partial<Persona>>("/api/personas/expand", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
}

export async function createPersona(request: CreatePersonaRequest): Promise<Persona> {
  return req<Persona>("/api/personas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function updatePersona(
  id: string,
  updates: Partial<Pick<Persona, "summary" | "identity_anchor" | "epistemic_style" | "argumentative_voice" | "opinion_change_threshold">>
): Promise<Persona> {
  return req<Persona>(`/api/personas/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function recommendPanel(
  decision: string,
  panelSize: number,
  documentIds: string[]
): Promise<PanelRecommendationResponse> {
  return req<PanelRecommendationResponse>("/api/panel/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, panel_size: panelSize, document_ids: documentIds }),
  });
}

export async function createSession(
  decision: string,
  personaIds: string[],
  roundGoal: number,
  documentIds: string[]
): Promise<SessionSnapshot> {
  return req<SessionSnapshot>("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      persona_ids: personaIds,
      round_goal: roundGoal,
      document_ids: documentIds,
    }),
  });
}

export async function getSession(sessionId: string): Promise<SessionSnapshot> {
  return req<SessionSnapshot>(`/api/sessions/${sessionId}`);
}

export async function advanceSession(sessionId: string): Promise<SessionSnapshot> {
  return req<SessionSnapshot>(`/api/sessions/${sessionId}/advance`, { method: "POST" });
}

export async function interjectSession(
  sessionId: string,
  content: string
): Promise<SessionSnapshot> {
  return req<SessionSnapshot>(`/api/sessions/${sessionId}/interjections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function finishSession(sessionId: string): Promise<SessionSnapshot> {
  return req<SessionSnapshot>(`/api/sessions/${sessionId}/finish`, { method: "POST" });
}

/** Derive a display color for a persona based on its position in a list. */
export const PERSONA_COLORS = [
  "#FF6B9D", // pink
  "#E8FF8B", // lime
  "#6B9DFF", // blue
  "#FF8B6B", // orange
  "#8B6BFF", // purple
  "#FFB86B", // gold
  "#8BFFA7", // green
  "#FF6B6B", // red
  "#6BFFF0", // teal
  "#D4A59A", // terracotta
];

export function personaColor(index: number): string {
  return PERSONA_COLORS[index % PERSONA_COLORS.length];
}

/** Derive a sentiment label from a stance float. */
export function stanceLabel(stance: number | null): "for" | "against" | "undecided" {
  if (stance === null) return "undecided";
  if (stance > 0.25) return "for";
  if (stance < -0.25) return "against";
  return "undecided";
}
