
# Backend (FastAPI)

## Setup

### 1. Install Dependencies
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Database Setup

The application uses PostgreSQL for data persistence. You need to:

1. **Install PostgreSQL** (if not already installed)
   - macOS: `brew install postgresql`
   - Linux: `sudo apt-get install postgresql`
   - Or use Docker: `docker run --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres`

2. **Create a database**
   
   **Option A: Using psql (recommended)**
   ```bash
   psql postgres
   CREATE DATABASE lifestory;
   \q
   ```
   
   **Option B: Using createdb command** (if available)
   ```bash
   createdb lifestory
   ```
   
   **Option C: Using Docker** (if using Docker for PostgreSQL)
   ```bash
   docker exec -it postgres psql -U postgres
   CREATE DATABASE lifestory;
   \q
   ```
   
   **Note**: If `psql` command is not found, you may need to:
   - Add PostgreSQL to your PATH: `export PATH="/usr/local/opt/postgresql@14/bin:$PATH"` (adjust version as needed)
   - Or use the full path: `/usr/local/bin/psql` or `/opt/homebrew/bin/psql`
   - Or reinstall PostgreSQL: `brew reinstall postgresql@14` (or your version)

3. **Configure database connection**
   
   Create a `.env` file in the backend directory:
   ```bash
   DATABASE_URL=postgresql://user:password@localhost:5432/lifestory
   ```
   
   Replace `user` and `password` with your PostgreSQL credentials.

   The database tables will be automatically created on first startup.

### 3. OAuth2 Authentication Setup (Google)

The application uses Google OAuth2 for authentication. To set it up:

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Google+ API**
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google+ API" and enable it
   - Alternatively, use "Google Identity" API

3. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URIs:
     - `http://localhost:8000/api/auth/google/callback` (for development)
     - Your production callback URL (for production)
   - Save the **Client ID** and **Client Secret**

4. **Configure Environment Variables**
   
   Add to your `.env` file:
   ```bash
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   SECRET_KEY=your-secret-key-for-jwt-signing-change-this-in-production
   BACKEND_URL=http://localhost:8000
   FRONTEND_URL=http://localhost:3000
   ```
   
   **Important**: 
   - `SECRET_KEY` should be a long, random string (use `openssl rand -hex 32` to generate one)
   - `BACKEND_URL` should match your backend server URL (used for OAuth callbacks)
   - `FRONTEND_URL` should match your frontend application URL
   - The redirect URI in Google Cloud Console must match: `{BACKEND_URL}/api/auth/google/callback`

### 4. Run the Application
```bash
uvicorn app.main:app --reload --port 8000
```

## Authentication

The application uses Google OAuth2 for authentication with JWT tokens:

- **Login**: `/api/auth/google/login` - Redirects to Google OAuth
- **Callback**: `/api/auth/google/callback` - Handles OAuth callback and returns JWT token
- **Current User**: `/api/auth/me` - Get current authenticated user (requires Bearer token)
- **Logout**: `/api/auth/logout` - Logout endpoint (client removes token)

### Protected Endpoints

Most endpoints now require authentication via Bearer token:
- `POST /api/answers` - Add an answer
- `GET /api/answers` - Get answers (requires authentication)
- `POST /api/story/chapter` - Generate chapter narrative
- `POST /api/story/compile` - Compile full story
- `GET /api/story/{person_id}` - Get compiled story

### Using the API

1. **Login**: Redirect user to `/api/auth/google/login`
2. **Get Token**: After OAuth callback, extract token from redirect URL
3. **Make Requests**: Include token in Authorization header:
   ```
   Authorization: Bearer <your-jwt-token>
   ```

## LLM Permission Management

To control costs, LLM API calls are restricted by default. Users must have `can_use_llm = true` to use LLM features.

### Granting/Revoking LLM Permission

**Option 1: Using API Endpoint (Recommended)**

Use the admin endpoint to grant or revoke permissions:

```bash
POST /api/admin/llm-permission
Authorization: Bearer <your-jwt-token>
Content-Type: application/json

{
  "email": "user@example.com",
  "can_use_llm": true
}
```

You can identify the user by:
- `user_id` (UUID string)
- `person_id` (string)
- `email` (string)

Example requests:
```bash
# Grant permission by email
curl -X POST http://localhost:8000/api/admin/llm-permission \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "can_use_llm": true}'

# Revoke permission by person_id
curl -X POST http://localhost:8000/api/admin/llm-permission \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"person_id": "user_person_id", "can_use_llm": false}'
```

**Option 2: Direct Database Update**

You can also update the database directly:

```sql
-- Grant permission to a specific user by email
UPDATE users SET can_use_llm = true WHERE email = 'user@example.com';

-- Grant permission to a specific user by person_id
UPDATE users SET can_use_llm = true WHERE person_id = 'user_person_id';

-- Grant permission to all users (use with caution!)
UPDATE users SET can_use_llm = true;
```

**Note**: The API endpoint currently allows any authenticated user to grant/revoke permissions. In production, you should add admin role checking.

### Checking Permission Status

Users can check their permission status via the `/api/auth/me` endpoint, which includes the `can_use_llm` field.

### Protected Endpoints

The following endpoints require LLM permission:
- `POST /api/story/chapter` - Generates chapter narrative and summary
- `POST /api/story/compile` - Compiles full story book

If a user without permission tries to use these endpoints, they will receive a 403 error with a message indicating they need permission.

## Database Models

The application uses SQLAlchemy with the following models:
- **User**: Represents a person whose life story is being collected (includes OAuth info and LLM permission)
- **Chapter**: Predefined chapters in the life story (seeded automatically)
- **Answer**: User's answers to questions
- **StoryChapter**: Generated narrative for a chapter (includes summary)
- **Story**: Compiled full life story book
