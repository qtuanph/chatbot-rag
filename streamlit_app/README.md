# Streamlit Frontend Application

## Overview

This is the Streamlit web interface for the RAG chatbot system, providing a user-friendly Vietnamese-language UI for chatting with documents, managing uploads, and monitoring system health.

## Quick Start

```bash
# From project root
docker compose up --build web

# Access the application
# http://localhost:8501
```

## Features

### Pages

1. **Đăng nhập (Login)** - Authentication with JWT tokens
   - Default credentials: `admin/abc123` or `member/abc123`

2. **💬 Chat** - RAG-powered chat interface
   - Chat with uploaded documents
   - View citations and sources
   - Session-based conversations

3. **📄 Tài liệu (Documents)** - Document management (admin only)
   - Upload PDF files
   - View processing status
   - Delete documents
   - Monitor ingestion progress

4. **🌳 Tree Viewer** - Document hierarchy visualization
   - Interactive tree view of document structure
   - Search functionality
   - Node details view

5. **🏥 System Health** - System monitoring
   - Database status
   - Vector store status
   - Cache status
   - Storage status
   - Worker status

6. **👥 User Management** - User management (admin only, placeholder)
   - Future: Create/edit/delete users

## Architecture

### Components

- **app.py** - Main entry point with routing
- **components/auth.py** - Authentication utilities
- **components/api_client.py** - API client for backend communication
- **pages/** - Individual page implementations

### API Integration

The frontend communicates with the backend API at `http://api:8000` (configured via `API_BASE_URL` environment variable).

All API requests include:
- Automatic authentication headers
- Error handling with user-friendly messages
- Timeout handling
- Response validation

### Session State Management

Key session state variables:
- `authenticated` - Login status
- `token` - JWT access token
- `user_role` - User role (admin/member)
- `username` - Current username
- `current_page` - Active page
- `chat_history` - Chat conversation history

## Docker Configuration

### Service Definition

```yaml
web:
  build:
    context: ./streamlit_app
    dockerfile: Dockerfile
  ports:
    - "8501:8501"
  environment:
    - API_BASE_URL=http://api:8000
  depends_on:
    api:
      condition: service_healthy
```

### Health Check

The service includes a health check at `/_stcore/health` (built-in Streamlit endpoint).

## Development

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r streamlit_app/requirements.txt

# Set environment variables
export API_BASE_URL=http://localhost:8000

# Run Streamlit
cd streamlit_app
streamlit run app.py --server.port 8501
```

### File Structure

```
streamlit_app/
├── app.py                 # Main application entry point
├── Dockerfile             # Docker image definition
├── requirements.txt       # Python dependencies
├── components/
│   ├── __init__.py
│   ├── auth.py           # Authentication functions
│   └── api_client.py     # API client class
└── pages/
    ├── __init__.py
    ├── login.py          # Login page
    ├── chat.py           # Chat interface
    ├── documents.py      # Document management
    ├── tree.py           # Tree viewer
    ├── health.py         # System health
    └── users.py          # User management (placeholder)
```

## UI/UX Design

### Language

All UI text is in Vietnamese for consistency with the project requirements.

### Design Principles

- Clean, simple interface
- Consistent icon usage (emoji-based)
- Clear error messages
- Loading indicators for async operations
- Responsive layout

### Color Scheme

- Success: Green (✅)
- Warning: Yellow (⚠️)
- Error: Red (❌)
- Info: Blue (ℹ️)

## Security

### Authentication

- JWT-based authentication
- Token stored in session state
- Automatic redirect to login on token expiry
- Role-based access control (admin/member)

### Authorization

- Admin-only pages: Documents, User Management
- Member-accessible pages: Chat, Tree Viewer, System Health
- Automatic role checking in page components

## Troubleshooting

### Common Issues

1. **Cannot connect to API**
   - Verify backend API is running
   - Check `API_BASE_URL` environment variable
   - Ensure Docker network connectivity

2. **Authentication errors**
   - Verify default credentials
   - Check backend API logs
   - Clear browser cache and session state

3. **File upload failures**
   - Verify file is PDF format
   - Check file size limits
   - Ensure RustFS storage is accessible

## Next Steps

### Potential Enhancements

1. **Tree Viewer**
   - Interactive tree visualization library
   - Export tree structure
   - Print-friendly view

2. **Chat**
   - Multi-session support
   - Chat history persistence
   - Export conversation

3. **Documents**
   - Batch upload
   - Drag-and-drop interface
   - Document preview

4. **User Management**
   - CRUD operations for users
   - Activity logging
   - Role management

## Metrics

- **Total Lines of Code**: ~909 lines
- **Pages**: 6 pages
- **Components**: 2 core components
- **Dependencies**: 2 (streamlit, requests)

## Support

For issues or questions, refer to:
- Main project README: `../README.md`
- API documentation: `../docs/04_API_CONTRACT_AND_SECURITY.md`
- Architecture docs: `../docs/`
