"use client";

import { useEffect, useState } from "react";
import { Activity, Database, ListOrdered, Network, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HealthResponse, getHealth } from "@/lib/api";

export function DeveloperView({ topK, debug, onTopKChange, onDebugChange }: {
  topK: number;
  debug: boolean;
  onTopKChange: (value: number) => void;
  onDebugChange: (value: boolean) => void;
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

  return (
    <main className="flex-1 overflow-y-auto bg-muted/20 p-6 md:p-8">
      <div className="mx-auto max-w-[1200px] space-y-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Hệ thống RAG</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Theo dõi trạng thái pipeline và bật tùy chọn truy xuất nâng cao cho phiên hiện tại.
            </p>
          </div>
          <Button variant="outline" onClick={() => void refresh()} disabled={loading}>
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Tải lại
          </Button>
        </div>

        {error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <StatusCard
            icon={<Search />}
            title="Lexical BM25"
            active={Boolean(pipeline.bm25_active)}
            description="Tìm kiếm theo từ khóa và số hiệu văn bản."
          />
          <StatusCard
            icon={<Network />}
            title="Semantic Dense"
            active={Boolean(pipeline.dense_active)}
            description={(pipeline.dense_error as string) || "Tìm kiếm ngữ nghĩa bằng embedding."}
          />
          <StatusCard
            icon={<ListOrdered />}
            title="Reranker"
            active={Boolean(pipeline.reranker_active)}
            description={(pipeline.reranker_error as string) || "Xếp hạng lại kết quả truy xuất."}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[380px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                Điều khiển nâng cao
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <label className="block">
                <div className="mb-2 flex justify-between text-sm font-medium">
                  <span>Top K</span>
                  <span>{topK}</span>
                </div>
                <input
                  className="w-full accent-blue-600"
                  type="range"
                  min={3}
                  max={12}
                  value={topK}
                  onChange={(event) => onTopKChange(Number(event.target.value))}
                />
              </label>
              <label className="flex items-center justify-between rounded-lg border p-3 text-sm">
                <span>Gửi debug trong chat</span>
                <input
                  className="h-4 w-4 accent-blue-600"
                  type="checkbox"
                  checked={debug}
                  onChange={(event) => onDebugChange(event.target.checked)}
                />
              </label>
              <div className="rounded-lg bg-zinc-50 p-3 text-xs leading-6 text-muted-foreground">
                Debug chỉ phục vụ kiểm tra pipeline. Người dùng thông thường không cần thấy điểm truy xuất hoặc chunk ID.
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                Runtime
              </CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[460px] overflow-auto rounded-lg bg-zinc-950 p-4 text-xs leading-6 text-zinc-100">
                {JSON.stringify({ status: health?.status, pipeline, sanctions, index: health?.index }, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}

function StatusCard({ icon, title, active, description }: {
  icon: React.ReactNode;
  title: string;
  active: boolean;
  description: string;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <span className="[&_svg]:h-4 [&_svg]:w-4 text-muted-foreground">{icon}</span>
            {title}
          </CardTitle>
          <Badge variant={active ? "success" : "warning"}>{active ? "Active" : "Inactive"}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}
