import { ChatView } from "@/components/chat/chat-view";

export const metadata = {
  title: "Chat — RAG Chatbot",
};

export default function ChatPage() {
  return <div className="h-full"><ChatView /></div>;
}
