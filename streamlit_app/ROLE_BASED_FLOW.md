# Streamlit Role-Based Flow Implementation

## Overview

The Streamlit app has been successfully rewritten to follow a **role-based authentication flow** without dropdown menus. Users are automatically routed to the appropriate interface based on their role.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         app.py (Entry Point)                    │
│                                                                  │
│  if NOT authenticated → redirect to login.py                   │
│  if authenticated AND admin → redirect to admin.py             │
│  if authenticated AND member → redirect to chat.py             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      pages/login.py                             │
│  • Login form (username/password)                              │
│  • On success → redirect to app.py (triggers role routing)     │
│  • Shows default credentials hint                              │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│    pages/admin.py            │  │    pages/chat.py             │
│  (Admin Dashboard)            │  │  (Member Chat Interface)     │
│                              │  │                              │
│  Sidebar sections:           │  │  • Chat interface            │
│  • 📄 Tài liệu               │  │  • Chat history              │
│  • 👥 Người dùng             │  │  • Citations display         │
│  • 🏥 Sức khỏe hệ thống      │  │  • Clear chat button         │
│  • 🌳 Cây tài liệu           │  │  • Logout button             │
│                              │  │                              │
│  Features:                   │  │  Admin extras:               │
│  • Upload documents          │  │  • Link to Admin Dashboard   │
│  • Manage users              │  │                              │
│  • View system health        │  │                              │
│  • View document trees       │  │                              │
│  • Logout button             │  │                              │
└──────────────────────────────┘  └──────────────────────────────┘
```

## Files Modified

### 1. `streamlit_app/app.py` (Main Entry Point)
**Changes:**
- Removed sidebar navigation with dropdown menu
- Removed `render_sidebar()` and `render_page()` functions
- Added role-based routing logic in `main()`:
  - If not authenticated → redirect to `pages/login.py`
  - If authenticated + admin role → redirect to `pages/admin.py`
  - If authenticated + member role → redirect to `pages/chat.py`

**Key Code:**
```python
def main():
    # Route to login if not authenticated
    if not st.session_state.authenticated:
        st.switch_page("pages/login.py")

    # Authenticated - route based on role
    if check_admin_role():
        st.switch_page("pages/admin.py")
    else:
        st.switch_page("pages/chat.py")
```

### 2. `streamlit_app/pages/login.py` (Login Page)
**Changes:**
- Added page config (centered layout, collapsed sidebar)
- Added automatic redirect if already authenticated
- Modified success routing: after login → `st.switch_page("app.py")` to trigger role routing
- Kept default credentials hint

**Key Code:**
```python
# Clear any existing session
if st.session_state.get("authenticated"):
    st.switch_page("app.py")  # Trigger role routing

# On successful login:
if login(username, password):
    st.success("Đăng nhập thành công!")
    st.switch_page("app.py")  # Redirect for role routing
```

### 3. `streamlit_app/pages/chat.py` (Chat Interface)
**Changes:**
- Added page config and authentication checks
- Added sidebar with:
  - User info display
  - Admin link to dashboard (only for admin role)
  - Logout button
  - Clear chat history button
- Removed any page selector from sidebar
- Kept core chat functionality unchanged

**Key Features:**
- Members: Only see chat interface + logout
- Admins: See chat interface + link to Admin Dashboard + logout

## Files Created

### 4. `streamlit_app/pages/admin.py` (NEW - Admin Dashboard)
**Purpose:** Consolidated admin interface with all admin functions

**Features:**
- **Sidebar Navigation:**
  - Section selector: Documents, Users, Health, Tree
  - Logout button (returns to login)
  - Quick link to Chat (for testing)

- **📄 Tài liệu (Documents):**
  - Document statistics (total, processing, completed, failed)
  - Upload form (PDF files)
  - Documents list with expandable details
  - Delete button for each document
  - Task status checking
  - Ingestion details display

- **👥 Người dùng (User Management):**
  - Add new user form (username, password, role)
  - User list with role badges
  - User statistics (admin count, member count)
  - Delete user protection (cannot delete self)

- **🏥 Sức khỏe hệ thống (System Health):**
  - Overall system status
  - Service status cards (Database, Qdrant, Redis)
  - Storage information (RustFS, PostgreSQL size)
  - Document statistics
  - Worker Celery status
  - Auto-refresh option (30s)
  - Manual refresh button

- **🌳 Cây tài liệu (Document Tree):**
  - Document selector (completed documents only)
  - Hierarchical tree visualization
  - Document metadata display
  - Tree statistics (nodes, depth, sections, chunks)

**Key Code Structure:**
```python
# Sidebar section selector
section = st.radio(
    "Chọn mục:",
    ["📄 Tài liệu", "👥 Người dùng", "🏥 Sức khỏe hệ thống", "🌳 Cây tài liệu"]
)

# Main content based on selection
if section == "📄 Tài liệu":
    # Show documents management
elif section == "👥 Người dùng":
    # Show user management
elif section == "🏥 Sức khỏe hệ thống":
    # Show system health
elif section == "🌳 Cây tài liệu":
    # Show document tree viewer
```

## Authentication & Session State

### Session State Variables
- `authenticated`: Boolean, login status
- `token`: JWT token from backend
- `user_role`: "admin" or "member"
- `username`: Current username

### Auth Flow
1. User enters credentials in `login.py`
2. Backend validates and returns JWT + role
3. Session state updated via `components/auth.py`
4. Redirect to `app.py` for routing
5. `app.py` checks role and redirects to appropriate page

### Logout Flow
1. User clicks "Đăng xuất" button
2. `components/auth.py::logout()` clears session state
3. Redirect to `pages/login.py`

## Security Features

1. **Authentication Required:**
   - All pages check `check_authentication()` at startup
   - Unauthenticated users automatically redirected to login

2. **Role-Based Access Control:**
   - Admin pages check `check_admin_role()`
   - Members cannot access admin dashboard
   - Admins can access both dashboard and chat

3. **Session Management:**
   - JWT token stored in session state
   - Token sent with all API requests via `api_client`
   - Auto-logout on 401 responses

4. **Protected Routes:**
   - `admin.py`: Admin-only, shows error if not admin
   - `chat.py`: Open to all authenticated users
   - `login.py`: Redirects if already authenticated

## UI/UX Improvements

1. **Clean Navigation:**
   - No dropdown menus
   - Automatic routing based on role
   - Clear visual hierarchy

2. **Vietnamese Language:**
   - All UI text in Vietnamese
   - Professional terminology
   - Clear button labels

3. **Responsive Design:**
   - Wide layout for dashboard
   - Centered layout for login
   - Proper use of columns and containers

4. **Feedback Mechanisms:**
   - Loading spinners for async operations
   - Success/error messages
   - Status indicators with emojis

## Testing Checklist

### Login Flow
- [ ] Access `app.py` without auth → redirects to login
- [ ] Login with admin credentials → redirects to admin dashboard
- [ ] Login with member credentials → redirects to chat

### Admin Dashboard
- [ ] Upload document successfully
- [ ] View documents list
- [ ] Delete document
- [ ] Add new user
- [ ] View system health
- [ ] View document tree
- [ ] Logout returns to login

### Chat Interface
- [ ] Members can chat
- [ ] Members see citations
- [ ] Members can clear chat history
- [ ] Members can logout
- [ ] Admins see link to dashboard
- [ ] Admins can switch between chat and dashboard

### Edge Cases
- [ ] Already authenticated user访问 login → redirects to app
- [ ] Member tries to access admin page → error message
- [ ] Session expires → auto-redirect to login
- [ ] Network errors → proper error messages

## Migration Notes

### Files No Longer Used
- `pages/documents.py` - logic moved to `admin.py`
- `pages/users.py` - logic moved to `admin.py`
- `pages/health.py` - logic moved to `admin.py`
- `pages/tree.py` - logic moved to `admin.py`

**Note:** These files are kept for backward compatibility but can be deleted after testing.

### Breaking Changes
- **URL routing:** Users can no longer directly access pages via URL
- **Sidebar navigation:** Dropdown menu removed
- **Access control:** Stricter role enforcement

## Configuration

### Environment Variables
```bash
API_BASE_URL=http://api:8000  # Backend API URL
```

### Docker Integration
The Streamlit app is configured to run in Docker:
- Port: `8501`
- Depends on: `api` service
- Environment: `API_BASE_URL=http://api:8000`

## Next Steps

1. **Testing:**
   - Run the app with `docker compose up`
   - Test all flows with both admin and member accounts
   - Verify error handling

2. **Cleanup:**
   - Remove obsolete page files after testing:
     - `pages/documents.py`
     - `pages/users.py`
     - `pages/health.py`
     - `pages/tree.py`

3. **Documentation:**
   - Update user guide with new flow
   - Add screenshots of new interface
   - Document role-based access control

4. **Enhancements:**
   - Add password change functionality
   - Add user profile management
   - Add activity logs for admin
   - Add more granular permissions

## Summary

✅ **Successfully implemented role-based flow without dropdown menus**

**Key Achievements:**
- Clean authentication flow with automatic routing
- Separate interfaces for admin and member roles
- Consolidated admin dashboard with all management functions
- Improved user experience with Vietnamese UI
- Secure session management
- Proper error handling and feedback

**Files Modified:** 3 (`app.py`, `login.py`, `chat.py`)
**Files Created:** 1 (`admin.py`)
**Total Lines of Code:** ~600 lines

The app now provides a professional, role-based user experience that automatically routes users to the appropriate interface based on their authentication status and role.
