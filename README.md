# SkillPath — AI-Powered Career Accelerator 🚀

**SkillPath** is a production-grade, multi-feature AI platform designed to transform your career journey. From personalized skill recommendations and brutal resume analysis to company-specific interview prep — all backed by a Supabase cloud database, Flask backend, and Groq AI intelligence.

---

## ✨ Key Features

### 1. 🧠 AI-Powered Skill Recommendations
- **Hybrid Search Engine**: Instant results for core skills (Python, Java, C++, DSA) via curated local datasets, with smart fallback to **Groq (Llama-3.3 70B)** for any topic.
- **Multi-Step Flow**: Progress from curated YouTube playlists → professional certifications (Coursera, edX, etc.).
- **Language Filtering**: Results returned in your preferred language.
- **Level Filtering**: Match resources to your level — Beginner, Intermediate, or Advanced.

### 2. 🕒 Recent Searches (Supabase-Powered)
- Every search is **persisted in Supabase** for cross-session history.
- View and re-run past searches instantly from the sidebar.

### 3. 🛡️ Elite AI Resume Evaluator
- **Multi-Stage Simulation**: ATS scanner → recruiter snap judgment → hiring manager deep-dive.
- **Brutal Scoring**: Final score /10, hire verdict, market positioning.
- **Actionable Output**: Project ideas, tools to learn, and bullet-point rewrites.
- **File Support**: PDF and DOCX uploads via drag & drop.

### 4. 🎯 DSA Command Center
- **Company-Wise Question Bank**: Frequency-sorted LeetCode questions for 100+ top companies.
- **Progress Tracking**: Mark problems as solved, track revisions, view streaks.
- **Dashboard Consistency Chart**: 7-day consistency graph and doughnut difficulty breakdown.

### 5. 📊 SaaS-Level Performance Analytics
- **Readiness Index (PRI)**: A dynamically calculated index of prep fitness, complete with a circular progress animation and standard benchmarks (e.g. Novice, Proficient, FAANG Tier).
  `PRI = (DSA_Score * 0.4) + (Resume_Score * 0.3) + (Playlist_Progress * 0.15) + (Projects_Score * 0.15)`
- **Skills Alignment Radar**: Chart.js Radar comparing candidate competency in Data Structures, System Design, AI/ML, and Dev against FAANG benchmarks.
- **Cumulative Growth Area Chart**: Plots chronological solved question history over selected timeframe (7 days, 30 days, or all-time).
- **30-Day Practice Heatmap**: GitHub-style interactive activity blocks tracking daily learning commits (DSA solved + video playlists completed) with date tooltips.
- **AI Competency & Benchmark Audit**: Groq-powered career intelligence audit assessing market ready tiers (Intern, L3, L4, L5), technical gaps, action items checklist, and estimated timeline to target. Cached directly in Supabase for instant loads.

### 6. 🛠️ Roadmap Project Auto-Sync
- Linked active roadmap checklists directly to the Projects tab portfolio. Checking/unchecking a project inside the roadmap checklist dynamically logs/removes it in the Projects view and synchronizes the state across session stores.

### 7. 🔐 Animated Login System
- **Premium dark-themed login/signup page** with animated glassmorphic UI.
- **Flask session-based authentication** — protected routes, signup, logout.
- **Google OAuth UI** ready for Supabase Auth integration.

### 8. ☁️ Supabase Cloud Backend
- **PostgreSQL database** with production tables.
- **Row Level Security (RLS)** policies for per-user data isolation.
- **Private storage bucket** for resume file uploads.
- **Auto-profile trigger** on user signup.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python · Flask · Pandas |
| **AI Engine** | Groq API (Llama-3.3-70b-versatile) |
| **Database** | Supabase (PostgreSQL + RLS + Storage) |
| **Frontend** | Vanilla HTML5 · CSS3 · JavaScript |
| **Auth** | Flask Sessions (Supabase Auth ready) |
| **Parsing** | `pypdf` · `docx2txt` |
| **Charts** | Chart.js |

---

## 📁 Project Structure

```text
AI-CATALYST/
├── app.py                        # Flask backend, AI logic, auth routes
├── requirements.txt              # Python dependencies
├── .env                          # API Keys & Supabase credentials
├── README.md                     # Documentation
│
├── static/
│   ├── login.html                # Animated login & signup page
│   ├── index.html                # Main SPA dashboard
│   ├── css/style.css             # Nebula Design System & heatmaps
│   └── js/
│       ├── app.js                # Frontend orchestration
│       └── supabaseClient.js     # Supabase DB service layer
│
├── supabase/
│   ├── consolidated_schema.sql   # Complete idempotent Supabase setup script
│   ├── config.toml               # Supabase project config
│   └── migrations/
│       ├── 20240501000000_initial_schema.sql
│       ├── 20240502000000_ai_engine_tables.sql
│       └── ...
│
└── data/
    ├── leetcode-companywise-*/   # Company-specific LeetCode CSVs
    ├── certifications/           # Professional course data
    └── *.csv                     # Curated skill playlists
```

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/P-adithyagoud/AI-CATALYST.git
cd AI-CATALYST
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key_here
SECRET_KEY=your_flask_secret_key
```

### 4. Set Up Supabase Database
Go to your **Supabase Dashboard → SQL Editor**, paste the SQL from `supabase/consolidated_schema.sql` (or `supabase/migrations/20240502000000_ai_engine_tables.sql`), and click **Run**.

### 5. Run the Application
```bash
python app.py
```
Open your browser: **`http://localhost:5000`**

The app will redirect you to the login page. Sign up with any email + 6-character password to access the dashboard.

---

## 🖇 API Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/login-page` | Serve the animated login UI | No |
| `POST` | `/login` | Authenticate user, create session | No |
| `POST` | `/signup` | Register user, create session | No |
| `GET` | `/logout` | Destroy session, redirect to login | Yes |
| `GET` | `/` | Main dashboard (protected) | Yes |
| `POST` | `/get-resource` | AI skill recommendations | Yes |
| `POST` | `/analyze-resume` | Elite AI resume evaluation | Yes |
| `GET` | `/get-companies` | List all interview prep companies | Yes |
| `GET` | `/get-questions` | Fetch LeetCode questions by company | Yes |
| `POST` | `/generate-competency-audit` | Aggregates user metrics and queries Groq for career readiness | Yes |
| `GET` | `/get-competency-audit` | Retrieves user's latest competency audit from Supabase | Yes |
| `POST` | `/sync-user-projects` | Synchronize custom projects portfolio list to database | Yes |
| `GET` | `/get-user-projects` | Retrieve custom projects portfolio list | Yes |
| `POST` | `/sync-active-roadmap` | Sync current roadmap checklist progress | Yes |
| `GET` | `/get-active-roadmap` | Retrieve current active roadmap checklist | Yes |

---

## 🗄 Database Schema

| Table | Purpose |
|---|---|
| `profiles` | User info, auto-created on signup via trigger |
| `recent_searches` | Per-user search history with skill, level, language |
| `resume_analysis` | Full AI analysis JSON + scores per user |
| `dsa_progress` | Solved LeetCode problems with difficulty counts |
| `learning_progress` | User roadmap checkboxes, saved playlists, custom project arrays, and AI competency audit caching |
| `success_metrics` | Logged milestones (e.g. roadmap completes, resume improved, certified) |

**Storage:** Private `resumes` bucket (10MB limit, PDF/DOCX only) with per-user folder isolation.

---

## 🎨 Design Philosophy

SkillPath uses the **Nebula Design System** — a premium SaaS aesthetic built on:
- **Glassmorphism** — Sleek, semi-transparent UI components with blur effects.
- **Micro-animations** — Smooth hover states, entrance animations, and transitions.
- **Dark-first** — A deep, rich dark theme with indigo/violet gradient accents.
- **Data Density** — Dashboard-style layouts that surface insights at a glance.

---

*Built with ❤️ for the next generation of engineers.*
