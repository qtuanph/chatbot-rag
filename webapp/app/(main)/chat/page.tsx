import { ChatPanel } from "@/components/chat/chat-panel";

export const metadata = {
  title: "Chat — RAG Chatbot",
};

export default function ChatPage() {
  return (
    <div className="h-[calc(100vh-3rem)] overflow-hidden">
      <ChatPanel />
    </div>
  );
}
