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
  Gavel,
  Loader2,
  Send,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { TrafficLightIcon } from "@/components/traffic-light-icon";
import { Citation, EmbeddingPreset, LlmModelPreset, PreRagMode, sendChat } from "@/lib/api";
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

type LoadingStage = "routing" | "retrieving" | "generating";
type LoadingMode = "direct" | "rag";
type Feedback = "like" | "dislike" | null;

export function ChatView({
  messages,
  onMessagesChange,
  topK,
  debug,
  preRagMode,
  llmModelPreset,
  embeddingPreset,
  structuredLookupEnabled,
}: {
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  topK: number;
  debug: boolean;
  preRagMode: PreRagMode;
  llmModelPreset: LlmModelPreset;
  embeddingPreset: EmbeddingPreset;
  structuredLookupEnabled: boolean;
}) {
  const [input, setInput] = useState("");
  const [eventDate, setEventDate] = useState(todayISO());
  const [isSending, setIsSending] = useState(false);
  const [loadingStage, setLoadingStage] = useState<LoadingStage>("routing");
  const [loadingMode, setLoadingMode] = useState<LoadingMode>("rag");
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  async function submit(question = input.trim()) {
    if (!question || isSending) return;
    setInput("");
    setError(null);
    setIsSending(true);
    setLoadingStage("routing");
    const nextLoadingMode: LoadingMode = isDirectUiPrompt(question) ? "direct" : "rag";
    setLoadingMode(nextLoadingMode);
    const startedAt = performance.now();
    const retrievalTimer =
      nextLoadingMode === "rag" ? window.setTimeout(() => setLoadingStage("retrieving"), 450) : undefined;
    const generationTimer = window.setTimeout(() => setLoadingStage("generating"), nextLoadingMode === "rag" ? 1200 : 700);

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };
    const nextMessages = [...messages, userMessage];
    onMessagesChange(nextMessages);

    try {
      const llmConfig = llmConfigForPreset(llmModelPreset);
      const response = await sendChat({
        query: question,
        event_date: eventDate,
        as_of_date: eventDate,
        top_k: topK,
        debug,
        pre_rag_enabled: preRagMode !== "rule",
        pre_rag_mode: preRagMode,
        embedding_preset: embeddingPreset,
        llm_model_preset: llmModelPreset,
        llm_provider: llmConfig.provider,
        llm_model: llmConfig.model,
        structured_lookup_enabled: structuredLookupEnabled,
      });
      const displayedCitations = citationsReferencedByAnswer(response.answer, response.citations);
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
      setSelectedCitation(displayedCitations[0] || null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không thể xử lý câu hỏi.");
      onMessagesChange(nextMessages);
    } finally {
      if (retrievalTimer !== undefined) window.clearTimeout(retrievalTimer);
      window.clearTimeout(generationTimer);
      setIsSending(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto px-4 pb-72 pt-6 md:px-8 md:pb-80">
          {messages.length === 0 ? (
            <EmptyState onPick={submit} />
          ) : (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
              <ChatHeader />
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
              {isSending && <LoadingMessage stage={loadingStage} mode={loadingMode} />}
              {error && (
                <div className="rounded-[24px] border-2 border-red-700 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-[4px_4px_0_#7f1d1d]">
                  Không gọi được API. Kiểm tra FastAPI đang chạy ở `http://127.0.0.1:8010`.
                  <div className="mt-2 text-xs font-normal">{error}</div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="absolute inset-x-0 bottom-0 flex justify-center bg-gradient-to-t from-[#fff8ef] via-[#fff8ef] to-transparent p-4 md:p-6">
          <div className="w-full max-w-3xl">
            <div className="rounded-[32px] neo-border bg-white p-3 shadow-[5px_5px_0_#1a1c1c] focus-within:border-[#ff6b00] focus-within:shadow-[7px_7px_0_#ff6b00]">
              <Textarea
                ref={inputRef}
                className="max-h-36 min-h-[62px] border-0 bg-transparent px-3 text-[15px] font-medium shadow-none focus-visible:ring-0"
                placeholder="Hỏi bất cứ luật gì, ví dụ: đi sai làn ô tô trên QL1A bị phạt sao?"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submit();
                  }
                }}
              />
              <div className="flex items-center justify-between gap-3 border-t-2 border-dashed border-[#d0c6ab] pt-3">
                <label className="inline-flex min-w-0 items-center gap-2 rounded-full border-2 border-[#1a1c1c] bg-[#fcf3e0] px-3 py-1.5 text-xs font-bold text-[#1a1c1c]">
                  <Calendar className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Ngày áp dụng</span>
                  <input
                    className="min-w-0 bg-transparent text-[#1a1c1c] outline-none"
                    type="date"
                    value={eventDate}
                    onChange={(event) => setEventDate(event.target.value)}
                  />
                </label>
                <Button disabled={!input.trim() || isSending} size="icon" onClick={() => void submit()}>
                  {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <p className="mt-3 text-center text-xs font-medium text-muted-foreground">
              AI hỗ trợ tra cứu và luôn kèm căn cứ để kiểm chứng; nội dung không thay thế tư vấn pháp lý chuyên môn.
            </p>
          </div>
        </div>
      </main>

      <EvidencePanel citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
    </div>
  );
}

function ChatHeader() {
  return (
    <div className="rounded-[28px] neo-border bg-[#ffd600] p-5 shadow-[5px_5px_0_#1a1c1c]">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl neo-border bg-white">
          <Gavel className="h-5 w-5 text-[#ff6b00]" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-extrabold leading-tight">Hỏi đáp luật giao thông</h1>
          <p className="text-sm font-semibold text-[#4d4632]">Hỏi tự nhiên, nhận câu trả lời có nguồn đối chiếu.</p>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  const suggestions = [
    {
      icon: <AlertTriangle className="h-5 w-5" />,
      title: "Vượt đèn đỏ phạt gì?",
      question: "Xe máy vượt đèn đỏ bị phạt bao nhiêu và trừ mấy điểm GPLX?",
      color: "bg-red-50",
    },
    {
      icon: <ShieldCheck className="h-5 w-5" />,
      title: "Nồng độ cồn xử sao?",
      question: "Nồng độ cồn khi lái ô tô bị xử lý thế nào?",
      color: "bg-[#eafff6]",
    },
    {
      icon: <FileText className="h-5 w-5" />,
      title: "GPLX có bao nhiêu điểm?",
      question: "GPLX có bao nhiêu điểm theo luật hiện hành?",
      color: "bg-[#fff6bf]",
    },
  ];

  return (
    <div className="mx-auto flex min-h-full w-full max-w-[1060px] flex-col items-center justify-center pb-20 text-center">
      <div className="relative mb-6">
        <div className="flex h-24 w-24 items-center justify-center rounded-full border-4 border-[#1a1c1c] bg-[#ffd600] shadow-[7px_7px_0_#1a1c1c]">
          <TrafficLightIcon className="h-14 w-14 p-1" />
        </div>
        <div className="absolute -bottom-2 -right-3 flex h-11 w-11 rotate-12 items-center justify-center rounded-full neo-border bg-[#ff6b00] text-white">
          <Sparkles className="h-5 w-5" />
        </div>
      </div>
      <h1 className="font-display mb-3 max-w-[980px] text-4xl font-extrabold leading-tight text-[#1a1c1c] md:text-5xl lg:text-[54px] lg:leading-[1.08]">
        <span className="block">Hỏi đáp luật giao thông</span>
        <span className="block">chính xác, rõ ràng, có căn cứ</span>
      </h1>
      <p className="max-w-none text-[15px] font-medium leading-7 text-muted-foreground md:whitespace-nowrap">
        Tra cứu quy định, mức phạt, điểm GPLX và căn cứ pháp lý theo cách dễ đọc hơn.
      </p>
      <div className="mt-10 grid w-full grid-cols-1 gap-5 md:grid-cols-3">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion.question}
            className={cn(
              "neo-interactive rounded-[28px] neo-border p-5 text-left shadow-[5px_5px_0_#1a1c1c]",
              suggestion.color,
            )}
            onClick={() => onPick(suggestion.question)}
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl neo-border bg-white text-[#ff6b00]">
              {suggestion.icon}
            </div>
            <div className="font-display text-lg font-extrabold text-[#1a1c1c]">{suggestion.title}</div>
            <p className="mt-2 text-sm font-medium leading-6 text-muted-foreground">{suggestion.question}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[82%] rounded-[30px] rounded-br-md neo-border bg-[#ffd600] px-5 py-3 text-[15px] font-semibold leading-7 text-[#1a1c1c] shadow-[4px_4px_0_#1a1c1c]">
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
  const displayedCitations = citationsReferencedByAnswer(message.content, message.citations || []);

  async function copyAnswer() {
    await navigator.clipboard?.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <div className="flex gap-4">
      <div className="mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl neo-border bg-[#00f5a0] shadow-[3px_3px_0_#1a1c1c]">
        <TrafficLightIcon className="h-8 w-8" />
      </div>
      <div className="min-w-0 flex-1 rounded-[30px] rounded-tl-md neo-border bg-white p-5 shadow-[5px_5px_0_#1a1c1c]">
        {message.answerable === false && (
          <div className="mb-4 rounded-2xl border-2 border-red-700 bg-red-50 p-3 text-sm font-semibold text-red-700">
            Câu trả lời chưa đủ căn cứ để xem là kết luận chắc chắn.
          </div>
        )}
        {message.warnings?.map((warning) => (
          <div key={warning} className="mb-4 flex gap-2 rounded-2xl border-2 border-amber-700 bg-amber-50 p-3 text-sm font-semibold text-amber-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{warning}</span>
          </div>
        ))}
        <div className="answer-content rounded-[22px] border-2 border-[#d0c6ab] bg-[#fff8ef] px-4 py-3">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
            {message.content}
          </ReactMarkdown>
        </div>
        {!!displayedCitations.length && (
          <div className="mt-6">
            <div className="mb-3 flex items-center gap-2 text-xs font-extrabold uppercase text-muted-foreground">
              <Gavel className="h-4 w-4 text-[#ff6b00]" />
              Căn cứ pháp lý
            </div>
            <div className="grid gap-2">
              {displayedCitations.slice(0, 8).map((citation, index) => (
                <button
                  key={`${citation.chunk_id}-${index}`}
                  className={cn(
                    "rounded-2xl border-2 border-[#1a1c1c] bg-[#fcf3e0] p-3 text-left transition-colors hover:bg-[#fff6bf]",
                    selectedCitationId === citation.chunk_id && "bg-[#ffd600] shadow-[3px_3px_0_#1a1c1c]",
                  )}
                  onClick={() => onSelectCitation(citation)}
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">[{index + 1}]</Badge>
                    <span className="truncate text-sm font-extrabold">
                      {citation.document_number || citation.document_title || "Nguồn pháp lý"}
                    </span>
                  </div>
                  <div className="mt-1 text-xs font-medium text-muted-foreground">{formatRef(citation)}</div>
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="mt-5 flex items-center justify-between gap-3 border-t-2 border-dashed border-[#d0c6ab] pt-3 text-muted-foreground">
          <div className="flex flex-wrap items-center gap-1">
            <Button className={copied ? "text-emerald-700" : ""} size="sm" variant="ghost" onClick={() => void copyAnswer()}>
              <Copy className="h-4 w-4" />
              {copied && <span className="text-xs">Đã copy</span>}
            </Button>
            <Button
              className={feedback === "like" ? "bg-[#00f5a0] text-[#002111]" : ""}
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
            <div className="shrink-0 rounded-full border-2 border-[#1a1c1c] bg-white px-2.5 py-1 text-xs font-bold text-[#1a1c1c]">
              {formatLatency(message.latencyMs)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function LoadingMessage({ stage, mode }: { stage: LoadingStage; mode: LoadingMode }) {
  return (
    <div className="flex gap-4">
      <div className="mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl neo-border bg-[#00f5a0] shadow-[3px_3px_0_#1a1c1c]">
        <TrafficLightIcon className="h-8 w-8" />
      </div>
      <div className="w-full rounded-[30px] rounded-tl-md neo-border bg-white p-5 shadow-[5px_5px_0_#1a1c1c]">
        <div className="mb-4 grid gap-2 text-sm font-semibold">
          {mode === "rag" ? (
            <>
              <StageRow active={stage === "routing"} done={stage !== "routing"} label="Đang hiểu yêu cầu" />
              <StageRow active={stage === "retrieving"} done={stage === "generating"} label="Truy xuất nguồn pháp lý" />
              <StageRow active={stage === "generating"} done={false} label="Sinh câu trả lời" />
            </>
          ) : (
            <>
              <StageRow active={stage === "routing"} done={stage === "generating"} label="Đang hiểu yêu cầu" />
              <StageRow active={stage === "generating"} done={false} label="Đang soạn phản hồi" />
            </>
          )}
        </div>
        <div className="space-y-2">
          <div className="h-3 w-3/4 rounded-full bg-[#ffd600]" />
          <div className="h-3 w-5/6 rounded-full bg-[#fcf3e0]" />
          <div className="h-3 w-1/2 rounded-full bg-[#00f5a0]" />
        </div>
      </div>
    </div>
  );
}

function isDirectUiPrompt(value: string) {
  const normalized = value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[?.!,;:]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  return new Set(["hi", "hello", "chao", "xin chao", "xin chao ban", "chao ban", "ban co the lam gi", "ban co the lam nhung gi"]).has(
    normalized,
  );
}

function llmConfigForPreset(preset: LlmModelPreset) {
  if (preset === "qwen3_5_4b_q4_k_m") {
    return { provider: "qwen_local", model: "qwen3.5-4b-q4_k_m" };
  }
  return { provider: "openai", model: "gpt-4o-mini" };
}

function citationsReferencedByAnswer(answer: string, citations: Citation[]) {
  return citations.filter((citation) => isCitationReferencedByAnswer(answer, citation));
}

function isCitationReferencedByAnswer(answer: string, citation: Citation) {
  const normalizedAnswer = normalizeVietnamese(answer);
  const documentNumber = normalizeVietnamese(citation.document_number || "");
  if (!documentNumber || !normalizedAnswer.includes(documentNumber)) {
    return false;
  }
  if (citation.article && !normalizedAnswer.includes(`dieu ${normalizeVietnamese(citation.article)}`)) {
    return false;
  }
  if (citation.clause && !normalizedAnswer.includes(`khoan ${normalizeVietnamese(citation.clause)}`)) {
    return false;
  }
  if (citation.point && !normalizedAnswer.includes(`diem ${normalizeVietnamese(citation.point)}`)) {
    return false;
  }
  return true;
}

function normalizeVietnamese(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

function StageRow({ active, done, label }: { active: boolean; done: boolean; label: string }) {
  return (
    <div className={cn("flex items-center gap-2", done ? "text-emerald-700" : active ? "text-zinc-900" : "text-muted-foreground")}>
      {done ? (
        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
      ) : active ? (
        <Loader2 className="h-4 w-4 animate-spin text-[#ff6b00]" />
      ) : (
        <span className="h-4 w-4 rounded-full border-2 border-zinc-400" />
      )}
      <span>{label}</span>
    </div>
  );
}

function EvidencePanel({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  if (!citation) return null;
  return (
    <aside className="relative hidden w-[420px] shrink-0 flex-col border-l-2 border-[#1a1c1c] bg-[#f0f4f8] shadow-[-5px_0_0_#1a1c1c] xl:flex">
      <div className="flex h-16 items-center justify-between border-b-2 border-[#1a1c1c] bg-[#ffd600] px-5">
        <div className="flex items-center gap-2 text-sm font-extrabold">
          <FileText className="h-4 w-4" />
          Căn cứ pháp lý
        </div>
        <Button size="icon" variant="ghost" onClick={onClose} aria-label="Đóng căn cứ">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-5 pb-44">
        <Badge variant="success" className="mb-3">
          {citation.document_number || citation.chunk_type}
        </Badge>
        <h2 className="mb-2 font-display text-xl font-extrabold">{citation.document_title || "Văn bản pháp luật"}</h2>
        <p className="mb-4 text-sm font-semibold text-muted-foreground">{formatRef(citation)}</p>
        <div className="rounded-[24px] neo-border bg-white p-4 text-sm leading-7 text-zinc-800 shadow-[4px_4px_0_#1a1c1c]">
          {citation.text || "Không có nội dung nguồn."}
        </div>
        <div className="mt-4 break-all text-xs font-medium text-muted-foreground">
          <div>File: {citation.source_file}</div>
          <div>Chunk: {citation.chunk_id}</div>
        </div>
        <ScoreDetails citation={citation} />
      </div>
      <TrafficPoliceMascot />
    </aside>
  );
}

function TrafficPoliceMascot() {
  return (
    <div className="pointer-events-none absolute bottom-8 left-1/2 flex -translate-x-1/2 flex-col items-center text-center text-xs font-extrabold text-muted-foreground">
      <img className="mb-1 h-24 w-24 opacity-70" src="/traffic-police.svg" alt="" aria-hidden="true" />
      <div className="rounded-2xl bg-[#f0f4f8]/90 px-3 py-1 leading-5">
        Luôn tuân thủ luật lệ
        <br />
        để bảo vệ bản thân nhé!
      </div>
    </div>
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
    <div className="mt-5 overflow-hidden rounded-[22px] neo-border bg-white">
      <div className="border-b-2 border-[#1a1c1c] bg-[#fcf3e0] px-3 py-2 text-xs font-extrabold text-zinc-800">
        Chi tiết điểm truy xuất
      </div>
      <div className="divide-y-2 divide-[#eae2cf] text-xs">
        {rows.map(([label, value, rank]) => (
          <div key={String(label)} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-3 py-2">
            <span className="font-semibold text-muted-foreground">{label}</span>
            <span className="font-mono text-zinc-900">{formatScoreValue(value)}</span>
            <span className="w-10 text-right font-mono text-muted-foreground">{rank ? `#${rank}` : ""}</span>
          </div>
        ))}
      </div>
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

function formatRef(citation: Citation) {
  const parts = [
    citation.article ? `Điều ${citation.article}` : null,
    citation.clause ? `Khoản ${citation.clause}` : null,
    citation.point ? `Điểm ${citation.point}` : null,
    citation.article_title,
  ].filter(Boolean);
  return parts.join(" - ") || citation.source_file;
}
