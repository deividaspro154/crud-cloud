# Product Manager CRUD — Cloud Computing task 3

Small Flask application that satisfies the assignment:

> CRUD (Create, Read, Update, Delete + list), validation of at least 4 data types, web application, public API, persistent database, file storage, background operation and a small architecture drawing.

## What is implemented

| Requirement | Implementation |
|---|---|
| Create | `/products/new` |
| Read | `/products/<id>` |
| Update | `/products/<id>/edit` |
| Delete | POST `/products/<id>/delete` |
| List | `/` |
| 4+ input data types | string, integer, decimal/number, boolean, date |
| Public API | `/api/products` |
| Persistent DB | PostgreSQL on Render |
| File storage | Cloudinary when configured; local upload fallback |
| Background operation | every 60 s, zero-stock products become unavailable |
| Architecture drawing | `docs/architecture.svg` and `docs/architecture.md` |

---

# 1. Run locally

Open the project folder in VS Code.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Locally, if `DATABASE_URL` is not defined, the project automatically uses SQLite (`products.db`).

---

# 2. Test the CRUD

1. Click **Add product**.
2. Enter:
   - Name: `Keyboard`
   - SKU: `KB-001`
   - Quantity: `5`
   - Price: `49.99`
   - Available: checked
   - Restock date: `2026-10-10`
3. Save.
4. Open the product.
5. Click **Edit** and change the price.
6. Delete another test product.

Try invalid values too, for example a negative quantity or invalid API types.

---

# 3. Test the public API

Open:

```text
http://127.0.0.1:5000/api/products
```

### Create with curl

```bash
curl -X POST http://127.0.0.1:5000/api/products \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Mouse\",\"sku\":\"MS-001\",\"quantity\":10,\"price\":19.99,\"available\":true,\"restock_date\":\"2026-10-10\",\"description\":\"Wireless mouse\"}"
```

### Update

```bash
curl -X PATCH http://127.0.0.1:5000/api/products/1 \
  -H "Content-Type: application/json" \
  -d "{\"price\":39.99,\"quantity\":3}"
```

### Delete

```bash
curl -X DELETE http://127.0.0.1:5000/api/products/1
```

---

# 4. Background operation demo

The app automatically starts a background scheduler.

Every **60 seconds** it:

1. finds products where `quantity == 0`;
2. changes `available` to `false`;
3. writes a run record to the `background_events` database table.

Easy demonstration:

1. Create a product with quantity `0`.
2. Leave **Available** checked.
3. Wait for the automatic run, or press **Run now**.
4. Refresh the page.
5. The product is now unavailable.
6. The background run appears at the bottom of the page.

---

# 5. File storage

Images can be uploaded in the Create/Edit form.

## Simple local mode

Without Cloudinary, images are stored in:

```text
static/uploads/
```

This is enough for local development. On a normal free Render web service the local filesystem is ephemeral, so an uploaded file can disappear after a restart/redeploy.

## Persistent cloud file storage with Cloudinary

For a better final demo:

1. Create a Cloudinary account.
2. Copy your `CLOUDINARY_URL`.
3. In Render open your web service → **Environment**.
4. Add:

```text
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

5. Save and redeploy.

The application detects this variable automatically and stores new uploaded images in Cloudinary.

Never commit the real Cloudinary secret to GitHub.

---

# 6. Push to GitHub

From the project folder:

```bash
git init
git add .
git commit -m "Create CRUD product manager"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Later changes:

```bash
git add .
git commit -m "Describe your change"
git push
```

---

# 7. Deploy to Render

The repository already contains `render.yaml` and `.python-version`.

The `.python-version` file pins the project to Python 3.13 on Render for predictable dependency compatibility.

## Recommended: Render Blueprint

1. Push this project to GitHub.
2. Open Render Dashboard.
3. Choose **New → Blueprint**.
4. Connect your GitHub repository.
5. Render reads `render.yaml`.
6. It creates:
   - a Python web service;
   - a PostgreSQL database;
   - the `DATABASE_URL` link automatically.
7. Deploy.
8. Open the generated `https://...onrender.com` URL.

`render.yaml` uses one Gunicorn worker intentionally so the in-process scheduler is not started multiple times.

### Important about the free PostgreSQL database

Render's free PostgreSQL database is suitable for this student demo, but free databases currently expire after 30 days. Create it close enough to the assignment/demo date.

---

# 8. Add Cloudinary on Render

After the Render web service exists:

1. Web Service → **Environment**.
2. Add `CLOUDINARY_URL`.
3. Paste the secret Cloudinary URL.
4. Save and redeploy.
5. Upload an image and verify that the product detail page still shows it.

---

# 9. Architecture drawing

Open:

```text
docs/architecture.svg
```

or view the Mermaid source in:

```text
docs/architecture.md
```

Architecture:

```text
Browser / API client
        |
        v
+-----------------------+
| Flask app on Render   |
| Web UI + REST API     |
+----------+------------+
           |
       +---+----------------+
       |                    |
       v                    v
 PostgreSQL            Cloudinary
 persistent DB         file storage
       ^
       |
 Background scheduler
 every 60 seconds
```

---

# 10. What to say during the defence

Short version:

> This application is a product manager built with Python Flask and deployed as a PaaS web service on Render. It implements full CRUD functionality and a public REST API. PostgreSQL provides persistent data storage. Create and update operations validate string, integer, decimal number, boolean and date values. Product images are stored using file storage, with Cloudinary supported for persistent cloud files. An APScheduler background operation runs every 60 seconds and automatically marks products with zero quantity as unavailable. The architecture separates the browser/API client, Flask application, PostgreSQL database, file storage and background processing.

### Live demonstration order

1. Open the deployed Render URL.
2. Create a product.
3. Show that invalid input is rejected.
4. Edit the product.
5. Open `/api/products` and show JSON.
6. Upload/show an image.
7. Create a product with quantity `0` but Available checked.
8. Demonstrate the background operation.
9. Delete a product.
10. Show `docs/architecture.svg`.

---

# 11. API data types to mention

| Field | Data type | Validation |
|---|---|---|
| `name` | string | 2–80 characters |
| `sku` | string | 2–30 characters, unique |
| `quantity` | integer | >= 0 |
| `price` | decimal / number | >= 0 |
| `available` | boolean | true/false |
| `restock_date` | date | YYYY-MM-DD or null |

This gives more than the required four different data types.
