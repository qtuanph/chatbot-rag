import { DocumentTable } from "@/components/admin/document-table";

export const metadata = {
  title: "Tài liệu — RAG Chatbot",
};

export default function DocumentsPage() {
  return (
    <div className="p-2 sm:p-6">
      <DocumentTable />
    </div>
  );
}
