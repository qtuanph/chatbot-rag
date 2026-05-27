import { ChatView } from "@/components/chat/chat-view";

export const metadata = {
  title: "Chat — RAG Chatbot",
};

export default function ChatPage() {
  return <div className="h-[calc(100dvh-3rem)] overflow-hidden"><ChatView /></div>;
}
