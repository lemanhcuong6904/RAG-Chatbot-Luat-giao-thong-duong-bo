"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell, ConversationSummary } from "@/components/app-shell";
import { ChatMessage, ChatView } from "@/components/chat";
import { DeveloperView } from "@/components/developer";
import { DocumentsView } from "@/components/documents";
import { PreRagMode } from "@/lib/api";
import { shortText } from "@/lib/utils";

type View = "chat" | "documents" | "developer";
type Conversation = ConversationSummary & {
  messages: ChatMessage[];
  updatedAt: number;
};

const STORAGE_KEY = "rag_luat_gt_conversations";

export default function Home() {
  const [view, setView] = useState<View>("chat");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>();
  const [topK, setTopK] = useState(8);
  const [debug, setDebug] = useState(false);
  const [preRagMode, setPreRagMode] = useState<PreRagMode>("optimized");
  const [structuredLookupEnabled, setStructuredLookupEnabled] = useState(true);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as Conversation[];
      setConversations(parsed);
      setActiveId(parsed[0]?.id);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId),
    [activeId, conversations],
  );

  function newChat() {
    const id = crypto.randomUUID();
    const conversation: Conversation = {
      id,
      title: "Cuộc trò chuyện mới",
      messages: [],
      updatedAt: Date.now(),
    };
    setConversations((current) => [conversation, ...current]);
    setActiveId(id);
    setView("chat");
  }

  function setMessages(messages: ChatMessage[]) {
    setView("chat");
    const id = activeId ?? crypto.randomUUID();
    setConversations((current) => {
      const title = messages[0]?.content ? shortText(messages[0].content, 56) : "Cuộc trò chuyện mới";
      const nextConversation: Conversation = {
        id,
        title,
        messages,
        updatedAt: Date.now(),
      };
      const others = current.filter((conversation) => conversation.id !== id);
      return [nextConversation, ...others];
    });
    if (!activeId) setActiveId(id);
  }

  function deleteConversation(id: string) {
    setConversations((current) => {
      const next = current.filter((conversation) => conversation.id !== id);
      if (activeId === id) setActiveId(next[0]?.id);
      return next;
    });
  }

  const messages = activeConversation?.messages ?? [];

  return (
    <AppShell
      view={view}
      onViewChange={setView}
      conversations={conversations}
      activeConversationId={activeId}
      onNewChat={newChat}
      onSelectConversation={(id) => {
        setActiveId(id);
        setView("chat");
      }}
      onDeleteConversation={deleteConversation}
    >
      {view === "chat" && (
        <ChatView
          messages={messages}
          onMessagesChange={setMessages}
          topK={topK}
          debug={debug}
          preRagMode={preRagMode}
          structuredLookupEnabled={structuredLookupEnabled}
        />
      )}
      {view === "documents" && <DocumentsView />}
      {view === "developer" && (
        <DeveloperView
          topK={topK}
          debug={debug}
          preRagMode={preRagMode}
          structuredLookupEnabled={structuredLookupEnabled}
          onTopKChange={setTopK}
          onDebugChange={setDebug}
          onPreRagModeChange={setPreRagMode}
          onStructuredLookupEnabledChange={setStructuredLookupEnabled}
        />
      )}
    </AppShell>
  );
}
