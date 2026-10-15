# RESQ-OS: Autonomous AI Disaster Response & Rescue Coordination System
> **“Every Signal Matters. Every Response Counts.”**
> 
> *A 24-hour hackathon MVP engineered for operational reliability, explainable AI triage, and human-in-the-loop disaster coordination.*

---

## 🚨 System Overview

**RESQ-OS** is an autonomous emergency response coordination platform designed to convert raw emergency distress signals into actionable, explainable triage assessments, recommend suitable rescue resources, and empower human dispatchers to verify, assign, and track missions in real-time.

### Key Capabilities
- **Emergency Signal Intake**: Structured incident reporting with category, coordinates, casualty headcount, narrative transcripts, and instant test presets.
- **Explainable Triage Engine**: Transparent evaluation of urgency (`Critical`, `High`, `Medium`, `Low`), extracted risk factors, required operational capabilities, and an uncertainty index. Operates with an offline deterministic heuristic fallback engine and supports optional LLM integration (OpenAI / Gemini).
- **Intelligent Resource Recommendation**: Matches specialized rescue assets (Swiftwater boats, heavy US&R, HAZMAT, aerial drones, ALS paramedic units) based on capabilities, live availability, and real Haversine distance calculation (when coordinates exist).
- **Human Dispatcher Control**: Mandatory human approval for simulated assignments, manual urgency overrides with field rationale, and lifecycle status progression (`Reported` → `Verified` → `Assigned` → `En Route` → `Resolved`).
- **Geospatial Tactical Map**: Interactive Leaflet/OpenStreetMap command map featuring pulsing urgency rings, fleet markers, and click-to-focus triage workbench.

---

## 🛠️ Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | React 19 + Vite 8 | JavaScript, Leaflet, React-Leaflet, Lucide Icons |
| **Styling** | Vanilla CSS Design System | Tactical dark command center theme, high-contrast, responsive |
| **Backend** | Python 3.10 + FastAPI | Uvicorn ASGI server, Pydantic 2.9 validation |
| **Database** | SQLite + SQLAlchemy 2.0 | Zero-dependency local persistence (`resq_os.db`) |
| **Database Migration** | MongoDB Atlas Ready | Configuration guide & schema mapping included below |
| **Triage AI** | Dual Engine | Deterministic heuristic scorer + Configurable OpenAI/Gemini adapter |

---

## 🚀 Quickstart Guide (Windows PowerShell)

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Backend Setup & Run

Open a Windows PowerShell terminal:

```powershell
# Navigate to backend folder
cd backend

# (Optional) If you want to configure environment variables:
Copy-Item .env.example .env

# Run the FastAPI server
python run.py
```
> The backend server starts at **`http://localhost:8000`**.  
> Interactive Swagger API docs are available at **`http://localhost:8000/docs`**.

### 2. Frontend Setup & Run

Open a second Windows PowerShell terminal:

```powershell
# Navigate to frontend folder
cd frontend

# Install dependencies (already cached if cloned)
npm install

# Start Vite development server
npm run dev
```
> The frontend command center opens at **`http://localhost:5173`**.

---

## 🔐 Environment Variables & Configuration

A template configuration is provided in [`backend/.env.example`](file:///c:/Users/LENOVO/OneDrive/Desktop/resq-os/backend/.env.example):

```ini
# Database (Default: local SQLite database)
DATABASE_URL=sqlite:///./resq_os.db

# Optional: MongoDB Atlas (see section below)
# MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/resq_os?retryWrites=true&w=majority

# Server Settings
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Simulation Safety Flag
SIMULATION_MODE=true

# Optional LLM API Keys
OPENAI_API_KEY=
GEMINI_API_KEY=
```

> **Security Note:** Never commit live API keys or credentials. If no LLM key is configured, RESQ-OS automatically activates its deterministic heuristic engine with full explainability.

---

## 🔄 Switching to MongoDB Atlas

To connect MongoDB Atlas in production:
1. Create a cluster on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Set your connection URI in `backend/.env`:
   ```ini
   MONGODB_URI=mongodb+srv://<db_user>:<db_password>@cluster0.mongodb.net/resq_os?retryWrites=true&w=majority
   ```
3. Install `motor` or `pymongo` (`pip install motor pymongo`). The backend schema models in [`app/schemas.py`](file:///c:/Users/LENOVO/OneDrive/Desktop/resq-os/backend/app/schemas.py) are directly serializable into BSON/JSON collections.

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check, triage engine mode, simulation notice |
| `GET` | `/api/dashboard/stats` | Aggregated command center telemetry & counts |
| `GET` | `/api/incidents` | List incidents with search and filters (`status`, `urgency`) |
| `POST` | `/api/incidents` | Intake new emergency signal, trigger AI triage, store to DB |
| `GET` | `/api/incidents/{id}` | Retrieve incident details, assigned unit, and action logs |
| `PATCH` | `/api/incidents/{id}/status` | Advance incident workflow (`Reported` → `Verified` → `Assigned` → `En Route` → `Resolved`) |
| `PATCH` | `/api/incidents/{id}/urgency` | Human dispatcher urgency override with rationale note |
| `POST` | `/api/incidents/reset-demo` | Reset database to pristine fictional demo scenario |
| `GET` | `/api/resources` | List all simulated emergency assets and availability |
| `GET` | `/api/incidents/{id}/recommendations` | Compute match scores, capabilities, and Haversine distance |
| `POST` | `/api/incidents/{id}/assignments` | Approve and deploy simulated unit to an incident |
| `POST` | `/api/incidents/{id}/unassign` | Release unit back to Available standby status |

---

## 🎬 3-Minute Hackathon Demo Script

1. **Mission Introduction (30s)**:
   - Present the tagline: *“Every Signal Matters. Every Response Counts.”*
   - Point out the top header: Live UTC clock, simulation indicator, and active signal counters.
   - Show the geospatial Leaflet map with pulsing emergency markers and deployed fleet units.
2. **Emergency Intake & Explainable Triage (60s)**:
   - Click **"+ Report Incident"**.
   - Select the preset: *“Flash Flood at Downtown Underpass”* or type a custom emergency report.
   - Click **"Dispatch Signal to Triage"**.
   - Show how the AI triage engine immediately flags life-safety triggers (`trapped`, rising water), calculates the heuristic score, marks required capabilities, and scores uncertainty.
3. **Dispatcher Decision Support & Mission Assignment (60s)**:
   - Click on the new incident in the **Signal Triage Queue**.
   - Demonstrate the **Dispatcher Override**: adjust urgency from High to Critical with a field rationale note and click save. Notice the audit log record created.
   - Review the **Resource Recommendations**: explain how the algorithm matched *Swiftwater Rescue Boat Alpha-1* based on capabilities overlap and calculated real Haversine distance (~2.2 km).
   - Click **"Approve & Dispatch Unit"**. Notice the unit status switches to Assigned, the incident links to the asset, and the audit trail updates.
4. **Lifecycle Resolution & Persistence (30s)**:
   - Advance the status: click **"En Route"**, then click **"Resolved"**.
   - Refresh the browser page (`F5`) to demonstrate that SQLite persisted all data, status updates, and audit logs.

---

## ⚖️ Safety & Simulation Disclaimer
*RESQ-OS is a disaster-response coordination software prototype built for hackathon demonstration and operational research. It does NOT connect to real-world 911/112 public safety answering points and does NOT claim medically validated triage. All emergency reports and resources in demo mode are fictional.*
