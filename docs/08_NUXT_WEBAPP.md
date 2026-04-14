# Nuxt.js Webapp Frontend

## Overview

The frontend is built with **Nuxt.js 3** (Vue 3 framework) in SPA mode, providing a modern, responsive interface for the RAG chatbot system.

## Technology Stack

- **Framework**: Nuxt.js 3.15.1 (Vue 3)
- **Styling**: TailwindCSS 3.4.17
- **HTTP Client**: Axios 1.7.9
- **Visualization**: D3.js 7.9.0 (hierarchical tree viewer)
- **State Management**: Pinia 2.2.4
- **Build Tool**: Vite 6.0.7

## Architecture

### Directory Structure

```
webapp/
├── pages/
│   ├── index.vue          # Login page (entry point)
│   ├── chat.vue           # Chat interface
│   ├── admin.vue          # Admin dashboard
│   └── demo.vue           # Demo/test page
├── components/
│   ├── TreeVisualizer.vue # D3.js hierarchical tree
│   └── ChatInterface.vue  # Chat message display
├── utils/
│   └── api.js             # API client with auth
├── public/                # Static assets
├── nuxt.config.ts         # Nuxt configuration
├── package.json           # Dependencies
└── Dockerfile             # Production build
```

### Authentication Flow

1. **Login** (`pages/index.vue`):
   - User enters username/password
   - POST to `/api/v1/auth/login`
   - JWT token stored in `localStorage`
   - Role-based redirect: admin → `/admin`, member → `/chat`

2. **API Client** (`utils/api.js`):
   - Auto-injects `Authorization: Bearer <token>` header
   - Handles 401 errors (auto-redirect to login)
   - Centralized error handling

3. **Logout**:
   - Clear localStorage
   - Redirect to `/`

### Pages

#### Login Page (`/`)
- Vietnamese language UI
- Username/password form
- Error message display
- Role-based routing after login

#### Chat Page (`/chat`)
- Chat interface with message history
- User/assistant message bubbles
- Expandable citations
- Session management (auto-create new session)
- Logout button

#### Admin Dashboard (`/admin`)
- **Tài liệu** (Documents):
  - List all documents with status
  - Upload new documents (drag & drop)
  - Delete documents with confirmation
  - View document tree

- **Người dùng** (Users):
  - List all users
  - Add new user (username, password, role)
  - Delete user

- **Sức khỏe** (Health):
  - System health dashboard
  - Service status (DB, Redis, Qdrant, RustFS, Celery)
  - Document statistics
  - Auto-refresh every 30 seconds

- **Cây tài liệu** (Tree Viewer):
  - Select document from dropdown
  - Hierarchical tree visualization
  - Click node to view details
  - Search functionality

#### Demo Page (`/demo`)
- Test page for development
- Not used in production

### Components

#### TreeVisualizer.vue
- **Purpose**: Hierarchical document tree visualization
- **Technology**: D3.js v7 + d3-hierarchy
- **Features**:
  - Interactive tree with collapsible nodes
  - Zoom and pan support
  - Node selection with detail panel
  - Search functionality
  - Responsive design

#### ChatInterface.vue
- **Purpose**: Chat message display component
- **Features**:
  - User/assistant message bubbles
  - Expandable citations with document links
  - Welcome message with quick suggestions
  - Auto-scroll to latest message
  - Mobile responsive

### API Integration

All API calls go through `utils/api.js`:

```javascript
// Available methods
api.auth.login(username, password)
api.auth.logout()
api.documents.list()
api.documents.upload(file)
api.documents.delete(documentId)
api.documents.getTree(documentId)
api.documents.searchNodes(documentId, query)
api.chat.sendMessage(query, sessionId)
api.health.getSystemStatus()
api.users.list()
api.users.create(userData)
api.users.delete(username)
```

## Configuration

### Environment Variables

In `.env`:
```
# Backend API URL for webapp
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Docker internal API URL
API_BASE_URL=http://api:8000
```

### Nuxt Config (`nuxt.config.ts`)

```typescript
export default defineNuxtConfig({
  devtools: { enabled: true },
  ssr: false,  // SPA mode

  runtimeConfig: {
    public: {
      apiBase: process.env.API_BASE_URL || 'http://localhost:8000'
    }
  },

  modules: ['@pinia/nuxt', '@nuxtjs/tailwindcss'],

  css: ['~/assets/css/main.css'],

  app: {
    head: {
      title: 'RAG Chatbot - Vietnamese Enterprise Documents',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
    },
  },
})
```

## Development

### Local Development

```bash
cd webapp

# Install dependencies
npm install

# Run development server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Docker Development

```bash
# Build and start all services
docker compose up --build webapp

# Rebuild webapp only
docker compose up --build webapp

# View logs
docker compose logs -f webapp
```

### Production Deployment

The webapp uses a **multi-stage Docker build**:

1. **Builder stage**: Compiles Nuxt.js application
2. **Production stage**: Minimal Node.js image with compiled output

Built application outputs to `.output/` directory and runs with:

```bash
node .output/server/index.mjs
```

## Features

### ✅ Implemented

- [x] Login page with role-based routing
- [x] Chat interface with citations
- [x] Admin dashboard
- [x] Document upload/management
- [x] User management (admin only)
- [x] System health monitoring
- [x] Hierarchical tree viewer
- [x] Vietnamese language UI
- [x] Mobile responsive design
- [x] Auto-logout on 401 errors
- [x] JWT token management
- [x] Search functionality

### 🎨 UI/UX

- **Modern Design**: Clean, minimalist interface
- **Vietnamese Language**: All text in Vietnamese
- **Responsive**: Works on desktop and mobile
- **Accessible**: Semantic HTML, keyboard navigation
- **Feedback**: Loading states, error messages, success toasts

## Troubleshooting

### Common Issues

**Issue**: "Cannot find module" errors
- **Solution**: Run `npm install` in webapp directory

**Issue**: API calls return 401
- **Solution**: Check localStorage for token, try logging out and back in

**Issue**: Tree viewer not displaying
- **Solution**: Check browser console for errors, verify document has tree data

**Issue**: Docker build fails
- **Solution**: Ensure Dockerfile has correct permissions, check node version

### Debug Mode

Enable Nuxt.js devtools:

```typescript
// nuxt.config.ts
devtools: { enabled: true }
```

View console logs in browser DevTools (F12).

## Security

### Implemented

- JWT token stored in localStorage (httpOnly cookie recommended for production)
- Auto-logout on 401 responses
- Role-based access control (admin/member)
- API communication over HTTPS (recommended for production)

### Future Improvements

- [ ] httpOnly cookies for JWT tokens
- [ ] CSRF protection
- [ ] Content Security Policy (CSP)
- [ ] Rate limiting on frontend
- [ ] Input sanitization

## Performance

### Optimization Techniques

- **SPA Mode**: No server-side rendering overhead
- **Code Splitting**: Automatic with Nuxt.js
- **Lazy Loading**: Components loaded on demand
- **Tree Shaking**: Unused code removed in build
- **Asset Optimization**: Images, CSS, JS minified

### Monitoring

Monitor performance with:

```javascript
// Browser DevTools Performance tab
// Lighthouse audit
// Nuxt.js devtools performance metrics
```

## Migration from Streamlit

The frontend was migrated from Streamlit to Nuxt.js for:

1. **Better Control**: Full control over UI/UX
2. **Modern Stack**: Vue 3 ecosystem
3. **Performance**: Faster page loads, better caching
4. **Debugging**: Better developer tools
5. **Customization**: Easier to customize and extend

### Key Differences

| Feature | Streamlit | Nuxt.js |
|---------|-----------|---------|
| Language | Python | JavaScript/TypeScript |
| Rendering | Server-side | Client-side SPA |
| Styling | Limited | Full CSS control |
| Performance | Slower | Faster |
| Deployment | Single container | Separate service |

## Support

For issues or questions:

1. Check browser console for errors
2. Verify API backend is running
3. Check docker logs: `docker compose logs -f webapp`
4. Review documentation in `docs/`

## Credits

- **Framework**: [Nuxt.js](https://nuxt.com/)
- **UI Library**: [TailwindCSS](https://tailwindcss.com/)
- **Visualization**: [D3.js](https://d3js.org/)
- **Icons**: Heroicons (SVG)
