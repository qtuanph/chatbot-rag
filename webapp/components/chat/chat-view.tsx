"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { ChatPanel } from "./chat-panel";
import { chatApi } from "@/lib/api-client";
import type { ChatSession } from "@/types/api";

export function ChatView() {
  const { data: session } = useSession();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionIdState] = useState<string | null>(null);
  const [sessionsReady, setSessionsReady] = useState(false);
  const [justCreatedSessionId, setJustCreatedSessionId] = useState<string | null>(null);

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
      setSessionsReady(true);
      return list;
    } catch {
      return [];
    }
  }, []);

  // Always start from a fresh empty chat after login/page load.
  // History still appears in the dropdown for manual selection.
  useEffect(() => {
    const userId = session?.userId;
    if (!userId) return;
    localStorage.removeItem("chat_active_session");
    localStorage.setItem("chat_user_id", userId);
    queueMicrotask(() => {
      setActiveSessionIdState(null);
      setJustCreatedSessionId(null);
    });
  }, [session?.userId]);

  // Load sessions on mount
  useEffect(() => {
    if (!session) {
      return;
    }

    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) setSessionsReady(false);
    });

    (async () => {
      const list = await loadSessions();
      if (cancelled) return;
      setSessions(list);
    })();

    return () => {
      cancelled = true;
    };
  }, [session, loadSessions]);

  // "Chat mới" — chỉ clear UI, KHÔNG tạo session rỗng
  const handleNewChat = useCallback(() => {
    setJustCreatedSessionId(null);
    setActiveSessionId(null);
  }, [setActiveSessionId]);

  const handleSelectSession = useCallback((sessionId: string) => {
    setJustCreatedSessionId(null);
    setActiveSessionId(sessionId);
  }, [setActiveSessionId]);

  const handleSessionCreated = useCallback((sessionId: string) => {
    setJustCreatedSessionId(sessionId);
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
      justCreatedSessionId={justCreatedSessionId}
      sessions={sessions}
      sessionsLoading={Boolean(session) && !sessionsReady}
      onNewChat={handleNewChat}
      onSelectSession={handleSelectSession}
      onRefreshSessions={loadSessions}
      onSessionCreated={handleSessionCreated}
      onSessionUpdate={handleSessionUpdate}
    />
  );
}
