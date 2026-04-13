# Claude Code Configuration - Project: chatbot-rag

Thư mục này chứa cấu hình và memory riêng cho project này.

## 📁 Cấu trúc

```
.claude/
├── README.md              # File này - hướng dẫn sử dụng
├── settings.json          # Cấu hình MCP, hooks, UI cho project
├── MEMORY.md              # Index của tất cả memories
├── memory/                # Chứa các memory file
│   ├── user_profile.md    # Thông tin về bạn (vai trò, sở thích)
│   ├── user_feedback.md   # Feedback: những gì nên/không nên làm
│   ├── project_context.md # Context về project (goals, deadlines)
│   └── external_resources.md # Links ra external systems
├── plans/                 # Implementation plans (khi dùng Plan mode)
└── hooks/                 # Custom hook scripts
```

## ⚙️ Cấu hình MCP (Model Context Protocol)

**MCP** là gì?
- MCP cho phép Claude kết nối với external services
- Ví dụ: GitHub, Database, Web search, Filesystem
- Claude có thể đọc issues, query DB, search web, đọc file bên ngoài project

### Cách bật MCP servers:

1. **GitHub** - Để Claude đọc PRs, issues, commits:
   ```json
   "github": {
     "env": {
       "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxxxxxxxxx"
     }
   }
   ```
   Lấy token tại: https://github.com/settings/tokens

2. **Postgres** - Để Claude query database trực tiếp:
   ```json
   "postgres": {
     "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://app_rw:password@localhost:5432/ragbot"]
   }
   ```

3. **Brave Search** - Để Claude search web:
   ```json
   "brave-search": {
     "env": {
       "BRAVE_API_KEY": "your-api-key"
     }
   }
   ```
   Lấy API key tại: https://api.search.brave.com/app/keys

4. **Filesystem** - Để Claude đọc codebase ngoài project này:
   ```json
   "filesystem": {
     "args": ["-y", "@modelcontextprotocol/server-filesystem", "D:/Dev"]
   }
   ```

## 🧠 Memory System

**Memory** là gì?
- Memory cho phép Claude "nhớ" về bạn và project này
- Khi bạn bắt đầu cuộc hội thoại mới, Claude sẽ đọc memories để hiểu context
- Memories được chia thành 4 loại:
  - **user**: Về bạn (vai trò, kiến thức, sở thích)
  - **feedback**: Những gì bạn thích/không thích (lessons learned)
  - **project**: Context về project (goals, deadlines, stakeholders)
  - **reference**: Links đến external resources

### Cách dùng Memory:

Bạn không cần tự tạo memory files. Claude sẽ tự động:
- Tạo memory khi học được điều mới về bạn/project
- Cập nhật memory khi có thay đổi
- Đọc memory ở mỗi session mới để hiểu context

**Bạn có thể:** chỉnh sửa memory trực tiếp nếu muốn.

### Về Obsidian và Memory:

Em họ bạn nói dùng **Obsidian** để lưu memory có nghĩa là:
- Obsidian là app note-taking với markdown files
- Memory files của Claude cũng là markdown
- Bạn có thể mở thư mục `.claude/memory/` bằng Obsidian để:
  - Đọc/search memories dễ dàng hơn
  - Xem graph view của các memories
  - Chỉnh sửa memories bằng Obsidian's editor
  - Sync memories giữa machines (vía Obsidian Sync, Git, iCloud)

**Kết quả:** Memories được lưu ở 2 nơi:
1. Trong project (`.claude/memory/`) - Claude đọc từ đây
2. Trong Obsidian - Bạn đọc/chỉnh sửa cho tiện

## 🪝 Hooks

**Hooks** là gì?
- Hooks cho phép chạy lệnh tự động trước/sau sự kiện
- Ví dụ: Warn trước khi chạy `docker compose down`
- Hoặc: Auto-run tests sau khi edit file Python

### Ví dụ Hook:

```json
"hooks": {
  "preToolUse": {
    "Bash": {
      "command": "echo '⚡ About to run: {command}'"
    }
  }
}
```

## 🚀 Quick Start

1. **Cấu hình MCP** (nếu muốn):
   - Mở `.claude/settings.json`
   - Thêm API keys của bạn

2. **Để Claude tự học về bạn**:
   - Hỏi Claude record preferences: "Hãy nhớ rằng tôi thích..."
   - Claude sẽ tự tạo memory files

3. **Xem memories trong Obsidian** (nếu có):
   - Mở Obsidian
   - Open folder as vault: `.claude/memory/`
   - Xem/search/edit memories

## 📚 Tài liệu tham khảo

- Claude Code Docs: https://docs.anthropic.com/en/docs/build-with-claude/claude-for-developers
- MCP Documentation: https://modelcontextprotocol.io/
- Obsidian: https://obsidian.md/

---

**Created:** 2026-04-13
**Project:** chatbot-rag - Vietnamese RAG chatbot for enterprise documents
