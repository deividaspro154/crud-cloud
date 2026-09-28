# Architecture

```mermaid
flowchart TD
    U[User / Browser] --> W[Flask Web Application on Render]
    C[API Client] -->|HTTP JSON| W

    W -->|SQLAlchemy| DB[(Render PostgreSQL)]
    W -->|Image upload| FS[Cloudinary File Storage]
    W -->|Fallback| LF[Local uploads folder]

    BG[APScheduler Background Task] -->|Every 60 sec| DB
    BG -->|Set quantity=0 products unavailable| DB

    W --> UI[HTML CRUD Interface]
    W --> API[Public REST API]
```

## Components

- **Web application:** Flask + Jinja templates.
- **Public API:** REST JSON endpoints under `/api/products`.
- **Database:** PostgreSQL on Render; SQLite fallback for local development.
- **File storage:** Cloudinary when `CLOUDINARY_URL` is configured; local upload fallback.
- **Background operation:** APScheduler runs every 60 seconds and automatically marks zero-stock products unavailable.
