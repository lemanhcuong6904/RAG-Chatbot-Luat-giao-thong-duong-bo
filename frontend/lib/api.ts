export type Citation = {
  chunk_id: string;
  chunk_type: string;
  rule_id?: string | null;
  document_number?: string | null;
  document_title?: string | null;
  article?: string | null;
  article_title?: string | null;
  clause?: string | null;
  point?: string | null;
  parent_id?: string | null;
  sibling_group_id?: string | null;
  source_file: string;
  text: string;
  rule_function: string;
  coverage_status: string;
  source_quality: string;
  score?: number | null;
  score_details?: Record<string, number | string | null>;
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  warnings: string[];
  answerable: boolean;
  debug?: Record<string, unknown> | null;
};

export type DocumentItem = {
  document_id: string;
  document_number?: string | null;
  title?: string | null;
  document_type?: string | null;
  issuing_authority?: string | null;
  issue_date?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  abstract?: string | null;
  raw_pdf_url?: string | null;
  coverage_status?: string;
  source_quality?: string;
  keywords?: string[];
};

export type AdminDocumentPayload = {
  document_number: string;
  title: string;
  document_type?: string | null;
  issuing_authority?: string | null;
  issue_date?: string | null;
  effective_from?: string | null;
  abstract?: string | null;
  pdf_filename?: string | null;
  pdf_base64?: string | null;
};

export type HealthResponse = {
  status: string;
  index?: Record<string, unknown>;
  pipeline?: Record<string, unknown>;
  sanctions?: Record<string, unknown>;
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `API error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function sendChat(payload: {
  query: string;
  event_date?: string;
  as_of_date?: string;
  top_k: number;
  debug: boolean;
  pre_rag_enabled: boolean;
}) {
  return request<ChatResponse>("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDocuments() {
  return request<DocumentItem[]>("/api/v1/documents", { cache: "no-store" });
}

export function createAdminDocument(payload: AdminDocumentPayload) {
  return request<DocumentItem>("/api/v1/admin/documents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getHealth() {
  return request<HealthResponse>("/api/v1/health", { cache: "no-store" });
}
