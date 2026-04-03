# IntelliKnow KMS – Complete Design Document

## 1. Project Overview

### 1.1 Background & Objectives
IntelliKnow KMS is an AI‑powered knowledge management system that addresses fragmented enterprise information, inefficient knowledge retrieval, and siloed communication channels. It provides document‑driven knowledge base construction, multi‑channel frontend integration (Telegram, Microsoft Teams), intelligent query intent classification and routing, and a full‑featured admin dashboard.

### 1.2 Core Features
- **Multi‑Channel Access**: Telegram Bot and Microsoft Teams Bot; users can query directly from chat tools.
- **Document Knowledge Base**: Upload PDF, DOCX documents; automatic parsing, vectorization, and storage with semantic search.
- **Intent Classification & Routing**: Predefined intent spaces (HR, Legal, Finance) plus custom spaces; AI classifies user queries and routes to the relevant knowledge domain.
- **Admin Dashboard**: Pages for integrations, KB management, intent configuration, and analytics.

### 1.3 Technology Stack

| Layer          | Technology                                                       |
|----------------|------------------------------------------------------------------|
| Frontend       | Vue 3 (TypeScript) + Vite + Element Plus / Naive UI              |
| Backend        | Python 3.10+ + FastAPI + SQLite + LangChain                      |
| AI Integration | OpenAI standard interface (supports GPT‑5, DeepSeek 3.2, swappable) |
| Vector Store   | SQLite with `sqlitevec` extension                                |
| Full‑Text Search| SQLite FTS5 (Virtual table)                                      |
| Deployment     | Docker Compose or local run; supports Render / Vercel frontend hosting |
| Version Control| GitHub (public repository)                                       |

> **Note**: Hybrid search combines FTS5 (full‑text) and sqlitevec (vector) with configurable weights (text: 0.3, vector: 0.7) for ranking.

### 1.4 Constraints
- Timeline: 7 calendar days (1 person)
- Must support at least 2 frontend channels (Telegram + Teams)
- Support at least 2 document formats (PDF, DOCX)
- AI intent classification confidence threshold configurable, default ≥70%
- End‑to‑end response latency ≤3 seconds

---

## 2. Overall Architecture

### 2.1 Architecture Diagram (Textual)

```
[User] <--> [Telegram / Teams] <--> [Bot Adapter] <--> [FastAPI Gateway]
                                                           |
[Admin] <--> [Vue Admin Dashboard] <------------------------>|
                                                           |
                      +------------------+-----------------+
                      |                  |
              [Intent Classifier]   [Hybrid Retriever]
                    (LLM)          (FTS5 + sqlitevec)
                      |                  |
                      +--------+---------+
                               |
                        [SQLite Database]
```

### 2.2 Core Components

| Component           | Responsibility                                                                                  |
|---------------------|-------------------------------------------------------------------------------------------------|
| **Bot Adapter**     | Receives Telegram/Teams messages, converts to internal events, calls backend API.               |
| **FastAPI Gateway** | Unified entry: authentication, routing, rate limiting, logging. Exposes REST APIs for frontend and bots. |
| **Intent Classifier** | Invokes LLM to classify user queries (HR/Legal/Finance/General).                                 |
| **Hybrid Retriever** | Performs combined search using SQLite FTS5 (full‑text) and sqlitevec (vector) with weighted scoring (text 0.3, vector 0.7). Returns ranked document chunks. |
| **Knowledge Engine** | Document parsing, chunking, embedding (vectorization).                                          |
| **Admin Frontend**  | Vue 3 SPA providing configuration, monitoring, and analytics interfaces.                        |

### 2.3 Data Flow Example (User Query)

1. User sends `/ask How many vacation days do I have?` in Telegram.
2. Telegram Bot receives message, POSTs it to FastAPI `/api/bot/message` via webhook or polling.
3. FastAPI validates source, extracts text.
4. Intent classifier calls LLM; returns `intent: HR`, confidence 0.92.
5. Based on intent, the hybrid retriever executes:
   - FTS5 query on `fts_chunks` (full‑text) → returns a set of chunks with BM25 scores.
   - Vector query on `vec_chunks` (cosine similarity) → returns another set with distances.
   - Combine both sets, normalise scores, and compute weighted rank: `final_score = 0.3 * text_score + 0.7 * (1 - vector_distance)`.
6. Top‑k chunks are used to build a prompt for the LLM, which generates a final answer with citations.
7. Answer sent back to Telegram via Bot API.
8. Query log recorded in SQLite (time, user, intent, confidence, response time, and the most relevant document ID from the retrieved chunks).

---

## 3. Page Design (Vue Admin Dashboard)

**Layout**: Left side navigation menu + right content area; responsive for desktop/tablet.

### 3.1 Page List

| Page Name          | Route           | Description                                                                                  |
|--------------------|-----------------|----------------------------------------------------------------------------------------------|
| Dashboard          | `/dashboard`    | Overview panel showing key metrics and quick action cards for the four core modules.         |
| Frontend Integrations | `/integrations` | Configure Telegram / Teams Bot tokens, webhook URLs, test connections, view status.          |
| Knowledge Base     | `/kb`           | Upload documents (drag‑and‑drop or file picker), document list (name, upload date, format, size, status), delete/re‑parse. |
| Intent Configuration| `/intents`      | Manage intent spaces (HR, Legal, Finance, General, Custom), edit keywords, view classification logs. |
| Analytics & Logs   | `/analytics`    | Query history table, key metric cards, intent distribution, top documents, export CSV.       |

### 3.2 Pages Descriptions

#### Dashboard Cards
- **Layout**: Four cards in a responsive grid; two per row on desktop, stacked on mobile.
- **Style**: Rounded corners (12px), padding 16px, white background with light shadow. Each card with distinct accent colors (blue=Frontend, green=KB, purple=Intent, orange=Analytics).
- **Interaction**: Cards are not clickable; only action buttons trigger navigation (Vue Router).
- **Data Refresh**: Page polls `/api/v1/analytics/dashboard-summary` every 30 seconds; manual refresh button available.

| Card Name              | Displayed Content                                                | Quick Action Button                        | Target Route      |
|------------------------|------------------------------------------------------------------|--------------------------------------------|-------------------|
| **Frontend Integration** | List of connected frontend tools (Telegram / Teams) and their status (🟢 Connected / 🔴 Disconnected) | “Add Integration” → `/integrations`        | `/integrations`   |
| **KB Management**      | Total documents, processed documents, pending documents          | “Upload Document” → `/kb`                  | `/kb`             |
| **Intent Configuration**| List of defined intent spaces (HR, Legal, Finance, etc.) and associated document counts | “Create Intent Space” → `/intents`         | `/intents`        |
| **Analytics**          | **Total number of queries** (e.g., “Total Queries: 1,240”)       | “View Detailed Logs” → `/analytics`        | `/analytics`      |

#### Frontend Integrations Page
- **Layout**: Two cards side by side (Telegram, Teams). Each card displays:
  - Channel name and icon
  - Status (Connected / Disconnected) with color indicator
  - Last test timestamp (if any)
  - A **“Test” button** (placed directly on the card)
- **Interaction**: The entire card is **clickable** and opens a **modal edit form**. Clicking the “Test” button sends a test message without opening the modal.
- **Modal Edit Form** (appears when clicking the card):
  - **Telegram**:
    - `Bot Token` (text field, required)
  - **Teams**:
    - `App ID` (text field, required)
    - `App Secret` (password field, required)
    - `Tenant ID` (text field, optional; for multi‑tenant apps)
  - After saving, the configuration is stored (encrypted) and the card’s status updates. No automatic test is performed.
- **Test Button**: Clicking the “Test” button sends a sample message to verify the credentials; result shown as a toast notification.

#### Knowledge Base Management Page
- **Upload Area**: A prominent drag‑and‑drop zone (or file picker button) is always displayed at the top of the page. It clearly states: “Drag & drop a file here or click to browse. Supported formats: PDF, DOCX (max 20MB).”
- **Upload Flow**:
  1. The user drops a file or clicks to select one.
  2. Immediately after file selection, a **modal dialog** opens.  
     - The modal shows the file name and asks: **“Select Intent Space (optional)”** with a dropdown listing all intent spaces (HR, Legal, Finance, General, etc.).  
     - A “Upload” button starts the upload.  
     - The user can also close the modal without uploading.
  3. On submit, the file is sent to the backend with the selected intent space ID (if any). The document appears in the table with status `pending`.
  4. The document table is automatically **reloaded** (via polling or WebSocket) to reflect the new entry and status changes (`pending` → `processed` or `error`).
- **Document Table**: Columns: `Name`, `Upload Date`, `Format`, `Size`, `Intent Space`, `Status`, `Actions` (View/Delete/Reparse/Edit Intent).  
  - **Edit Intent** opens a modal to reassign the document to another intent space, which updates the table without requiring re‑upload.  
- **Auto‑Refresh**: The table polls the backend every 5 seconds while any document is in `pending` status, and stops polling once all are processed. After a successful upload, the table is immediately refreshed to show the new row.

#### Intent Configuration Page
- **Layout**:
  - **Top**: Horizontal (or grid) list of intent space cards, each showing:
    - Name (e.g., HR, Legal, Finance, General, Custom)
    - Description (short)
    - Number of associated documents
    - Classification accuracy rate
    - An edit icon (pencil) and a delete icon (trash) for each card.
    - A “+” icon button (floating or at the end) to add a new intent space.
  - Clicking on a card (or the edit icon) opens a **modal form** with fields:
    - `Name` (text, required)
    - `Description` (textarea)
    - `Keywords` (text, comma‑separated) – used to improve classification.
    - (Optionally) `Associated Documents` (multi‑select) – to manually link documents.
  - **Middle**: Classification log table (showing recent queries with intent, confidence, etc.).
  - **Bottom**: (Optional) Pagination for the log table.

#### Analytics Page
**Purpose**: Provides core system metrics and historical logs.

**Layout and Modules**:
1. **Key Metric Cards** – One row, three cards:
   - **Total Queries**: Total number of queries in the system.
   - **Avg Response Time (ms)**: Average response time across all queries.
   - **Avg Classification Accuracy**: Accuracy based on admin feedback (`user_feedback='correct'`) calculated overall.
2. **Intent Space Distribution** – Pie chart or bar chart showing the count of queries per intent space (HR, Legal, Finance, General, etc.).
3. **Top Documents** – Table listing documents sorted by the number of times they were retrieved (hit count). Columns: `Document Name`, `Hit Count`, `Associated Intent Space`.
4. **Query History Log** – Table with pagination and search (by user, query text, intent). Columns:
   - `Timestamp`
   - `Source` (Telegram / Teams / Web)
   - `User ID`
   - `Query Text`
   - `Intent`
   - `Confidence`
   - `Response Time (ms)`
   - `User Feedback` (correct/wrong/null; clickable buttons to correct)
5. **Export** – Button to export the current filtered query log as CSV.

---

## 4. Backend Module Structure

```
backend/
├── api/                     # Routing layer
│   ├── v1/
│   │   ├── auth.py          # Admin login (JWT)
│   │   ├── bot.py           # Telegram/Teams message handling
│   │   ├── admin.py         # Admin APIs (document upload, configs, logs)
│   │   └── analytics.py     # Analytics data endpoints
├── core/                    # Core business logic
│   ├── classifier.py        # Intent classifier (LLM calls)
│   ├── hybrid_retriever.py  # Hybrid search (FTS5 + vector) with weighting
│   ├── document_parser.py   # PDF/DOCX parsing, chunking
│   ├── embedding.py         # Embedding model client
│   └── document_store.py    # Unified storage for documents, text (FTS5) & vectors (sqlitevec)
├── models/                  # SQLAlchemy ORM models
├── schemas/                 # Pydantic models (request/response)
├── services/                # External integrations
│   ├── telegram.py
│   ├── teams.py
│   └── llm_factory.py       # Unified LLM client (model switching)
├── utils/                   # Utilities (logging, config, exceptions)
├── data/                    # SQLite database file (includes FTS5 & vector tables)
├── uploads/                 # Uploaded original documents (optional)
├── main.py                  # FastAPI entry point
└── requirements.txt
```

---

## 5. API Design (REST)

All endpoints are prefixed with `/api/v1`. Admin authentication uses **JWT** (Bearer token).

### 5.1 Authentication

| Method | Endpoint         | Description                          |
|--------|------------------|--------------------------------------|
| POST   | `/auth/login`    | Authenticate admin, return JWT       |

**POST /auth/login**
- **Request Body**:
  ```json
  {
    "username": "admin",
    "password": "secret"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
  ```
- **Error**: 401 Unauthorized if credentials invalid.

All subsequent admin endpoints (except bot webhooks) require the `Authorization: Bearer <token>` header.

### 5.2 Bot Message Endpoints (for Telegram/Teams callbacks)

| Method | Endpoint               | Description                                 |
|--------|------------------------|---------------------------------------------|
| POST   | `/bot/message`         | Receive messages from frontend channels     |
| POST   | `/bot/teams/webhook`   | Teams‑specific webhook (can be separate)    |

**POST /bot/message**
- **Request Body** (JSON):
  ```json
  {
    "source": "telegram",     // "telegram" or "teams"
    "chat_id": "123456789",   // channel-specific user/chat ID
    "text": "How many vacation days do I have?"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "status": "success",
    "response": "According to the HR policy, you have 20 vacation days per year."
  }
  ```
- **Error Responses**:
  - 400: Missing fields
  - 401: Invalid source
  - 500: Internal server error

**POST /bot/teams/webhook**
- **Request Body**: Teams standard activity object (JSON)
- **Response**: 202 Accepted (empty body) – Teams expects immediate acknowledgment.

### 5.3 Admin Endpoints

All endpoints require JWT.

#### Knowledge Base Management

| Method | Endpoint                          | Description                       |
|--------|-----------------------------------|-----------------------------------|
| POST   | `/kb/upload`                      | Upload document (multipart/form)  |
| GET    | `/kb/documents`                   | Paginated document list           |
| DELETE | `/kb/documents/{id}`              | Delete document and related vectors |
| POST   | `/kb/documents/{id}/reparse`      | Re‑parse document                 |
| PUT    | `/kb/documents/{id}/intent`       | Change document's intent space    |

**POST /kb/upload**
- **Request**: `multipart/form-data` with:
  - `file` (binary) – the document
  - `intent_space_id` (integer, optional) – ID of the intent space to associate with the document. If omitted, the document is not linked to any specific space.
- **Response** (201 Created):
  ```json
  {
    "id": 123,
    "name": "HR_Policy.pdf",
    "format": "pdf",
    "size_bytes": 1048576,
    "upload_time": "2025-03-31T10:00:00Z",
    "status": "pending",
    "intent_space_id": 1,
    "intent_space_name": "HR"
  }
  ```

**GET /kb/documents**
- **Query Parameters**:
  - `page` (int, default 1)
  - `page_size` (int, default 20)
  - `search` (string, optional) – filter by document name
  - `status` (string, optional) – one of `pending`, `processed`, `error`
  - `intent_space_id` (int, optional) – filter by intent space
- **Response** (200 OK):
  ```json
  {
    "total": 42,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "id": 1,
        "name": "HR_Policy.pdf",
        "format": "pdf",
        "size_bytes": 1048576,
        "upload_time": "2025-03-30T09:00:00Z",
        "status": "processed",
        "intent_space_id": 1,
        "intent_space_name": "HR"
      }
    ]
  }
  ```

**DELETE /kb/documents/{id}**
- **Response**: 204 No Content

**POST /kb/documents/{id}/reparse**
- **Response** (202 Accepted):
  ```json
  { "status": "reparse started" }
  ```

**PUT /kb/documents/{id}/intent**
- **Request Body**:
  ```json
  { "intent_space_id": 2 }
  ```
- **Response**: 200 OK with updated document object.

#### Intent Configuration

| Method | Endpoint                          | Description                       |
|--------|-----------------------------------|-----------------------------------|
| GET    | `/intents`                        | List all intent spaces            |
| POST   | `/intents`                        | Create a new intent space         |
| PUT    | `/intents/{id}`                   | Update intent (keywords, etc.)    |
| DELETE | `/intents/{id}`                   | Delete intent space               |
| GET    | `/intents/{id}/queries`           | Get query logs for that intent    |

**GET /intents**
- **Response** (200 OK):
  ```json
  {
    "data": [
      {
        "id": 1,
        "name": "HR",
        "description": "Human Resources policies",
        "keywords": "vacation, leave, salary, benefits",
        "document_count": 12,
        "accuracy": 0.86
      }
    ]
  }
  ```

**POST /intents**
- **Request Body**:
  ```json
  {
    "name": "IT",
    "description": "IT support and infrastructure",
    "keywords": "password, laptop, network, VPN"
  }
  ```
- **Response** (201 Created): same as GET item.

**PUT /intents/{id}**
- **Request Body**: same as POST
- **Response** (200 OK): updated intent object

**DELETE /intents/{id}**
- **Response**: 204 No Content

**GET /intents/{id}/queries**
- **Query Parameters**:
  - `page` (int, default 1)
  - `page_size` (int, default 20)
- **Response** (200 OK): paginated list of query logs (same structure as `/analytics/queries` but filtered by intent).

#### Frontend Integration Configuration

| Method | Endpoint                          | Description                       |
|--------|-----------------------------------|-----------------------------------|
| GET    | `/integrations`                   | Get current channel configurations|
| POST   | `/integrations/telegram`          | Configure Telegram Bot Token      |
| POST   | `/integrations/teams`             | Configure Teams app credentials   |
| POST   | `/integrations/{channel}/test`    | Send test message to verify connection |

**GET /integrations**
- **Response** (200 OK):
  ```json
  {
    "data": [
      {
        "channel": "telegram",
        "is_active": true,
        "last_test_at": "2025-03-31T10:00:00Z",
        "config_hint": "token ends with ...AbCd"
      },
      {
        "channel": "teams",
        "is_active": false,
        "last_test_at": null,
        "config_hint": "not configured"
      }
    ]
  }
  ```

**POST /integrations/telegram**
- **Request Body**:
  ```json
  { "token": "123456:ABCdef..." }
  ```
- **Response** (200 OK): updated integration object.

**POST /integrations/teams**
- **Request Body**:
  ```json
  { "app_id": "your-app-id", "app_secret": "secret", "tenant_id": "common" }
  ```
- **Response** (200 OK): updated integration object.

**POST /integrations/{channel}/test**
- **Request Body** (optional):
  ```json
  { "test_message": "Hello from KMS" }
  ```
- **Response** (200 OK):
  ```json
  { "status": "success", "message": "Test message sent successfully" }
  ```

#### Analytics & Logs

| Method | Endpoint                          | Description                                                        |
|--------|-----------------------------------|--------------------------------------------------------------------|
| GET    | `/analytics/queries`              | Query history (supports search, pagination, optional filters)      |
| GET    | `/analytics/stats`                | Aggregate statistics: total queries, avg response time, accuracy   |
| GET    | `/analytics/intent-distribution`  | Intent space distribution (count per intent)                       |
| GET    | `/analytics/top-documents`        | Top documents by hit count (retrieval frequency)                   |
| GET    | `/analytics/export`               | Export query logs as CSV (based on current filters)                |
| GET    | `/analytics/dashboard-summary`    | Aggregated data for dashboard cards (overall metrics)              |

**GET /analytics/queries**
- **Query Parameters**:
  - `search` (string, optional) – filter by `user_id` or `query_text`
  - `intent_id` (int, optional) – filter by intent space
  - `page` (int, default 1)
  - `page_size` (int, default 20)
- **Response** (200 OK):
  ```json
  {
    "total": 1240,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "id": 987,
        "timestamp": "2025-03-31T09:15:00Z",
        "source": "telegram",
        "user_id": "user123",
        "query_text": "How many vacation days?",
        "intent": "HR",
        "intent_id": 1,
        "confidence": 0.92,
        "response_time_ms": 1250,
        "user_feedback": "correct"
      }
    ]
  }
  ```

**GET /analytics/stats**
- **Response** (200 OK):
  ```json
  {
    "total_queries": 1240,
    "avg_response_time_ms": 1250,
    "avg_accuracy": 0.86
  }
  ```

**GET /analytics/intent-distribution**
- **Response** (200 OK):
  ```json
  {
    "distribution": [
      { "intent": "HR", "count": 520 },
      { "intent": "Legal", "count": 380 },
      { "intent": "Finance", "count": 210 },
      { "intent": "General", "count": 130 }
    ]
  }
  ```

**GET /analytics/top-documents**
- **Query Parameters**:
  - `limit` (int, default 10, max 50)
- **Response** (200 OK):
  ```json
  {
    "documents": [
      {
        "id": 1,
        "name": "HR_Policy_2025.pdf",
        "hit_count": 45,
        "intent_space": "HR"
      },
      {
        "id": 3,
        "name": "Legal_Guidelines.docx",
        "hit_count": 32,
        "intent_space": "Legal"
      }
    ]
  }
  ```

**GET /analytics/export**
- **Query Parameters**: same as `/queries` (search, intent_id)
- **Response**: CSV file with headers:
  ```
  timestamp,source,user_id,query_text,intent,confidence,response_time_ms,user_feedback
  ```

**GET /analytics/dashboard-summary**
- **Response** (200 OK):
  ```json
  {
    "frontend_integrations": [
      {"channel": "telegram", "is_active": true, "last_test_at": "2025-03-31T10:00:00Z"},
      {"channel": "teams", "is_active": false, "last_test_at": null}
    ],
    "kb_stats": {
      "total_documents": 42,
      "processed": 38,
      "pending": 4,
      "error": 0
    },
    "intent_spaces": [
      {"id": 1, "name": "HR", "document_count": 12},
      {"id": 2, "name": "Legal", "document_count": 8}
    ],
    "analytics": {
      "total_queries": 1240
    }
  }
  ```

---

## 6. Database Design (SQLite + sqlitevec + FTS5)

Business tables are managed with SQLAlchemy ORM; vector storage uses `sqlitevec` virtual tables; full‑text search uses FTS5 virtual tables.

### 6.1 Business Tables

#### `documents`
| Column          | Type       | Description                                      |
|-----------------|------------|--------------------------------------------------|
| id              | INTEGER PK |                                                  |
| name            | TEXT       | Original file name                               |
| format          | TEXT       | pdf / docx                                       |
| size_bytes      | INTEGER    |                                                  |
| upload_time     | DATETIME   |                                                  |
| status          | TEXT       | pending / processed / error                      |
| intent_space_id | INTEGER FK | Optional, default association                    |
| error_message   | TEXT       |                                                  |

#### `chunks` (document chunks, text and metadata)
| Column          | Type       | Description                                      |
|-----------------|------------|--------------------------------------------------|
| id              | INTEGER PK |                                                  |
| document_id     | INTEGER FK | References `documents.id`                         |
| content         | TEXT       | Chunk raw text                                   |
| metadata        | TEXT JSON  | e.g., page number, section title                 |

#### `vec_chunks` (sqlitevec table)
Virtual table using `vec0` for vectors, linked to `chunks` by `rowid`.

```sql
CREATE VIRTUAL TABLE vec_chunks USING vec0(
  embedding float[384]  -- dimension matches embedding model
);
```

Insert:
```sql
INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?);
```

#### `fts_chunks` (FTS5 table for full‑text search)
```sql
CREATE VIRTUAL TABLE fts_chunks USING fts5(
  content,
  chunk_id UNINDEXED
);
```

Content is stored in `fts_chunks`, and we link back to the original chunk via `chunk_id`. After each document is parsed, we insert one row per chunk into the FTS5 table.

#### `intent_spaces`
| Column          | Type       | Description                                      |
|-----------------|------------|--------------------------------------------------|
| id              | INTEGER PK |                                                  |
| name            | TEXT       | HR / Legal / Finance / General / Custom          |
| description     | TEXT       |                                                  |
| keywords        | TEXT       | Comma‑separated keywords to assist classification|
| created_at      | DATETIME   |                                                  |

#### `query_logs`
| Column             | Type       | Description                                      |
|--------------------|------------|--------------------------------------------------|
| id                 | INTEGER PK |                                                  |
| source             | TEXT       | telegram / teams / web_admin                     |
| user_id            | TEXT       | Channel‑specific user identifier                 |
| query_text         | TEXT       |                                                  |
| intent_id          | INTEGER FK | Classified intent                                |
| confidence         | REAL       | 0–1                                              |
| response_text      | TEXT       | Answer returned to user                          |
| response_time_ms   | INTEGER    |                                                  |
| timestamp          | DATETIME   |                                                  |
| user_feedback      | TEXT       | correct / wrong / null                           |
| document_id        | INTEGER FK | Most relevant document used for the response (references `documents.id`) |

#### `integrations`
| Column          | Type       | Description                                      |
|-----------------|------------|--------------------------------------------------|
| id              | INTEGER PK |                                                  |
| channel         | TEXT       | telegram / teams                                 |
| config          | TEXT JSON  | Encrypted token / webhook URL                    |
| is_active       | BOOLEAN    |                                                  |
| last_test_at    | DATETIME   |                                                  |

### 6.2 Hybrid Search Implementation

The hybrid retriever combines FTS5 (full‑text) and vector (semantic) scores.

**Steps:**
1. **Full‑text search** using FTS5:
   ```sql
   SELECT chunk_id, bm25(fts_chunks) AS score
   FROM fts_chunks
   WHERE fts_chunks MATCH ?
   ORDER BY score;
   ```
   The BM25 score is converted to a similarity score (higher is better) by taking `1 / (1 + score)` after normalisation.

2. **Vector search** using sqlitevec:
   ```sql
   SELECT rowid, distance
   FROM vec_chunks
   WHERE embedding MATCH ?
   ORDER BY distance
   LIMIT K;
   ```
   Distance is converted to a similarity score: `sim = 1 - distance` (for cosine distance).

3. **Combine and rank**:
   - Retrieve top‑N results from both searches (e.g., top 50 each).
   - Normalise both sets of scores to the range [0,1] using min‑max normalisation.
   - Compute final score: `final_score = 0.3 * text_sim + 0.7 * vec_sim`.
   - Sort by `final_score` descending and return top‑K.

The implementation lives in `core/hybrid_retriever.py` and is used by the RAG engine.

---

## 7. Security Design

### 7.1 Authentication & Authorization
- **Admin API**: JWT‑based authentication. A login endpoint (`/api/v1/auth/login`) accepts username/password (stored in environment variables, e.g., `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH`). On success, returns a signed JWT (using `HS256` algorithm) with a short expiration (e.g., 24 hours).
- **Protected Endpoints**: All admin endpoints (except login) require the `Authorization: Bearer <token>` header. A FastAPI dependency verifies the token, extracts the user identity, and rejects invalid/expired tokens.
- **Bot Callbacks**: Telegram requests validated with `X-Telegram-Bot-Api-Secret-Token`; Teams uses Bot Framework signature validation – these do not require JWT.

### 7.2 Data Security
- Sensitive credentials (Bot tokens, Teams secrets) are encrypted with **Fernet** before storing in `integrations.config`.
- Uploaded documents stored in local filesystem with 600 permissions.
- Query logs exclude PII; `user_id` uses anonymous IDs provided by channels.

### 7.3 Input Validation & Injection Prevention
- All API inputs validated with Pydantic models; SQL injection prevented by ORM parameterization and FTS5’s safe MATCH syntax.
- User query text limited to 2000 characters; optional sensitive‑word filtering.

### 7.4 Security Recommendations
- Store JWT secret (`JWT_SECRET_KEY`) and admin credentials in environment variables.
- Use HTTPS in production (Nginx reverse proxy or cloud service).
- Rotate JWT secrets periodically and enforce short token lifetimes.

---

## 8. Deployment & Operations

### 8.1 Environment Variables

| Variable               | Description                                          | Example                              |
|------------------------|------------------------------------------------------|--------------------------------------|
| `ADMIN_USERNAME`       | Admin login username                                 | `admin`                              |
| `ADMIN_PASSWORD_HASH`  | bcrypt hash of admin password                        | `$2b$12$...`                         |
| `JWT_SECRET_KEY`       | Secret used to sign JWTs                             | `your-secret-key`                    |
| `OPENAI_API_KEY`       | OpenAI standard interface API key                    | `sk-...`                             |
| `OPENAI_BASE_URL`      | Optional, points to proxy or DeepSeek endpoint       | `https://api.deepseek.com/v1`        |
| `DEFAULT_LLM_MODEL`    | Default model name                                   | `gpt-5` or `deepseek-chat`           |
| `TELEGRAM_BOT_TOKEN`   | Optional; can be set via admin UI                    | `123:ABC...`                         |
| `TEAMS_APP_ID`         | Teams app ID (optional, can be set via UI)           |                                      |
| `TEAMS_APP_SECRET`     | Teams app secret (optional)                          |                                      |
| `TEAMS_TENANT_ID`      | Teams tenant ID (optional)                           | `common`                             |
| `DATABASE_URL`         | SQLite path                                          | `sqlite:///./data/kms.db`            |
| `HYBRID_WEIGHT_TEXT`   | Weight for full‑text search (default 0.3)            | `0.3`                                |
| `HYBRID_WEIGHT_VECTOR` | Weight for vector search (default 0.7)               | `0.7`                                |

### 8.2 Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Ensure sqlitevec is installed (pip install sqlite-vec)
# FTS5 is enabled by default in SQLite
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### 8.3 Docker Deployment (Recommended)

`docker-compose.yml` example:
```yaml
version: '3'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    env_file: .env
  frontend:
    build: ./frontend
    ports:
      - "80:80"
```

---

## 9. Summary & Extension Plans

This design document provides a complete blueprint for building IntelliKnow KMS, satisfying the 7‑day MVP requirements. Future extensions may include:
- Adding more frontend channels (WhatsApp, Slack)
- Multi‑tenancy and role‑based access control
- Replacing sqlitevec with a distributed vector database (e.g., Qdrant)
- Implementing user feedback loop for fine‑tuning classification models

> **Note**: All designs are production‑ready and testable. During implementation, priorities can be adjusted (e.g., implement Telegram first, then Teams).