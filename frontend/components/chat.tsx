"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Copy,
  FileText,
  Loader2,
  Send,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { TrafficLightIcon } from "@/components/traffic-light-icon";
import { Citation, sendChat } from "@/lib/api";
import { cn, todayISO } from "@/lib/utils";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  warnings?: string[];
  answerable?: boolean;
  debug?: Record<string, unknown> | null;
  latencyMs?: number;
};

type LoadingStage = "retrieving" | "generating";
type Feedback = "like" | "dislike" | null;

export function ChatView({
  messages,
  onMessagesChange,
  topK,
  debug,
}: {
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  topK: number;
  debug: boolean;
}) {
  const [input, setInput] = useState("");
  const [eventDate, setEventDate] = useState(todayISO());
  const [isSending, setIsSending] = useState(false);
  const [loadingStage, setLoadingStage] = useState<LoadingStage>("retrieving");
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  async function submit(question = input.trim()) {
    if (!question || isSending) return;
    setInput("");
    setError(null);
    setIsSending(true);
    setLoadingStage("retrieving");
    const startedAt = performance.now();
    const generationTimer = window.setTimeout(() => setLoadingStage("generating"), 900);

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };
    const nextMessages = [...messages, userMessage];
    onMessagesChange(nextMessages);

    try {
      const response = await sendChat({
        query: question,
        event_date: eventDate,
        as_of_date: eventDate,
        top_k: topK,
        debug,
      });
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        warnings: response.warnings,
        answerable: response.answerable,
        debug: response.debug,
        latencyMs: Math.round(performance.now() - startedAt),
      };
      onMessagesChange([...nextMessages, assistantMessage]);
      if (response.citations?.[0]) setSelectedCitation(response.citations[0]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không thể xử lý câu hỏi.");
      onMessagesChange(nextMessages);
    } finally {
      window.clearTimeout(generationTimer);
      setIsSending(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto px-4 pb-44 pt-6 md:px-8">
          {messages.length === 0 ? (
            <EmptyState onPick={submit} />
          ) : (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
              {messages.map((message) =>
                message.role === "user" ? (
                  <UserMessage key={message.id} message={message} />
                ) : (
                  <AssistantMessage
                    key={message.id}
                    message={message}
                    selectedCitationId={selectedCitation?.chunk_id}
                    onSelectCitation={setSelectedCitation}
                  />
                ),
              )}
              {isSending && <LoadingMessage stage={loadingStage} />}
              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  Không gọi được API. Kiểm tra FastAPI đang chạy ở `http://127.0.0.1:8010`.
                  <div className="mt-2 text-xs">{error}</div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="absolute inset-x-0 bottom-0 flex justify-center bg-gradient-to-t from-background via-background to-transparent p-4 md:p-6">
          <div className="w-full max-w-3xl">
            <div className="rounded-[18px] border bg-card p-3 shadow-soft focus-within:border-primary focus-within:ring-1 focus-within:ring-primary">
              <Textarea
                ref={inputRef}
                className="max-h-36 min-h-[62px] border-0 px-2 text-[15px] shadow-none focus-visible:ring-0"
                placeholder="Hỏi về mức phạt, điểm GPLX, hiệu lực văn bản..."
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submit();
                  }
                }}
              />
              <div className="flex items-center justify-between border-t pt-2">
                <label className="inline-flex items-center gap-2 rounded-full bg-muted/70 px-3 py-1.5 text-xs font-medium text-muted-foreground">
                  <Calendar className="h-3.5 w-3.5" />
                  Áp dụng
                  <input
                    className="bg-transparent text-zinc-700 outline-none"
                    type="date"
                    value={eventDate}
                    onChange={(event) => setEventDate(event.target.value)}
                  />
                </label>
                <Button className="rounded-xl" disabled={!input.trim() || isSending} size="icon" onClick={() => void submit()}>
                  {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Nội dung do AI hỗ trợ tra cứu và có kèm căn cứ để kiểm chứng; không thay thế tư vấn pháp lý chuyên môn.
            </p>
          </div>
        </div>
      </main>

      <EvidencePanel citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  const suggestions = [
    "Xe máy vượt đèn đỏ bị phạt bao nhiêu và trừ mấy điểm?",
    "GPLX có bao nhiêu điểm theo luật hiện hành?",
    "Nồng độ cồn khi lái ô tô bị xử lý thế nào?",
  ];

  return (
    <div className="mx-auto flex min-h-full w-full max-w-[860px] flex-col items-center justify-center pb-20 text-center">
      <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft text-primary">
        <TrafficLightIcon className="h-8 w-8 p-1" />
      </div>
      <h1 className="mb-3 text-3xl font-semibold tracking-tight text-zinc-950 md:text-4xl">
        Hỏi luật giao thông, dễ hiểu hơn.
      </h1>
      <p className="max-w-xl text-[15px] leading-7 text-muted-foreground">
        Tra cứu quy định, mức phạt, điểm GPLX và căn cứ pháp lý từ hệ thống văn bản giao thông đường bộ.
      </p>
      <div className="mt-10 grid w-full grid-cols-1 gap-4 md:grid-cols-3">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            className="rounded-xl border bg-card p-5 text-left shadow-sm transition-colors hover:border-primary/50 hover:bg-blue-50"
            onClick={() => onPick(suggestion)}
          >
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-primary">
              <FileText className="h-5 w-5" />
            </div>
            <span className="text-sm font-medium leading-6 text-zinc-900">{suggestion}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[78%] rounded-2xl rounded-tr-sm border border-blue-700 bg-blue-600 px-5 py-3 text-[15px] leading-7 text-white shadow-sm">
        {message.content}
      </div>
    </div>
  );
}

function AssistantMessage({
  message,
  selectedCitationId,
  onSelectCitation,
}: {
  message: ChatMessage;
  selectedCitationId?: string;
  onSelectCitation: (citation: Citation) => void;
}) {
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [copied, setCopied] = useState(false);

  async function copyAnswer() {
    await navigator.clipboard?.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <div className="flex gap-4">
      <div className="mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-emerald-100 bg-emerald-50 shadow-sm">
        <TrafficLightIcon className="h-9 w-9" />
      </div>
      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-emerald-100 bg-white p-5 shadow-sm">
        {message.answerable === false && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            Câu trả lời chưa đủ căn cứ để xem là kết luận chắc chắn.
          </div>
        )}
        {message.warnings?.map((warning) => (
          <div key={warning} className="mb-4 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{warning}</span>
          </div>
        ))}
        <div className="answer-content rounded-xl border border-zinc-100 bg-zinc-50/60 px-4 py-3">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
            {message.content}
          </ReactMarkdown>
        </div>
        {!!message.citations?.length && (
          <div className="mt-6">
            <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Căn cứ pháp lý</div>
            <div className="grid gap-2">
              {message.citations.slice(0, 8).map((citation, index) => (
                <button
                  key={`${citation.chunk_id}-${index}`}
                  className={cn(
                    "rounded-lg border bg-card p-3 text-left transition-colors hover:border-primary/50 hover:bg-blue-50",
                    selectedCitationId === citation.chunk_id && "border-primary bg-blue-50",
                  )}
                  onClick={() => onSelectCitation(citation)}
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">[{index + 1}]</Badge>
                    <span className="truncate text-sm font-medium">
                      {citation.document_number || citation.document_title || "Nguồn pháp lý"}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{formatRef(citation)}</div>
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="mt-5 flex items-center justify-between gap-3 border-t pt-3 text-muted-foreground">
          <div className="flex items-center gap-1">
            <Button className={copied ? "text-emerald-600" : ""} size="sm" variant="ghost" onClick={() => void copyAnswer()}>
              <Copy className="h-4 w-4" />
              {copied && <span className="text-xs">Đã copy</span>}
            </Button>
            <Button
              className={feedback === "like" ? "bg-emerald-50 text-emerald-700" : ""}
              size="sm"
              variant="ghost"
              onClick={() => setFeedback(feedback === "like" ? null : "like")}
            >
              <ThumbsUp className="h-4 w-4" />
              {feedback === "like" && <span className="text-xs">Hữu ích</span>}
            </Button>
            <Button
              className={feedback === "dislike" ? "bg-red-50 text-red-700" : ""}
              size="sm"
              variant="ghost"
              onClick={() => setFeedback(feedback === "dislike" ? null : "dislike")}
            >
              <ThumbsDown className="h-4 w-4" />
              {feedback === "dislike" && <span className="text-xs">Cần sửa</span>}
            </Button>
          </div>
          {message.latencyMs !== undefined && (
            <div className="shrink-0 rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-500">
              {formatLatency(message.latencyMs)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function LoadingMessage({ stage }: { stage: LoadingStage }) {
  return (
    <div className="flex gap-4">
      <div className="mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-emerald-100 bg-emerald-50 shadow-sm">
        <TrafficLightIcon className="h-9 w-9" />
      </div>
      <div className="w-full rounded-2xl rounded-tl-sm border border-emerald-100 bg-white p-5 shadow-sm">
        <div className="mb-4 grid gap-2 text-sm">
          <StageRow
            active={stage === "retrieving"}
            done={stage === "generating"}
            label="Truy xuất nguồn pháp lý"
          />
          <StageRow
            active={stage === "generating"}
            done={false}
            label="Sinh câu trả lời"
          />
        </div>
        <div className="space-y-2">
          <div className="h-3 w-3/4 rounded bg-zinc-200" />
          <div className="h-3 w-5/6 rounded bg-zinc-200" />
          <div className="h-3 w-1/2 rounded bg-zinc-200" />
        </div>
      </div>
    </div>
  );
}

function StageRow({ active, done, label }: { active: boolean; done: boolean; label: string }) {
  return (
    <div className={cn("flex items-center gap-2", done ? "text-emerald-700" : active ? "text-zinc-800" : "text-muted-foreground")}>
      {done ? (
        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
      ) : active ? (
        <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
      ) : (
        <span className="h-4 w-4 rounded-full border border-zinc-300" />
      )}
      <span>{label}</span>
    </div>
  );
}

function EvidencePanel({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  if (!citation) return null;
  return (
    <aside className="hidden w-[420px] shrink-0 flex-col border-l bg-card xl:flex">
      <div className="flex h-14 items-center justify-between border-b px-5">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <BookIcon />
          Căn cứ pháp lý
        </div>
        <Button size="icon" variant="ghost" onClick={onClose} aria-label="Đóng căn cứ">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-5">
        <Badge variant="secondary" className="mb-3">
          {citation.document_number || citation.chunk_type}
        </Badge>
        <h2 className="mb-2 text-base font-semibold">{citation.document_title || "Văn bản pháp luật"}</h2>
        <p className="mb-4 text-sm text-muted-foreground">{formatRef(citation)}</p>
        <div className="rounded-lg border bg-zinc-50 p-4 text-sm leading-7 text-zinc-800">
          {citation.text || "Không có nội dung nguồn."}
        </div>
        <div className="mt-4 text-xs text-muted-foreground">
          <div>File: {citation.source_file}</div>
          <div>Chunk: {citation.chunk_id}</div>
        </div>
        <ScoreDetails citation={citation} />
      </div>
    </aside>
  );
}

function ScoreDetails({ citation }: { citation: Citation }) {
  const details = citation.score_details || {};
  const rows = [
    ["BM25 raw", details.bm25_score, details.bm25_rank],
    ["Dense similarity", details.dense_score, details.dense_rank],
    ["RRF hybrid", details.rrf_score, details.rrf_score_rank],
    ["Sau heuristic", details.preference_score, details.preference_score_rank],
    ["Trước reranker", details.pre_reranker_score, details.pre_reranker_score_rank],
    ["Reranker", details.reranker_score, details.reranker_score_rank],
    ["Score cuối", details.final_citation_score ?? citation.score, null],
  ].filter((row) => row[1] !== undefined && row[1] !== null);

  if (!rows.length) return null;

  return (
    <div className="mt-5 rounded-lg border">
      <div className="border-b bg-zinc-50 px-3 py-2 text-xs font-semibold text-zinc-700">Chi tiết điểm truy xuất</div>
      <div className="divide-y text-xs">
        {rows.map(([label, value, rank]) => (
          <div key={String(label)} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-3 py-2">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-mono text-zinc-900">{formatScoreValue(value)}</span>
            <span className="w-10 text-right font-mono text-muted-foreground">{rank ? `#${rank}` : ""}</span>
          </div>
        ))}
      </div>
      {(details.context_reason || details.context_anchor_chunk_id) && (
        <div className="border-t bg-zinc-50 px-3 py-2 text-xs text-muted-foreground">
          {details.context_reason && <div>Context: {String(details.context_reason)}</div>}
          {details.context_anchor_chunk_id && <div>Anchor: {String(details.context_anchor_chunk_id)}</div>}
        </div>
      )}
    </div>
  );
}

function formatScoreValue(value: unknown) {
  return typeof value === "number" ? value.toFixed(6) : String(value);
}

function formatLatency(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function BookIcon() {
  return <FileText className="h-4 w-4" />;
}

function formatRef(citation: Citation) {
  const parts = [
    citation.article ? `Điều ${citation.article}` : null,
    citation.clause ? `Khoản ${citation.clause}` : null,
    citation.point ? `Điểm ${citation.point}` : null,
    citation.article_title,
  ].filter(Boolean);
  return parts.join(" - ") || citation.source_file;
}
