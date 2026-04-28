"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useSession } from "next-auth/react";
import { ChatPanel } from "./chat-panel";
import { chatApi } from "@/lib/api-client";
import { toast } from "sonner";
import type { ChatSession } from "@/types/api";

export function ChatView() {
  const { data: session } = useSession();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionIdState] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("chat_active_session") || null;
    }
    return null;
  });
  const [sessionsLoading, setSessionsLoading] = useState(true);
  // Track sessions just created locally — don't reload messages for them
  const justCreatedRef = useRef<string | null>(null);

  const setActiveSessionId = useCallback((id: string | null) => {
    setActiveSessionIdState(id);
    if (id) {
      localStorage.setItem("chat_active_session", id);
    } else {
      localStorage.removeItem("chat_active_session");
    }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const list = await chatApi.getSessions();
      setSessions(list);
      return list;
    } catch {
      return [];
    }
  }, []);

  // Load sessions on mount
  useEffect(() => {
    if (!session) {
      setSessionsLoading(false);
      return;
    }

    let cancelled = false;

    (async () => {
      const list = await loadSessions();
      if (cancelled) return;
      setSessions(list);
      setSessionsLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [session, loadSessions]);

  // "Chat mới" — chỉ clear UI, KHÔNG tạo session rỗng
  const handleNewChat = useCallback(() => {
    justCreatedRef.current = null;
    setActiveSessionId(null);
  }, [setActiveSessionId]);

  const handleSelectSession = useCallback((sessionId: string) => {
    justCreatedRef.current = null;
    setActiveSessionId(sessionId);
  }, [setActiveSessionId]);

  const handleSessionCreated = useCallback((sessionId: string) => {
    justCreatedRef.current = sessionId;
    setActiveSessionId(sessionId);
    loadSessions();
  }, [loadSessions, setActiveSessionId]);

  const handleSessionUpdate = useCallback(
    (sessionId: string, updates: Partial<ChatSession>) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.session_id === sessionId ? { ...s, ...updates } : s,
        ),
      );
    },
    [],
  );

  return (
    <ChatPanel
      sessionId={activeSessionId}
      justCreatedSessionId={justCreatedRef.current}
      sessions={sessions}
      sessionsLoading={sessionsLoading}
      onNewChat={handleNewChat}
      onSelectSession={handleSelectSession}
      onRefreshSessions={loadSessions}
      onSessionCreated={handleSessionCreated}
      onSessionUpdate={handleSessionUpdate}
    />
  );
}
