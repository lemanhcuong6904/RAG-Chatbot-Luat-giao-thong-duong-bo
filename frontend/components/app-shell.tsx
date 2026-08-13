"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  Clock,
  HelpCircle,
  Menu,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
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
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("rag_luat_gt_sidebar_width");
    if (saved) setSidebarWidth(Math.min(420, Math.max(240, Number(saved) || 280)));
  }, []);

  function startResize(event: React.MouseEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = sidebarWidth;

    function onMove(moveEvent: MouseEvent) {
      const nextWidth = Math.min(420, Math.max(240, startWidth + moveEvent.clientX - startX));
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
    <div className="playful-bg flex h-screen overflow-hidden text-foreground">
      {sidebarCollapsed && (
        <Button
          aria-label="Hiện sidebar"
          className="fixed left-3 top-3 z-40 hidden h-10 w-10 lg:inline-flex"
          size="icon"
          variant="secondary"
          onClick={() => setSidebarCollapsed(false)}
        >
          <PanelLeftOpen className="h-4 w-4" />
        </Button>
      )}

      {!sidebarCollapsed && (
        <aside
          className="relative hidden shrink-0 flex-col border-r-2 border-[#1a1c1c] bg-[#f0f4f8] p-4 shadow-[6px_0_0_#1a1c1c] lg:flex"
          style={{ width: sidebarWidth }}
        >
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-12 w-12 rotate-[-4deg] items-center justify-center rounded-2xl neo-border bg-[#ffd600] shadow-[3px_3px_0_#1a1c1c] text-[#1a1c1c]">
              <TrafficLightIcon className="h-7 w-7" />
            </div>
            <div className="min-w-0">
              <div className="font-display text-xl font-extrabold leading-tight text-[#1a1c1c]">LuậtVui</div>
              <div className="truncate text-xs font-bold text-muted-foreground">Hiểu luật, lái an toàn</div>
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

          <div className="pb-6">
            <Button className="w-full justify-start" onClick={onNewChat}>
              <Plus className="h-4 w-4" />
              Chat mới ngay
            </Button>
          </div>

          <nav className="flex-1 overflow-y-auto pr-1">
            <div className="mb-5">
              <div className="mb-2 px-3 text-xs font-extrabold uppercase text-muted-foreground">Hỏi đáp</div>
              <NavButton active={view === "chat"} icon={<MessageSquare />} onClick={() => onViewChange("chat")}>
                Hỏi đáp luật
              </NavButton>
              <div className="mt-2 space-y-1">
                {conversations.length === 0 ? (
                  <p className="px-3 py-2 text-xs font-medium text-muted-foreground">Chưa có cuộc trò chuyện nào.</p>
                ) : (
                  conversations.slice(0, 12).map((item) => (
                    <div
                      key={item.id}
                      className={cn(
                        "group flex w-full items-center gap-1 rounded-2xl text-sm font-medium text-muted-foreground hover:bg-[#fcf3e0] hover:text-foreground",
                        activeConversationId === item.id && "neo-border bg-white text-foreground shadow-[2px_2px_0_#1a1c1c]",
                      )}
                    >
                      <button
                        className="flex min-w-0 flex-1 items-center gap-2 rounded-2xl px-3 py-2 text-left"
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
              <div className="mb-2 px-3 text-xs font-extrabold uppercase text-muted-foreground">Tra cứu</div>
              <NavButton active={view === "documents"} icon={<BookOpen />} onClick={() => onViewChange("documents")}>
                Văn bản pháp luật
              </NavButton>
            </div>
          </nav>

          <div className="mt-4 border-t-2 border-[#1a1c1c] pt-4">
            <NavButton active={view === "developer"} icon={<Activity />} onClick={() => onViewChange("developer")}>
              Hệ thống
            </NavButton>
            <NavButton icon={<Settings />}>Cài đặt</NavButton>
            <NavButton icon={<HelpCircle />}>Hỗ trợ</NavButton>
          </div>

          <div
            aria-label="Kéo để đổi chiều rộng sidebar"
            className="absolute right-[-4px] top-0 h-full w-2 cursor-col-resize bg-transparent transition-colors hover:bg-[#ff6b00]"
            onMouseDown={startResize}
            role="separator"
          />
        </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b-2 border-[#1a1c1c] bg-[#fff8ef]/95 px-4 shadow-[0_4px_0_#1a1c1c] backdrop-blur lg:hidden">
          <div className="flex items-center gap-2">
            <Menu className="h-5 w-5 text-muted-foreground" />
            <div className="flex h-9 w-9 items-center justify-center rounded-xl neo-border bg-[#ffd600] text-[#1a1c1c]">
              <TrafficLightIcon className="h-6 w-6" />
            </div>
            <span className="font-display text-base font-extrabold">LuậtVui</span>
          </div>
          <Button size="icon" variant="secondary" onClick={onNewChat} aria-label="Cuộc trò chuyện mới">
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
        "mb-1 flex w-full items-center gap-3 rounded-2xl border-2 border-transparent px-3 py-3 text-left text-sm font-bold text-muted-foreground transition-all hover:border-[#1a1c1c] hover:bg-[#fcf3e0] hover:text-foreground",
        active && "border-[#1a1c1c] bg-[#ffd600] text-[#1a1c1c] shadow-[3px_3px_0_#1a1c1c]",
      )}
      onClick={onClick}
    >
      <span className={cn("[&_svg]:h-4 [&_svg]:w-4", active ? "text-[#1a1c1c]" : "text-[#ff6b00]")}>{icon}</span>
      {children}
    </button>
  );
}
