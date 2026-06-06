import { ChatView } from "@/components/chat/chat-view";

export const metadata = {
  title: "Chat test nội bộ",
};

export default function ChatPage() {
  return (
    <div className="h-[calc(100dvh-3.5rem)] overflow-hidden">
      <ChatView />
    </div>
  );
}
