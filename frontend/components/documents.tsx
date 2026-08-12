"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Calendar,
  CheckCircle2,
  Edit3,
  Eye,
  FilePlus2,
  GripVertical,
  Landmark,
  RotateCcw,
  Save,
  Search,
  ShieldCheck,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { API_URL, AdminDocumentPayload, DocumentItem, createAdminDocument, getDocuments } from "@/lib/api";

type ManagedDocument = DocumentItem & { uiKey: string };
type DocumentOverride = Partial<
  Pick<DocumentItem, "document_number" | "title" | "document_type" | "issuing_authority" | "issue_date" | "effective_from" | "abstract">
>;

type NewDocumentDraft = Required<Pick<AdminDocumentPayload, "document_number" | "title">> &
  Omit<AdminDocumentPayload, "document_number" | "title" | "pdf_base64" | "pdf_filename">;

const OVERRIDES_KEY = "rag_luat_gt_document_overrides";
const ORDER_KEY = "rag_luat_gt_document_order";

const EMPTY_NEW_DOCUMENT: NewDocumentDraft = {
  document_number: "",
  title: "",
  document_type: "Thông tư",
  issuing_authority: "",
  issue_date: "",
  effective_from: "",
  abstract: "",
};

export function DocumentsView() {
  const [documents, setDocuments] = useState<ManagedDocument[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingNew, setSavingNew] = useState(false);
  const [adminMode, setAdminMode] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draggingKey, setDraggingKey] = useState<string | null>(null);
  const [pdfDocument, setPdfDocument] = useState<ManagedDocument | null>(null);
  const [draft, setDraft] = useState<DocumentOverride>({});
  const [newDraft, setNewDraft] = useState<NewDocumentDraft>(EMPTY_NEW_DOCUMENT);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [overrides, setOverrides] = useState<Record<string, DocumentOverride>>({});
  const [order, setOrder] = useState<string[]>([]);

  useEffect(() => {
    setOverrides(readJson<Record<string, DocumentOverride>>(OVERRIDES_KEY, {}));
    setOrder(readJson<string[]>(ORDER_KEY, []));
  }, []);

  useEffect(() => {
    let active = true;
    getDocuments()
      .then((items) => {
        if (!active) return;
        setDocuments(items.map((item, index) => ({ ...item, uiKey: stableDocumentKey(item, index) })));
      })
      .catch((exc) => {
        if (active) setError(exc instanceof Error ? exc.message : "Không tải được danh sách văn bản.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const displayDocuments = useMemo(() => {
    const merged = documents.map((document) => normalizeDocument({ ...document, ...overrides[document.uiKey] }));
    const orderRank = new Map(order.map((key, index) => [key, index]));
    return [...merged].sort((a, b) => {
      const aRank = orderRank.get(a.uiKey);
      const bRank = orderRank.get(b.uiKey);
      if (aRank !== undefined || bRank !== undefined) return (aRank ?? 99999) - (bRank ?? 99999);
      return (a.document_number || "").localeCompare(b.document_number || "");
    });
  }, [documents, order, overrides]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return displayDocuments;
    return displayDocuments.filter((document) =>
      [document.document_number, document.title, document.abstract, document.issuing_authority, document.document_type]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(normalized)),
    );
  }, [displayDocuments, query]);

  function startEdit(document: ManagedDocument) {
    setEditingKey(document.uiKey);
    setDraft({
      document_number: document.document_number,
      title: document.title,
      document_type: document.document_type,
      issuing_authority: document.issuing_authority,
      issue_date: document.issue_date,
      effective_from: document.effective_from,
      abstract: document.abstract,
    });
  }

  function saveEdit(key: string) {
    const next = { ...overrides, [key]: draft };
    setOverrides(next);
    localStorage.setItem(OVERRIDES_KEY, JSON.stringify(next));
    setEditingKey(null);
  }

  function resetEdit(key: string) {
    const next = { ...overrides };
    delete next[key];
    setOverrides(next);
    localStorage.setItem(OVERRIDES_KEY, JSON.stringify(next));
    setEditingKey(null);
  }

  function moveDocument(fromKey: string, toKey: string) {
    const keys = displayDocuments.map((document) => document.uiKey);
    const from = keys.indexOf(fromKey);
    const to = keys.indexOf(toKey);
    if (from < 0 || to < 0 || from === to) return;
    const [moved] = keys.splice(from, 1);
    keys.splice(to, 0, moved);
    setOrder(keys);
    localStorage.setItem(ORDER_KEY, JSON.stringify(keys));
  }

  async function saveNewDocument() {
    if (!newDraft.document_number.trim() || !newDraft.title.trim()) {
      setError("Cần nhập số hiệu và tên văn bản.");
      return;
    }
    setSavingNew(true);
    setError(null);
    try {
      const pdfBase64 = pdfFile ? await fileToBase64(pdfFile) : null;
      const created = await createAdminDocument({
        ...newDraft,
        pdf_filename: pdfFile?.name ?? null,
        pdf_base64: pdfBase64,
      });
      const managed = { ...created, uiKey: stableDocumentKey(created, documents.length) };
      const nextDocuments = [managed, ...documents];
      const nextOrder = [managed.uiKey, ...order.filter((key) => key !== managed.uiKey)];
      setDocuments(nextDocuments);
      setOrder(nextOrder);
      localStorage.setItem(ORDER_KEY, JSON.stringify(nextOrder));
      setNewDraft(EMPTY_NEW_DOCUMENT);
      setPdfFile(null);
      setAdding(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không thêm được văn bản.");
    } finally {
      setSavingNew(false);
    }
  }

  return (
    <main className="flex-1 overflow-y-auto bg-muted/20">
      <div className="mx-auto w-full max-w-[1040px] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="mb-2 text-3xl font-semibold tracking-tight">Văn bản pháp luật</h1>
              <p className="text-[15px] text-muted-foreground">
                Tra cứu và kiểm tra nguồn văn bản dùng trong hệ thống hỏi đáp luật giao thông.
              </p>
            </div>
            <div className="flex gap-2">
              {adminMode && (
                <Button variant="outline" onClick={() => setAdding((value) => !value)}>
                  <FilePlus2 className="h-4 w-4" />
                  Thêm văn bản
                </Button>
              )}
              <Button variant={adminMode ? "default" : "outline"} onClick={() => setAdminMode((value) => !value)}>
                {adminMode ? <ShieldCheck className="h-4 w-4" /> : <UserRound className="h-4 w-4" />}
                {adminMode ? "ADMIN" : "Người dùng"}
              </Button>
            </div>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Tìm theo số hiệu, tên văn bản, cơ quan ban hành..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>

        {adminMode && adding && (
          <Card className="mb-5 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Thêm văn bản pháp luật</h2>
              <Button size="icon" variant="ghost" onClick={() => setAdding(false)} aria-label="Đóng form thêm văn bản">
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid gap-3">
              <Input placeholder="Tên văn bản, ví dụ: Thông tư số 105/2026/TT-BCA" value={newDraft.title} onChange={(event) => setNewDraft({ ...newDraft, title: event.target.value })} />
              <Input placeholder="Trích yếu" value={newDraft.abstract || ""} onChange={(event) => setNewDraft({ ...newDraft, abstract: event.target.value })} />
              <div className="grid gap-3 md:grid-cols-2">
                <Input placeholder="Số hiệu" value={newDraft.document_number} onChange={(event) => setNewDraft({ ...newDraft, document_number: event.target.value })} />
                <Input placeholder="Loại văn bản" value={newDraft.document_type || ""} onChange={(event) => setNewDraft({ ...newDraft, document_type: event.target.value })} />
                <Input placeholder="Cơ quan ban hành" value={newDraft.issuing_authority || ""} onChange={(event) => setNewDraft({ ...newDraft, issuing_authority: event.target.value })} />
                <Input placeholder="Ngày ban hành YYYY-MM-DD" value={newDraft.issue_date || ""} onChange={(event) => setNewDraft({ ...newDraft, issue_date: event.target.value })} />
                <Input placeholder="Ngày hiệu lực YYYY-MM-DD" value={newDraft.effective_from || ""} onChange={(event) => setNewDraft({ ...newDraft, effective_from: event.target.value })} />
                <label className="flex cursor-pointer items-center gap-2 rounded-md border bg-white px-3 py-2 text-sm">
                  <Upload className="h-4 w-4" />
                  <span className="truncate">{pdfFile ? pdfFile.name : "Chọn file PDF"}</span>
                  <input className="hidden" type="file" accept="application/pdf" onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)} />
                </label>
              </div>
              <div className="flex gap-2">
                <Button onClick={saveNewDocument} disabled={savingNew}>
                  <Save className="h-4 w-4" />
                  {savingNew ? "Đang lưu..." : "Lưu văn bản"}
                </Button>
                <Button variant="outline" onClick={() => setNewDraft(EMPTY_NEW_DOCUMENT)}>
                  <RotateCcw className="h-4 w-4" />
                  Khôi phục
                </Button>
              </div>
            </div>
          </Card>
        )}

        {loading && <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">Đang tải văn bản...</div>}
        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error}</div>}
        {!loading && !error && filtered.length === 0 && (
          <div className="rounded-lg border bg-card p-8 text-center">
            <h2 className="font-semibold">Không tìm thấy văn bản phù hợp</h2>
            <p className="mt-2 text-sm text-muted-foreground">Thử tìm theo số hiệu như 168/2024/NĐ-CP.</p>
          </div>
        )}

        <div className="space-y-4">
          {filtered.map((document) => {
            const editing = editingKey === document.uiKey;
            return (
              <Card
                key={document.uiKey}
                className="p-5 transition-colors hover:border-primary/50"
                draggable={adminMode}
                onDragOver={(event) => event.preventDefault()}
                onDragStart={() => setDraggingKey(document.uiKey)}
                onDrop={() => {
                  if (draggingKey) moveDocument(draggingKey, document.uiKey);
                  setDraggingKey(null);
                }}
              >
                <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{document.document_number || "Văn bản"}</Badge>
                    <Badge variant="outline">{document.document_type}</Badge>
                    <Badge variant={document.effective_to ? "warning" : "success"}>
                      <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                      {document.effective_to ? "Có thời hạn hiệu lực" : "Đang hiệu lực"}
                    </Badge>
                  </div>
                  <span className="flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground">
                    <Calendar className="h-4 w-4" />
                    Hiệu lực: {formatDate(document.effective_from)}
                  </span>
                </div>

                {editing ? (
                  <div className="mb-4 grid gap-3 rounded-lg border bg-zinc-50 p-4">
                    <Input value={draft.title || ""} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
                    <Input value={draft.abstract || ""} onChange={(event) => setDraft({ ...draft, abstract: event.target.value })} />
                    <div className="grid gap-3 md:grid-cols-2">
                      <Input value={draft.document_number || ""} onChange={(event) => setDraft({ ...draft, document_number: event.target.value })} />
                      <Input value={draft.document_type || ""} onChange={(event) => setDraft({ ...draft, document_type: event.target.value })} />
                      <Input value={draft.issuing_authority || ""} onChange={(event) => setDraft({ ...draft, issuing_authority: event.target.value })} />
                      <Input value={draft.issue_date || ""} onChange={(event) => setDraft({ ...draft, issue_date: event.target.value })} />
                      <Input value={draft.effective_from || ""} onChange={(event) => setDraft({ ...draft, effective_from: event.target.value })} />
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => saveEdit(document.uiKey)}>
                        <Save className="h-4 w-4" />
                        Lưu
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => resetEdit(document.uiKey)}>
                        <RotateCcw className="h-4 w-4" />
                        Khôi phục
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="mb-4">
                    <h2 className="text-xl font-semibold leading-tight">{displayDocumentName(document)}</h2>
                    {document.abstract && <div className="mt-2 text-sm font-semibold leading-6 text-zinc-700">{document.abstract}</div>}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Landmark className="h-4 w-4" />
                    {document.issuing_authority || "Chưa rõ cơ quan"}
                  </span>
                  <span className="h-4 w-px bg-border" />
                  <span>Ban hành: {formatDate(document.issue_date)}</span>
                  <span className="ml-auto flex items-center gap-1 font-medium text-primary">
                    {document.raw_pdf_url ? (
                      <button className="inline-flex items-center gap-1" onClick={() => setPdfDocument(document)}>
                        <Eye className="h-4 w-4" />
                        Xem PDF
                      </button>
                    ) : (
                      <>
                        Chưa có PDF
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </span>
                </div>

                {adminMode && (
                  <div className="mt-4 flex flex-wrap gap-2 border-t pt-3">
                    <div className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground">
                      <GripVertical className="h-4 w-4" />
                      Kéo thả để sắp xếp
                    </div>
                    <Button size="sm" variant="outline" onClick={() => startEdit(document)}>
                      <Edit3 className="h-4 w-4" />
                      Sửa hiển thị
                    </Button>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
        {pdfDocument && <PdfViewer document={pdfDocument} onClose={() => setPdfDocument(null)} />}
      </div>
    </main>
  );
}

function normalizeDocument(document: ManagedDocument): ManagedDocument {
  return {
    ...document,
    document_type: normalizeDocumentType(document.document_number, document.title, document.document_type),
  };
}

function normalizeDocumentType(number?: string | null, title?: string | null, fallback?: string | null) {
  const text = `${number || ""} ${title || ""}`.toLowerCase();
  if (/\/qh\d*/i.test(number || "") || text.includes("luật ")) return "Luật";
  if (/\/nđ-cp|\/nd-cp/i.test(number || "") || text.includes("nghị định")) return "Nghị định";
  if (/\/tt-/i.test(number || "") || text.includes("thông tư")) return "Thông tư";
  return fallback || "Văn bản";
}

function stableDocumentKey(document: DocumentItem, index: number) {
  return [document.document_id, document.document_number, document.title, document.effective_from, index].filter(Boolean).join("::");
}

function displayDocumentName(document: ManagedDocument) {
  const number = document.document_number || "";
  if (!number) return document.title || "Chưa có tiêu đề";
  return `${document.document_type || "Văn bản"} số ${number}`;
}

function formatDate(value?: string | null) {
  if (!value) return "Chưa rõ";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

function PdfViewer({ document, onClose }: { document: ManagedDocument; onClose: () => void }) {
  if (!document.raw_pdf_url) return null;
  const url = `${API_URL}${document.raw_pdf_url}`;
  return (
    <div className="fixed inset-0 z-50 bg-black/50 p-4">
      <div className="mx-auto flex h-full max-w-6xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between gap-4 border-b px-4 py-3">
          <div className="min-w-0">
            <div className="truncate font-semibold">{displayDocumentName(document)}</div>
            {document.abstract && <div className="truncate text-sm text-muted-foreground">{document.abstract}</div>}
          </div>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Đóng PDF">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <iframe className="min-h-0 flex-1" src={url} title={displayDocumentName(document)} />
      </div>
    </div>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || "").split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
