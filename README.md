# CollabNotes — Notes & Classroom Collaboration Platform

A polished full-stack **Flask collaboration workspace** for personal notes, classroom communication, direct messaging, polls, public knowledge sharing, and role-based administration.

CollabNotes is designed as a portfolio-scale product rather than a single-feature CRUD demo. It combines server-rendered Flask pages with JSON endpoints for interactive features, while keeping authorization and validation on the server.

## Product Highlights

### Personal workspace
- Dashboard with note, class, pinned-item, and unread-message metrics
- Rich-text notes powered by Quill
- Tags, pinned notes, file attachments, and public/private visibility
- Note search, tag filtering, visibility filtering, and sorting
- Note duplication
- Recoverable **version history** with one-click restore
- Public share links with link regeneration
- Comments and like/dislike reactions
- Explore page for public notes shared by other users

### Classroom collaboration
- Students can join a classroom with a generated class code
- Teachers/admins can create classrooms
- Teacher announcement feed
- Class chat with automatic polling updates
- Classroom polls with live vote totals
- Teacher/admin member removal controls

### Messaging
- One-to-one direct messages
- Polling-based updates without a full page refresh
- Read/unread state and navbar unread badge
- Per-conversation unread counters
- User search by name or email

### Accounts & administration
- Student self-registration and secure login
- Public signup cannot self-assign teacher/admin access
- Account profile editing and password changes
- Student/teacher/admin roles
- Admin user and role management
- Admin activity overview

### Product polish & engineering
- Responsive dashboard-style interface
- Light/dark theme saved in `localStorage`
- Custom 400/404/413/500 pages
- CSRF protection on form and JSON write requests
- Sanitised rich-text note content
- 10 MB attachment limit and allow-listed file extensions
- Security response headers and safer session-cookie defaults
- Docker + Gunicorn deployment files
- Automated pytest suite
- GitHub Actions CI workflow
- `/health` endpoint for deployment checks

---

## Tech Stack

**Backend**
- Python
- Flask
- Flask-SQLAlchemy / SQLAlchemy
- Flask-Login
- Flask-Migrate / Alembic
- SQLite for local development
- Werkzeug password hashing
- Bleach HTML sanitisation

**Frontend**
- Jinja2
- Bootstrap 4
- Bootstrap Icons
- Quill.js
- Vanilla JavaScript / Fetch API
- Custom responsive CSS

**Quality / Deployment**
- pytest
- GitHub Actions
- Gunicorn
- Docker

---

## Architecture

```text
Browser
  │
  ├── Server-rendered pages ───────► Flask blueprints
  │                                   ├── auth.py
  │                                   ├── views.py
  │                                   └── admin.py
  │
  └── Fetch / JSON interactions ───► comments, reactions, chat,
                                      messages, polls, pinning
                                           │
                                           ▼
                                  SQLAlchemy models
                                           │
                                           ▼
                                      SQLite DB
```

The application keeps access control server-side even when the UI uses asynchronous requests.

---

## Project Structure

```text
flask-notes-collaboration-platform/
├── .github/
│   └── workflows/
│       └── ci.yml
├── migrations/
├── tests/
│   ├── conftest.py
│   └── test_app.py
├── uploads/
│   └── .gitkeep
├── website/
│   ├── __init__.py
│   ├── admin.py
│   ├── auth.py
│   ├── models.py
│   ├── views.py
│   ├── static/
│   │   ├── app.css
│   │   └── index.js
│   └── templates/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── main.py
├── requirements.txt
├── seed.py
├── setup_db.py
└── wsgi.py
```

---

## Data Model

The app includes SQLAlchemy models for:

- `User`
- `Note`
- `NoteHistory`
- `NoteAttachment`
- `Tag`
- `Comment`
- `Reaction`
- `ClassRoom`
- `ClassPost`
- `ClassChatMessage`
- `Message`
- `Poll`
- `PollOption`
- `PollVote`

Association tables connect notes ↔ tags and users ↔ classrooms.

---

## Local Setup

### 1. Clone

```bash
git clone https://github.com/saintsasi/flask-notes-collaboration-platform.git
cd flask-notes-collaboration-platform
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

Windows:

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Set a long random Flask secret in `.env`:

```env
FLASK_SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=0
PORT=5000
```

For HTTPS production deployments set:

```env
SESSION_COOKIE_SECURE=1
```

### 5. Apply database migrations

```bash
flask --app main:app db upgrade
```

### 6. Run

```bash
python main.py
```

Then open `http://127.0.0.1:5000`.

---

## Demo Data

To populate a local demo workspace:

```bash
python seed.py
```

Demo accounts:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@app.com` | `password123` |
| Teacher | `teacher@app.com` | `password123` |
| Student | `student@app.com` | `password123` |

The seed script is for local demonstration only. It can create the schema directly for a fresh local demo database.

---

## Main User Flows

### Notes

1. Create a rich-text note.
2. Add tags, pin it, attach a file, or make it public.
3. Search/filter it later in the note library.
4. Edit the note; the previous title/content is stored as a version.
5. Restore an older version if needed.
6. Share a public link or regenerate the link to invalidate the old one.

### Classroom

1. An admin promotes a user to `teacher`.
2. The teacher creates a classroom.
3. A six-character join code is generated.
4. Students join using the code.
5. The teacher posts announcements, runs polls, and uses class chat.

### Direct messages

1. Search for another workspace member.
2. Open a conversation and send messages.
3. The conversation polls for updates.
4. Read state and unread counts update automatically.

---

## Security Controls

This portfolio version includes several practical controls:

- passwords stored as Werkzeug hashes
- public signup restricted to student accounts
- server-side ownership checks for private notes and note deletion
- classroom membership checks
- admin-only role management
- CSRF token validation for state-changing requests
- rich-text sanitisation with Bleach
- safe DOM insertion for chat and message content
- upload extension allow-list
- 10 MB request/upload cap
- HttpOnly + SameSite session-cookie defaults
- optional Secure session cookies for HTTPS
- CSP, frame, referrer, permissions, and MIME-sniffing response headers
- local databases, uploads, logs, and `.env` excluded from Git

---

## Tests

Run:

```bash
pytest -q
```

The included suite covers key behaviours such as:

- health endpoint
- student-only public signup
- private note access
- anonymous public share links
- teacher-only classroom creation

GitHub Actions runs the suite automatically on pushes and pull requests to `main`.

---

## Docker

Build:

```bash
docker build -t collabnotes .
```

Run:

```bash
docker run --rm -p 5000:5000 \
  -e FLASK_SECRET_KEY="replace-me" \
  collabnotes
```

For persistent production data, mount storage and configure the database appropriately for the deployment platform.

---

## Remaining Production Work

The project is deliberately close to a product experience, but a real multi-user deployment would still benefit from:

- PostgreSQL instead of local SQLite
- object storage and malware scanning for attachments
- password-reset email flow
- email verification
- WebSocket/SSE messaging instead of HTTP polling
- request rate limiting
- structured logging and application monitoring
- pagination for very large note/chat datasets
- broader integration/browser test coverage
- deployment-specific backups and secrets management

These are kept explicit so the repository does not overstate production readiness.

---

## Author / Project Credit

Portfolio version maintained by **Sai Sashank Akula** — [@saintsasi](https://github.com/saintsasi).

If the original coursework was developed with collaborators or extended from an upstream project, preserve the relevant contributor/original-project attribution when publishing this version.
