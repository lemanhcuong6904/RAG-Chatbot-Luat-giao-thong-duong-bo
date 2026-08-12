"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  Clock,
  HelpCircle,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  MessageSquare,
  Plus,
  Settings,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { TrafficLightIcon } from "@/components/traffic-light-icon";
import { cn, shortText } from "@/lib/utils";

type View = "chat" | "documents" | "developer";

export type ConversationSummary = {
  id: string;
  title: string;
};

export function AppShell({
  view,
  onViewChange,
  conversations,
  activeConversationId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  children,
}: {
  view: View;
  onViewChange: (view: View) => void;
  conversations: ConversationSummary[];
  activeConversationId?: string;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  children: React.ReactNode;
}) {
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("rag_luat_gt_sidebar_width");
    if (saved) setSidebarWidth(Math.min(420, Math.max(220, Number(saved) || 260)));
  }, []);

  function startResize(event: React.MouseEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = sidebarWidth;

    function onMove(moveEvent: MouseEvent) {
      const nextWidth = Math.min(420, Math.max(220, startWidth + moveEvent.clientX - startX));
      setSidebarWidth(nextWidth);
      localStorage.setItem("rag_luat_gt_sidebar_width", String(nextWidth));
    }

    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {sidebarCollapsed && (
        <Button
          aria-label="Hiện sidebar"
          className="fixed left-3 top-3 z-40 hidden h-9 w-9 rounded-full shadow-md lg:inline-flex"
          size="icon"
          variant="outline"
          onClick={() => setSidebarCollapsed(false)}
        >
          <PanelLeftOpen className="h-4 w-4" />
        </Button>
      )}
      {!sidebarCollapsed && (
      <aside className="relative hidden shrink-0 flex-col border-r bg-card lg:flex" style={{ width: sidebarWidth }}>
        <div className="flex items-center gap-3 px-4 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-soft text-primary">
            <TrafficLightIcon className="h-7 w-7" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">Luật Giao Thông AI</div>
            <div className="text-xs text-muted-foreground">Trợ lý pháp lý số</div>
          </div>
          <Button
            aria-label="Ẩn sidebar"
            className="ml-auto h-8 w-8"
            size="icon"
            variant="ghost"
            onClick={() => setSidebarCollapsed(true)}
          >
            <PanelLeftClose className="h-4 w-4" />
          </Button>
        </div>

        <div className="px-4 pb-5">
          <Button className="w-full justify-start rounded-xl" onClick={onNewChat}>
            <Plus className="h-4 w-4" />
            Cuộc trò chuyện mới
          </Button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3">
          <div className="mb-5">
            <div className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Hỏi đáp</div>
            <NavButton active={view === "chat"} icon={<MessageSquare />} onClick={() => onViewChange("chat")}>
              Hỏi đáp
            </NavButton>
            <div className="mt-2 space-y-1">
              {conversations.length === 0 ? (
                <p className="px-2 py-2 text-xs text-muted-foreground">Chưa có cuộc trò chuyện nào.</p>
              ) : (
                conversations.slice(0, 12).map((item) => (
                  <div
                    key={item.id}
                    className={cn(
                      "group flex w-full items-center gap-1 rounded-md text-sm text-muted-foreground hover:bg-muted hover:text-foreground",
                      activeConversationId === item.id && "bg-muted text-foreground",
                    )}
                  >
                    <button
                      className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left"
                      onClick={() => onSelectConversation(item.id)}
                    >
                      <Clock className="h-4 w-4 shrink-0" />
                      <span className="truncate">{shortText(item.title, 28)}</span>
                    </button>
                    <Button
                      aria-label="Xóa cuộc trò chuyện"
                      className="mr-1 h-7 w-7 shrink-0 opacity-0 transition-opacity hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
                      size="icon"
                      variant="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeleteConversation(item.id);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <div className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Tra cứu</div>
            <NavButton active={view === "documents"} icon={<BookOpen />} onClick={() => onViewChange("documents")}>
              Văn bản pháp luật
            </NavButton>
          </div>
        </nav>

        <div className="border-t p-3">
          <NavButton active={view === "developer"} icon={<Activity />} onClick={() => onViewChange("developer")}>
            Hệ thống
          </NavButton>
          <NavButton icon={<Settings />}>Cài đặt</NavButton>
          <NavButton icon={<HelpCircle />}>Hỗ trợ</NavButton>
        </div>
        <div
          aria-label="Kéo để đổi chiều rộng sidebar"
          className="absolute right-[-3px] top-0 h-full w-1.5 cursor-col-resize bg-transparent transition-colors hover:bg-primary/30"
          onMouseDown={startResize}
          role="separator"
        />
      </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b bg-card/90 px-4 backdrop-blur lg:hidden">
          <div className="flex items-center gap-2">
            <Menu className="h-5 w-5 text-muted-foreground" />
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary-soft text-primary">
              <TrafficLightIcon className="h-6 w-6" />
            </div>
            <span className="text-sm font-semibold">Luật Giao Thông AI</span>
          </div>
          <Button size="icon" variant="ghost" onClick={onNewChat} aria-label="Cuộc trò chuyện mới">
            <Plus className="h-5 w-5" />
          </Button>
        </header>
        {children}
      </div>
    </div>
  );
}

function NavButton({
  active,
  icon,
  children,
  onClick,
}: {
  active?: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
        active && "bg-muted text-foreground",
      )}
      onClick={onClick}
    >
      <span className={cn("[&_svg]:h-4 [&_svg]:w-4", active && "text-primary")}>{icon}</span>
      {children}
    </button>
  );
}
