"use client";

import { useEffect, useState } from "react";
import { Activity, Gavel, ListOrdered, Network, RefreshCw, Search, SlidersHorizontal, Terminal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmbeddingPreset, HealthResponse, LlmModelPreset, PreRagMode, getHealth } from "@/lib/api";

export function DeveloperView({
  topK,
  debug,
  preRagMode,
  llmModelPreset,
  embeddingPreset,
  structuredLookupEnabled,
  onTopKChange,
  onDebugChange,
  onPreRagModeChange,
  onLlmModelPresetChange,
  onEmbeddingPresetChange,
  onStructuredLookupEnabledChange,
}: {
  topK: number;
  debug: boolean;
  preRagMode: PreRagMode;
  llmModelPreset: LlmModelPreset;
  embeddingPreset: EmbeddingPreset;
  structuredLookupEnabled: boolean;
  onTopKChange: (value: number) => void;
  onDebugChange: (value: boolean) => void;
  onPreRagModeChange: (value: PreRagMode) => void;
  onLlmModelPresetChange: (value: LlmModelPreset) => void;
  onEmbeddingPresetChange: (value: EmbeddingPreset) => void;
  onStructuredLookupEnabledChange: (value: boolean) => void;
}) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setHealth(await getHealth());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không kiểm tra được hệ thống.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const pipeline = health?.pipeline ?? {};
  const sanctions = health?.sanctions ?? {};
  const structuredLookup = health?.structured_lookup ?? {};

  return (
    <main className="flex-1 overflow-y-auto p-6 md:p-8">
      <div className="mx-auto max-w-[1200px] space-y-7">
        <div className="flex flex-col justify-between gap-4 rounded-[32px] neo-border bg-white p-6 shadow-[6px_6px_0_#1a1c1c] sm:flex-row sm:items-start">
          <div>
            <h1 className="font-display text-4xl font-extrabold tracking-tight text-[#1a1c1c]">Hệ thống RAG</h1>
            <p className="mt-2 max-w-2xl text-sm font-semibold leading-6 text-muted-foreground">
              Theo dõi pipeline truy xuất và bật tùy chọn nâng cao cho phiên hiện tại.
            </p>
          </div>
          <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Tải lại ngay
          </Button>
        </div>

        {error && <div className="rounded-[24px] border-2 border-red-700 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-[4px_4px_0_#7f1d1d]">{error}</div>}

        <div className="grid grid-cols-1 gap-5 md:grid-cols-4">
          <StatusCard
            icon={<Search />}
            title="Lexical BM25"
            active={Boolean(pipeline.bm25_active)}
            description="Tìm theo từ khóa, số hiệu văn bản và cụm pháp lý."
            tone="yellow"
          />
          <StatusCard
            icon={<Network />}
            title="Semantic Dense"
            active={Boolean(pipeline.dense_active)}
            description={(pipeline.dense_error as string) || "Tìm kiếm bằng embedding để hiểu ý hỏi tự nhiên."}
            tone="mint"
          />
          <StatusCard
            icon={<ListOrdered />}
            title="Reranker"
            active={Boolean(pipeline.reranker_active)}
            description={(pipeline.reranker_error as string) || "Xếp hạng lại kết quả truy xuất trước khi trả lời."}
            tone="orange"
          />
          <StatusCard
            icon={<Gavel />}
            title="Rule-based Structured Lookup"
            active={Boolean(structuredLookup.enabled && (structuredLookup.fact_enabled || structuredLookup.sanction_enabled))}
            description="Trạng thái master switch cho Structured Fact và Structured Sanction của backend."
            tone="mint"
          />
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[380px_1fr]">
          <Card className="bg-white">
            <CardHeader>
              <CardTitle className="flex items-center gap-3 font-display text-xl font-extrabold">
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl neo-border bg-[#ff6b00] text-white shadow-[2px_2px_0_#1a1c1c]">
                  <SlidersHorizontal className="h-5 w-5" />
                </span>
                Điều khiển nâng cao
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <label className="block rounded-[24px] border-2 border-[#1a1c1c] bg-[#fff8ef] p-4">
                <div className="mb-3 flex justify-between text-sm font-extrabold">
                  <span>Độ rộng truy xuất Top K</span>
                  <span className="rounded-full border-2 border-[#1a1c1c] bg-[#ffd600] px-3 py-1">{topK}</span>
                </div>
                <input
                  className="h-3 w-full cursor-pointer accent-[#ff6b00]"
                  type="range"
                  min={3}
                  max={12}
                  value={topK}
                  onChange={(event) => onTopKChange(Number(event.target.value))}
                />
              </label>
              <label className="flex cursor-pointer items-center justify-between rounded-[24px] border-2 border-[#1a1c1c] bg-[#eafff6] p-4 text-sm font-extrabold shadow-[3px_3px_0_#1a1c1c]">
                <span>Gửi debug trong chat</span>
                <input
                  className="h-6 w-6 cursor-pointer accent-[#ff6b00]"
                  type="checkbox"
                  checked={debug}
                  onChange={(event) => onDebugChange(event.target.checked)}
                />
              </label>
              <div className="rounded-[24px] border-2 border-[#1a1c1c] bg-[#fff6bf] p-4 text-sm font-extrabold shadow-[3px_3px_0_#1a1c1c]">
                <div className="mb-3">Pre-RAG</div>
                <div className="space-y-3">
                  <PreRagOption
                    value="rule"
                    checked={preRagMode === "rule"}
                    title="Rule-based"
                    description="Chỉ dùng parser/query planner rule-based, không gọi LLM."
                    onChange={onPreRagModeChange}
                  />
                  <PreRagOption
                    value="llm"
                    checked={preRagMode === "llm"}
                    title="LLM"
                    description="Luôn gọi LLM Pre-RAG để rewrite, multi-query, step-back hoặc HyDE."
                    onChange={onPreRagModeChange}
                  />
                  <PreRagOption
                    value="optimized"
                    checked={preRagMode === "optimized"}
                    title="Tối ưu"
                    description="Chỉ gọi LLM khi router chưa đủ tự tin hoặc thiếu rewrite rõ ràng."
                    onChange={onPreRagModeChange}
                  />
                </div>
              </div>
              <div className="rounded-[24px] border-2 border-[#1a1c1c] bg-[#fff8ef] p-4 text-sm font-extrabold shadow-[3px_3px_0_#1a1c1c]">
                <div className="mb-3">LLM model</div>
                <div className="space-y-3">
                  <LlmModelOption
                    value="gpt_4o_mini"
                    checked={llmModelPreset === "gpt_4o_mini"}
                    title="GPT-4o-mini (OpenAI)"
                    description="Dùng OpenAI API cho các bước LLM trong phiên hiện tại."
                    onChange={onLlmModelPresetChange}
                  />
                  <LlmModelOption
                    value="qwen3_5_4b_q4_k_m"
                    checked={llmModelPreset === "qwen3_5_4b_q4_k_m"}
                    title="qwen3.5-4b-q4_k_m"
                    description="Dùng model local qua LM Studio hoặc llama-server cho phiên hiện tại."
                    onChange={onLlmModelPresetChange}
                  />
                </div>
              </div>
              <div className="rounded-[24px] border-2 border-[#1a1c1c] bg-[#eafff6] p-4 text-sm font-extrabold shadow-[3px_3px_0_#1a1c1c]">
                <div className="mb-3">Embedding model</div>
                <div className="space-y-3">
                  <EmbeddingOption
                    value="bge_m3"
                    checked={embeddingPreset === "bge_m3"}
                    title="BGE-M3"
                    description="DÃ¹ng collection dense build tá»« BAAI/bge-m3."
                    onChange={onEmbeddingPresetChange}
                  />
                  <EmbeddingOption
                    value="qwen3_0_6b"
                    checked={embeddingPreset === "qwen3_0_6b"}
                    title="Qwen3-Embedding-0.6B"
                    description="DÃ¹ng collection dense build tá»« Qwen/Qwen3-Embedding-0.6B."
                    onChange={onEmbeddingPresetChange}
                  />
                </div>
              </div>
              <label className="block cursor-pointer rounded-[24px] border-2 border-[#1a1c1c] bg-[#eafff6] p-4 text-sm font-extrabold shadow-[3px_3px_0_#1a1c1c]">
                <div className="flex items-center justify-between gap-3">
                  <span>Dùng Structured Fact/Sanction Lookup cho phiên này</span>
                  <input
                    className="h-6 w-6 cursor-pointer accent-[#ff6b00]"
                    type="checkbox"
                    checked={structuredLookupEnabled}
                    onChange={(event) => onStructuredLookupEnabledChange(event.target.checked)}
                  />
                </div>
                <p className="mt-3 text-xs font-semibold leading-5 text-muted-foreground">
                  Khi bật, phiên hiện tại ưu tiên các rule-based lookup có cấu trúc: fact cố định và rule xử phạt, trước khi fallback sang RAG thường.
                </p>
              </label>
              <div className="rounded-[22px] border-2 border-dashed border-[#1a1c1c] bg-[#fcf3e0] p-4 text-xs font-semibold leading-6 text-muted-foreground">
                Debug chỉ phục vụ kiểm tra pipeline. Người dùng thông thường không cần thấy điểm truy xuất hoặc chunk ID.
              </div>
            </CardContent>
          </Card>

          <Card className="overflow-hidden bg-white">
            <div className="flex items-center justify-between border-b-2 border-[#1a1c1c] bg-[#ffd600] px-5 py-4">
              <CardTitle className="flex items-center gap-2 font-display text-xl font-extrabold">
                <Terminal className="h-5 w-5" />
                Runtime
              </CardTitle>
              <div className="flex gap-2">
                <span className="h-4 w-4 rounded-full border-2 border-[#1a1c1c] bg-red-500" />
                <span className="h-4 w-4 rounded-full border-2 border-[#1a1c1c] bg-[#ffd600]" />
                <span className="h-4 w-4 rounded-full border-2 border-[#1a1c1c] bg-[#00f5a0]" />
              </div>
            </div>
            <CardContent className="p-0">
              <pre className="traffic-tile max-h-[520px] overflow-auto p-5 font-mono text-xs font-semibold leading-6 text-[#1a1c1c]">
                {JSON.stringify({ status: health?.status, system: { pipeline, structured_lookup: structuredLookup, sanctions }, controls: { top_k: topK, debug, pre_rag_mode: preRagMode, llm_model_preset: llmModelPreset, embedding_preset: embeddingPreset, structured_lookup_enabled: structuredLookupEnabled }, index: health?.index }, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}

function PreRagOption({
  value,
  checked,
  title,
  description,
  onChange,
}: {
  value: PreRagMode;
  checked: boolean;
  title: string;
  description: string;
  onChange: (value: PreRagMode) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-[18px] border-2 border-[#1a1c1c] bg-white/70 p-3">
      <input
        className="mt-1 h-5 w-5 cursor-pointer accent-[#ff6b00]"
        type="radio"
        name="pre-rag-mode"
        checked={checked}
        onChange={() => onChange(value)}
      />
      <span>
        <span className="block font-extrabold text-[#1a1c1c]">{title}</span>
        <span className="mt-1 block text-xs font-semibold leading-5 text-muted-foreground">{description}</span>
      </span>
    </label>
  );
}

function LlmModelOption({
  value,
  checked,
  title,
  description,
  onChange,
}: {
  value: LlmModelPreset;
  checked: boolean;
  title: string;
  description: string;
  onChange: (value: LlmModelPreset) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-[18px] border-2 border-[#1a1c1c] bg-white/70 p-3">
      <input
        className="mt-1 h-5 w-5 cursor-pointer accent-[#ff6b00]"
        type="radio"
        name="llm-model-preset"
        checked={checked}
        onChange={() => onChange(value)}
      />
      <span>
        <span className="block font-extrabold text-[#1a1c1c]">{title}</span>
        <span className="mt-1 block text-xs font-semibold leading-5 text-muted-foreground">{description}</span>
      </span>
    </label>
  );
}

function EmbeddingOption({
  value,
  checked,
  title,
  description,
  onChange,
}: {
  value: EmbeddingPreset;
  checked: boolean;
  title: string;
  description: string;
  onChange: (value: EmbeddingPreset) => void;
}) {
  const displayDescription =
    value === "bge_m3"
      ? "Dùng collection dense đã build từ BAAI/bge-m3."
      : "Dùng collection dense đã build từ Qwen/Qwen3-Embedding-0.6B.";

  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-[18px] border-2 border-[#1a1c1c] bg-white/70 p-3">
      <input
        className="mt-1 h-5 w-5 cursor-pointer accent-[#ff6b00]"
        type="radio"
        name="embedding-preset"
        checked={checked}
        onChange={() => onChange(value)}
      />
      <span>
        <span className="block font-extrabold text-[#1a1c1c]">{title}</span>
        <span className="mt-1 block text-xs font-semibold leading-5 text-muted-foreground">{displayDescription || description}</span>
      </span>
    </label>
  );
}

function StatusCard({
  icon,
  title,
  active,
  description,
  tone,
}: {
  icon: React.ReactNode;
  title: string;
  active: boolean;
  description: string;
  tone: "yellow" | "mint" | "orange";
}) {
  const toneClass = {
    yellow: "bg-[#fff6bf]",
    mint: "bg-[#eafff6]",
    orange: "bg-[#fff0e5]",
  }[tone];

  return (
    <Card className={toneClass}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="flex items-center gap-3 font-display text-lg font-extrabold">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl neo-border bg-white text-[#ff6b00] shadow-[2px_2px_0_#1a1c1c] [&_svg]:h-5 [&_svg]:w-5">
              {icon}
            </span>
            {title}
          </CardTitle>
          <Badge variant={active ? "success" : "warning"}>{active ? "Active" : "Inactive"}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm font-semibold leading-6 text-muted-foreground">{description}</p>
        <div className="mt-4 flex items-center gap-2 text-xs font-bold text-[#1a1c1c]">
          <Activity className="h-4 w-4 text-[#ff6b00]" />
          {active ? "Active" : "Inactive"}
        </div>
      </CardContent>
    </Card>
  );
}
