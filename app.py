import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import json
import re
import io
import uuid
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from groq import Groq
try:
    from supabase import create_client, Client as SupabaseClient
except ImportError:
    SupabaseClient = None
try:
    from pypdf import PdfReader
    import docx2txt
except ImportError:
    PdfReader = None
    docx2txt = None

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY", "skillpath-dev-secret-key-2024")
CORS(app)

# ──────────────────────────────────────────────
# Supabase Client (service role — bypasses RLS)
# ──────────────────────────────────────────────
_sb: SupabaseClient = None
def get_sb():
    global _sb
    if _sb is None and SupabaseClient:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if url and key:
            try:
                _sb = create_client(url, key)
            except Exception as e:
                print(f"[DB] Supabase init failed: {e}")
    return _sb

# ──────────────────────────────────────────────
# DB Helper Functions
# ──────────────────────────────────────────────
def _skill_key(skill: str, level: str = "Beginner", language: str = "English") -> str:
    key_str = f"{skill}_{level}_{language}"
    return re.sub(r'[^a-z0-9]', '_', key_str.lower().strip())

def db_get_cached_skill(skill: str, level: str = "Beginner", language: str = "English"):
    """Step 1: Check DB cache first. Returns full response_data dict or None."""
    try:
        sb = get_sb()
        if not sb: return None
        key = _skill_key(skill, level, language)
        res = sb.table("skills_cache").select("*").eq("skill_key", key).limit(1).execute()
        if res.data:
            row = res.data[0]
            # Increment search counter asynchronously
            sb.table("skills_cache").update({"total_searches": row["total_searches"] + 1}).eq("id", row["id"]).execute()
            print(f"[DB] Cache HIT for '{skill} ({level} - {language})' (tier {row['tier']}, {row['total_searches']} searches)")
            return {
                "tier": 0,  # 0 = DB cache hit
                "skill": skill,
                "recommendations": row.get("recommendations"),
                "fallback_playlists": row.get("fallback_playlists") or [],
                "fallback_certs": row.get("fallback_certs") or [],
                "roadmap": row.get("roadmap"),
                "cache_hit": True,
                "total_searches": row["total_searches"] + 1
            }
    except Exception as e:
        print(f"[DB] Cache lookup failed: {e}")
    return None

def db_save_skill(skill: str, level: str, language: str, tier: int, source: str, response_data: dict):
    """Step 5: Persist result to DB for future instant retrieval."""
    try:
        sb = get_sb()
        if not sb: return
        key = _skill_key(skill, level, language)
        row = {
            "skill_name": f"{skill} ({level} - {language})",
            "skill_key": key,
            "tier": tier,
            "source_type": source,
            "recommendations": response_data.get("recommendations"),
            "fallback_playlists": response_data.get("fallback_playlists") or [],
            "fallback_certs": response_data.get("fallback_certs") or [],
            "roadmap": response_data.get("roadmap"),
            "total_searches": 1
        }
        sb.table("skills_cache").upsert(row, on_conflict="skill_key").execute()
        print(f"[DB] Saved '{skill} ({level} - {language})' to cache (tier={tier}, source={source})")
    except Exception as e:
        print(f"[DB] Save failed: {e}")

def db_log_recommendation(skill: str, tier: int, source: str, data: dict, session_id: str = None):
    """Step 5: Log every recommendation for analytics."""
    try:
        sb = get_sb()
        if not sb: return
        sb.table("recommendation_history").insert({
            "skill_name": skill,
            "tier": tier,
            "source_type": source,
            "recommendations_json": data,
            "roadmap_generated": bool(data.get("roadmap")),
            "session_id": session_id or "anonymous"
        }).execute()
    except Exception as e:
        print(f"[DB] Log recommendation failed: {e}")

def db_upsert_trust_score(resource_url: str, title: str, channel: str, skill: str):
    """Initialize trust score for a new resource."""
    try:
        sb = get_sb()
        if not sb: return
        sb.table("trust_score_engine").upsert({
            "resource_url": resource_url,
            "resource_title": title,
            "channel_name": channel,
            "skill_name": skill,
            "trust_score": 50.0,
            "confidence_score": 50.0
        }, on_conflict="resource_url").execute()
    except Exception as e:
        print(f"[DB] Trust score upsert failed: {e}")

def db_adjust_trust_score(resource_url: str, action: str):
    """Step 7: Auto-improve trust scores based on user actions."""
    try:
        sb = get_sb()
        if not sb: return
        res = sb.table("trust_score_engine").select("*").eq("resource_url", resource_url).limit(1).execute()
        if not res.data: return
        row = res.data[0]
        delta_map = {"click": (+2, +1), "save": (+5, +3), "ignore": (-3, -2), "complete": (+10, +8)}
        dt, dc = delta_map.get(action, (0, 0))
        new_trust = max(0, min(100, row["trust_score"] + dt))
        new_conf  = max(0, min(100, row["confidence_score"] + dc))
        count_key = f"{action}_count"
        new_count = row.get(count_key, 0) + 1
        sb.table("trust_score_engine").update({
            "trust_score": new_trust,
            "confidence_score": new_conf,
            count_key: new_count
        }).eq("resource_url", resource_url).execute()
        print(f"[DB] Trust score updated for {resource_url}: {row['trust_score']} → {new_trust}")
    except Exception as e:
        print(f"[DB] Trust score update failed: {e}")

# ──────────────────────────────────────────────
# 0. Resume Parsing Helpers
# ──────────────────────────────────────────────
def extract_text_from_file(file) -> str:
    """Extracts text from PDF or DOCX files."""
    if not PdfReader or not docx2txt:
        print("[ERROR] Dependencies missing: pypdf or docx2txt not installed.")
        return ""
    
    filename = file.filename.lower()
    try:
        if filename.endswith(".pdf"):
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        elif filename.endswith(".docx"):
            return docx2txt.process(file).strip()
        elif filename.endswith(".doc"):
            return docx2txt.process(file).strip()
        else:
            return file.read().decode("utf-8", errors="ignore").strip()
    except Exception as e:
        print(f"[ERROR] Extraction failed for {filename}: {e}")
        return ""

@app.route("/analyze-resume", methods=["POST"])
def analyze_resume():
    """Elite AI Resume Evaluator endpoint."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    role = request.form.get("role", "Software Engineer")
    level = request.form.get("level", "Experienced")
    benchmark = request.form.get("benchmark", "Average Company")
    
    resume_text = extract_text_from_file(file)
    if not resume_text:
        return jsonify({"error": "Failed to extract text from resume. Ensure it is a valid PDF or DOCX."}), 400

    prompt = f"""
You are an expert ATS Resume Reviewer and Hiring Manager with 15+ years of experience across tech roles.
Your task is to analyze a candidate's resume against a TARGET ROLE and provide a brutally honest, high-quality, actionable review.

INPUTS:
Target Role: {role}
Benchmark Standard: {benchmark} (FAANG > Tier-1 Startup > Average Company)
Resume Content: {resume_text}

---

EVALUATION FRAMEWORK:
1. ATS COMPATIBILITY: Keyword optimization, missing critical keywords, formatting issues. (Score 0-10)
2. ROLE ALIGNMENT: Match to target role, irrelevant content, missing role-specific skills. (Score 0-10)
3. IMPACT & ACHIEVEMENTS: Result-driven vs task-based, quantification (metrics/numbers). (Score 0-10)
4. STRUCTURE & CLARITY: Readability, flow, section ordering, conciseness. (Score 0-10)
5. SKILLS & PROJECTS ANALYSIS: Relevance, depth, suggestions for missing projects.

---

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "final_score": number (0-10),
  "hire_verdict": "Hire / No Hire / Borderline",
  "market_positioning": "Bottom 30% / Average / Top 20% / Top 5%",
  
  "ats_simulation": {{
    "keyword_match_score": number (0-100),
    "missing_critical_keywords": ["List important keywords missing for the target role"],
    "ats_pass_probability": "Low / Medium / High"
  }},

  "recruiter_snap_judgment": {{
    "first_impression": "Brutally honest 10-second screener summary",
    "verdict": "Shortlist / Reject",
    "top_reasons": ["List the top 5 critical issues clearly"]
  }},

  "category_breakdown": [
    {{ "category": "ATS Compatibility", "weight": "25%", "score": number, "reason": "Be critical of optimization" }},
    {{ "category": "Role Alignment", "weight": "35%", "score": number, "reason": "Identify irrelevant content vs missing skills" }},
    {{ "category": "Impact", "weight": "25%", "score": number, "reason": "Check for metrics and outcomes vs tasks" }},
    {{ "category": "Structure", "weight": "15%", "score": number, "reason": "Evaluate readability and flow" }}
  ],

  "brutal_analysis": {{
    "summary": "2-3 line direct overall evaluation",
    "competition_comparison": "Why would I pick someone else over this candidate?"
  }},

  "what_works": ["Identify what few things actually stand out"],
  
  "rejection_risk": {{
    "reason": "Step-by-step actions to improve the resume"
  }},

  "action_plan": {{
    "project_ideas": [
        {{ "title": "", "description": "", "stack": "", "outcome": "" }}
    ],
    "tools_to_learn": ["Specific certifications or tools to add"],
    "bullet_rewrites": [
        {{ "original": "Weak bullet point", "improved": "Quantified, result-driven rewrite" }}
    ]
  }}
}}

STRICT RULES:
- Be brutally honest, avoid generic praise.
- Give specific rewrites, not vague suggestions.
- Focus on impact, metrics, and role relevance.
- Assume this resume is competing at a top 10% level.
- If the resume domain doesn't match the target role, FAIL it immediately (Hire Verdict: No Hire, Score < 4).
"""


    try:
        client = Groq()
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a brutal, expert hiring manager. You hate sugarcoating and generic resumes. You penalize heavily for domain mismatches and lack of evidence."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        analysis = json.loads(completion.choices[0].message.content.strip())

        # Save analysis to Supabase
        sb = get_sb()
        user_id = session.get("user_id")
        if sb and user_id:
            try:
                sb.table("resume_analysis").insert({
                    "user_id": user_id,
                    "resume_file_url": file.filename or "uploaded_resume",
                    "ats_score": int(analysis.get("final_score", 0) * 10),
                    "ai_feedback": {
                        "verdict": analysis.get("hire_verdict", "No Hire"),
                        "ats_pass_probability": analysis.get("ats_simulation", {}).get("ats_pass_probability", "Low")
                    },
                    "improvement_suggestions": analysis.get("action_plan")
                }).execute()
            except Exception as e:
                print(f"[DB] Save resume analysis failed: {e}")

        return jsonify(analysis)
    except Exception as e:
        print(f"[ERROR] AI Analysis failed: {e}")
        return jsonify({"error": "AI Evaluation failed. Please try again."}), 500
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CERT_DIR = os.path.join(DATA_DIR, "certifications")
LEETCODE_DIR = os.path.join(DATA_DIR, "leetcode-companywise-interview-questions-master")

# Global Index: problem_link -> { 'name': str, 'companies': list }
LEETCODE_INDEX: dict[str, dict] = {}

def build_leetcode_index():
    """Scans all company CSVs to build a global cross-reference index."""
    if not os.path.exists(LEETCODE_DIR):
        print("[WARN] LeetCode directory not found.")
        return
    
    print("[INFO] Building LeetCode global index...")
    for company in os.listdir(LEETCODE_DIR):
        comp_path = os.path.join(LEETCODE_DIR, company)
        if not os.path.isdir(comp_path): continue
        
        csv_path = os.path.join(comp_path, "all.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    link = str(row.get("URL", "")).strip()
                    name = str(row.get("Title", "")).strip()
                    if not link: continue
                    
                    if link not in LEETCODE_INDEX:
                        LEETCODE_INDEX[link] = {"name": name, "companies": []}
                    
                    if company not in LEETCODE_INDEX[link]["companies"]:
                        LEETCODE_INDEX[link]["companies"].append(company)
            except Exception as e:
                print(f"[WARN] Failed to index {company}: {e}")
    print(f"[INFO] Index built: {len(LEETCODE_INDEX)} unique problems.")

# Build index once
build_leetcode_index()

# Map normalised skill slug → DataFrame
PLAYLIST_DB: dict[str, pd.DataFrame] = {}
CERT_DB:     dict[str, pd.DataFrame] = {}

CSV_SKILL_MAP = {
    "c_datastructures_tutorials.csv": ["c data structures", "data structures in c", "c datastructures"],
    "cpp_tutorials.csv":              ["c++", "cpp", "cplusplus", "c plus plus"],
    "dsa_in_cpp.csv":                 ["dsa in c++", "dsa cpp", "data structures algorithms c++", "dsa in cpp"],
    "dsa_in_java.csv":                ["dsa in java", "dsa java", "data structures algorithms java"],
    "dsa_in_python__1_.csv":          ["dsa in python", "dsa python", "data structures algorithms python"],
    "java_tutorials.csv":             ["java", "java programming", "java tutorials"],
    "python_tutorials.csv":           ["python", "python programming", "python tutorials"],
}

# Add certification files to the map
CERT_SKILL_MAP = {
    "Top_10_Python_Certifications-v2.csv": ["python", "python programming"],
    "Top_10_Java_Certifications-v4.csv":   ["java", "java programming"],
    "Top_10_CPP_Certifications-v3.csv":    ["c++", "cpp", "cplusplus"],
    "Top_10_C_Certifications-v2.csv":      ["c", "c programming"],
}

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower().strip())

# Initialize Playlists
for filename, aliases in CSV_SKILL_MAP.items():
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            df = df.loc[:, ~df.columns.str.contains("link_status", case=False)]
            for alias in aliases:
                PLAYLIST_DB[_normalize(alias)] = df
        except Exception as e:
            print(f"[WARN] Playlist load error {filename}: {e}")

# Initialize Certifications
if os.path.exists(CERT_DIR):
    for filename, aliases in CERT_SKILL_MAP.items():
        path = os.path.join(CERT_DIR, filename)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                for alias in aliases:
                    CERT_DB[_normalize(alias)] = df
            except Exception as e:
                print(f"[WARN] Cert load error {filename}: {e}")

print(f"[INFO] Playlist keys: {list(PLAYLIST_DB.keys())}")
print(f"[INFO] Cert keys: {list(CERT_DB.keys())}")

# ──────────────────────────────────────────────
# 2. Helpers: Row → Dict
# ──────────────────────────────────────────────

def row_to_playlist(row: pd.Series, rank: int) -> dict:
    url = str(row.get("playlist_url", row.get("url", ""))).strip()
    return {
        "rank":           rank,
        "title":          str(row.get("playlist_title", row.get("title", "Untitled"))).strip(),
        "channel":        str(row.get("channel_name",   row.get("channel", "Unknown"))).strip(),
        "level":          str(row.get("level", "All Levels")).strip(),
        "duration_hours": str(row.get("duration_hours", "N/A")).strip(),
        "url":            url,
        "description":    str(row.get("description", "")).strip(),
    }

def row_to_cert(row: pd.Series, rank: int) -> dict:
    return {
        "rank":           rank,
        "title":          str(row.get("Certification / Course Name", "Untitled Cert")).strip(),
        "channel":        str(row.get("Company / Provider", "Educational Provider")).strip(),
        "level":          "All Levels",
        "duration_hours": "Full Course",
        "url":            str(row.get("Link", "#")).strip(),
        "description":    f"Cost: {str(row.get('Cost Structure', 'Contact Provider'))}",
    }

# ──────────────────────────────────────────────
# 3. Helpers: Content Moderation & Search
# ──────────────────────────────────────────────

RESTRICTED_KEYWORDS = [
    "bomb", "weapon", "grenade", "explosion", "murder", "kill", "suicide",
    "drugs", "cocaine", "heroin", "meth", "fentanyl", "marijuana",
    "hack", "bypass", "crack", "ddos", "phishing", "malware", "virus",
    "porn", "sex", "nsfw", "black magic",
    "steal", "shoplifting", "robbery", "scam", "fraud"
]

def is_inappropriate(text: str) -> bool:
    """Checks if the search text contains restricted keywords using word boundaries."""
    if not text:
        return False
    
    text_lower = text.lower()
    for kw in RESTRICTED_KEYWORDS:
        # Use regex to find whole words only (e.g., 'hack' shouldn't block 'biohacking')
        pattern = rf"\b{re.escape(kw)}\b"
        if re.search(pattern, text_lower):
            return True
    return False

LEVEL_KEYWORDS = {
    "beginner":     ["beginner", "basic", "intro", "fundamental", "starter", "all"],
    "intermediate": ["intermediate", "medium", "mid", "moderate", "all"],
    "advanced":     ["advanced", "expert", "pro", "senior", "all"],
}

def _level_matches(row_level: str, requested: str) -> bool:
    rl   = row_level.lower()
    kws  = LEVEL_KEYWORDS.get(requested.lower(), ["all"])
    if "-" in rl or "to" in rl: return True
    return any(k in rl for k in kws)

def filter_by_level(df: pd.DataFrame, level: str) -> pd.DataFrame:
    if not level or level.lower() == "all" or "level" not in df.columns:
        return df
    mask = df["level"].apply(lambda v: _level_matches(str(v), level))
    filtered = df[mask]
    return filtered if not filtered.empty else df

def find_in_db(db: dict, skill: str, map_func, limit=10, level=None):
    normalized = _normalize(skill)
    # Exact match
    if normalized in db:
        df = db[normalized]
        if level: df = filter_by_level(df, level)
        return [map_func(row, i+1) for i, (_, row) in enumerate(df.head(limit).iterrows())]

    # Partial match — word-boundary safe to prevent "c" matching inside "css", etc.
    for key, df in db.items():
        key_pattern        = r'\b' + re.escape(key) + r'\b'
        normalized_pattern = r'\b' + re.escape(normalized) + r'\b'
        if re.search(key_pattern, normalized) or re.search(normalized_pattern, key):
            if level: df = filter_by_level(df, level)
            return [map_func(row, i+1) for i, (_, row) in enumerate(df.head(limit).iterrows())]
    return []

# ──────────────────────────────────────────────
# 4. LLM fallback
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """[ignoring loop detection]
You are a high-end learning resource recommendation engine.
Your ONLY job is to return a JSON object containing two distinct lists — no explanation, no markdown, no code fences.

JSON Structure:
{
  "playlists": [ ... 10 YouTube playlist objects ... ],
  "certificates": [ ... 10 professional certificate course objects (Coursera, Udemy, etc.) ... ]
}

Rules:
1. Return 10 resources for EACH category.
2. Playlists must be direct YouTube playlist links.
3. Certificates must be from reputable platforms (Coursera, edX, Udemy, etc.).

Object format:
{
  "rank": 1,
  "title": "",
  "channel": "",
  "level": "Beginner/Intermediate/Advanced",
  "duration_hours": "",
  "url": "",
  "description": ""
}"""

def llm_fallback(skill: str, level: str, language: str = "English", category: str = "both") -> dict:
    client = Groq()
    
    prompt_instruction = f"Return BOTH top 10 YouTube playlists and top 10 professional certificates for learning {skill} at a {level} level. The results MUST be in {language} language (titles and descriptions should be in {language})."
    if category == "certificates":
        prompt_instruction = f"Return ONLY top 10 professional certificates for learning {skill} ({level}). The results MUST be in {language}. Leave the 'playlists' key as an empty array []."
    elif category == "playlists":
        prompt_instruction = f"Return ONLY top 10 YouTube playlists for learning {skill} ({level}). The results MUST be in {language}. Leave the 'certificates' key as an empty array []."

    user_msg = (
        f"Instruction: {prompt_instruction}\n"
        f"Respond ONLY with a valid JSON object."
    )
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_msg}],
            temperature=0.2,
            max_tokens=2048,
        )
        raw = completion.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw); raw = re.sub(r"\n?```$", "", raw)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict): data = {"playlists": [], "certificates": []}
            return data
        except:
            return {"playlists": [], "certificates": []}
    except Exception as e:
        print(f"[ERROR] llm_fallback failed: {e}")
        return {"playlists": [], "certificates": []}

# ──────────────────────────────────────────────
# 4.5 AI Decision Engine Core
# ──────────────────────────────────────────────
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

def validate_url(url, source="csv"):
    """Validates a URL. For CSV sources, performs HTTP check.
    For YouTube API sources, trusts the API-issued ID (YouTube blocks HEAD requests)."""
    if not url or not url.startswith("http"):
        return False
    
    # YouTube API results: IDs are guaranteed valid by the API itself.
    # YouTube blocks automated HEAD/GET requests so we validate by format only.
    if source == "youtube_api":
        import re
        return bool(re.search(r'(list=[A-Za-z0-9_\-]{10,}|v=[A-Za-z0-9_\-]{10,})', url))
    
    # CSV sources: perform a real HTTP check to catch deleted/broken links
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.head(url, timeout=4, allow_redirects=True, headers=headers)
        if res.status_code in [404, 400, 410]:
            print(f"[VALIDATE] Broken CSV link ({res.status_code}): {url}")
            return False
        return True
    except Exception as e:
        print(f"[VALIDATE] CSV link check failed: {e} — {url}")
        # On timeout/connection error, allow it through rather than false-reject
        return True

def fetch_youtube_playlists(skill, level="Beginner", language="English", max_results=10):
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "your_youtube_api_key_here":
        print("[WARN] Invalid YouTube API Key")
        return []
    
    # Construct a descriptive search query incorporating level and language
    query_parts = [skill]
    if level and level.lower() != "all":
        query_parts.append(level)
    query_parts.append("full course tutorial playlist")
    if language and language.lower() != "english":
        query_parts.append(f"in {language}")
        
    query_str = " ".join(query_parts)
    print(f"[YT] Fetching playlists with query: '{query_str}'")
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query_str,
        "type": "playlist",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        results = []
        for idx, item in enumerate(data.get("items", [])):
            playlist_id = item["id"].get("playlistId")
            if not playlist_id: continue
            snippet = item.get("snippet", {})
            results.append({
                "id": f"yt_{idx}",
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "url": f"https://www.youtube.com/playlist?list={playlist_id}"
            })
        return results
    except Exception as e:
        print(f"[ERROR] YouTube API fetch failed: {e}")
        return []

def analyze_and_rank_resources(youtube_data, skill, level):
    client = Groq()
    system_prompt = """[ignoring loop detection]
You are an elite Tech Career Mentor and AI Recommendation Engine.
I am providing you with a list of YouTube playlists fetched from the API for a specific skill. Each item has an 'id' (e.g., yt_0, yt_1).
Your job is to analyze their titles, channels, and descriptions, and RANK them intelligently into 5 distinct categories.

CRITICAL RULE: DO NOT INVENT URLs or TITLES. You MUST ONLY output the 'selected_id' from the provided list.

RETURN EXACTLY THIS JSON STRUCTURE:
{
  "recommendations": {
    "primary": { "selected_id": "yt_X", "confidence_score": 0, "trust_score": 0, "why_selected": "", "estimated_time": "", "expected_outcome": "" },
    "fast_track": { "selected_id": "yt_X", "confidence_score": 0, "trust_score": 0, "why_selected": "", "estimated_time": "", "expected_outcome": "" },
    "interview": { "selected_id": "yt_X", "confidence_score": 0, "trust_score": 0, "why_selected": "", "estimated_time": "", "expected_outcome": "" },
    "project": { "selected_id": "yt_X", "confidence_score": 0, "trust_score": 0, "why_selected": "", "estimated_time": "", "expected_outcome": "" },
    "advanced": { "selected_id": "yt_X", "confidence_score": 0, "trust_score": 0, "why_selected": "", "estimated_time": "", "expected_outcome": "" }
  }
}
Do NOT return anything else. Ensure the JSON is valid."""

    user_msg = f"Skill: {skill} ({level})\nYouTube Data: {json.dumps(youtube_data)}"
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        print(f"[ERROR] Groq ranking failed: {e}")
        return None

def generate_learning_path(skill, level):
    client = Groq()
    system_prompt = """[ignoring loop detection]
You are an elite Tech Career Mentor.
Generate a structured, step-by-step learning roadmap for the given skill.
All texts (titles, descriptions, topics, etc.) MUST be returned in English.
RETURN EXACTLY THIS JSON STRUCTURE:
{
  "roadmap": {
    "beginner": ["Topic 1", "Topic 2", "Topic 3"],
    "intermediate": ["Topic 1", "Topic 2", "Topic 3"],
    "advanced": ["Topic 1", "Topic 2"],
    "projects": [{"name": "", "description": ""}, {"name": "", "description": ""}],
    "certifications": ["Cert 1", "Cert 2"],
    "interview_prep": ["Prep step 1", "Prep step 2"]
  }
}
Do NOT return anything else. Ensure the JSON is valid."""

    user_msg = f"Skill: {skill} ({level})"
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        print(f"[ERROR] Groq roadmap failed: {e}")
        return None

# ──────────────────────────────────────────────
# 5. Main endpoint — 7-Step AI Pipeline
# ──────────────────────────────────────────────

@app.route("/get-resource", methods=["POST"])
def get_resource():
    body = request.get_json(silent=True) or {}
    skill    = (body.get("skill") or "").strip()
    level    = (body.get("level") or "Beginner").strip()
    language = (body.get("language") or "English").strip()
    sid      = body.get("session_id") or session.get("session_id") or "anonymous"

    if not skill:
        return jsonify({"error": "skill is required"}), 400
    if is_inappropriate(skill):
        return jsonify({"error": "please kindly search appropriate skills"}), 400

    # ── STEP 1: DB Cache (fastest path — zero API cost) ───────────
    cached = db_get_cached_skill(skill, level, language)
    if cached:
        cached["tier_label"] = "⚡ Instant Result: Retrieved from AI Memory"
        return jsonify(cached)

    # ── STEP 2: CSV Check (curated trusted data — English only) ──────────────────
    local_playlists = []
    if language.lower() == "english":
        local_playlists = find_in_db(PLAYLIST_DB, skill, row_to_playlist, level=level)

    if local_playlists:
        def validate_csv_playlists():
            valid = []
            for pl in local_playlists:
                if validate_url(pl.get("url"), source="csv"):
                    pl["verification_status"] = "✅ Verified via CSV"
                    valid.append(pl)
            return valid

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_playlists = executor.submit(validate_csv_playlists)
            future_roadmap   = executor.submit(generate_learning_path, skill, level)
            valid_local_playlists = future_playlists.result()

        if valid_local_playlists:
            certs = find_in_db(CERT_DB, skill, row_to_cert)
            for cert in certs: cert["verification_status"] = "✅ Verified via CSV"

            response_data = {
                "tier": 1, "skill": skill,
                "tier_label": "🚀 Curated Result: Trusted CSV Dataset",
                "recommendations": None,
                "fallback_playlists": valid_local_playlists,
                "fallback_certs": certs, "roadmap": None
            }
            try:
                roadmap_data = future_roadmap.result(timeout=12)
                if roadmap_data:
                    response_data["roadmap"] = roadmap_data.get("roadmap")
            except Exception as e:
                print(f"[TIER1] Roadmap timed out: {e}")

            # ── STEP 5: Save to DB + init trust scores ─────────────
            def _persist():
                db_save_skill(skill, level, language, 1, "csv", response_data)
                db_log_recommendation(skill, 1, "csv", response_data, sid)
                for pl in valid_local_playlists:
                    db_upsert_trust_score(pl.get("url",""), pl.get("title",""), pl.get("channel",""), skill)
            ThreadPoolExecutor(max_workers=1).submit(_persist)

            return jsonify(response_data)

    # ── STEP 3: YouTube API Fallback ──────────────────────────────
    youtube_data = fetch_youtube_playlists(skill, level=level, language=language)
    if not youtube_data:
        return jsonify({"error": "No verified high-quality learning resource found for this skill yet."}), 404

    # ── STEP 4: Groq AI Ranking + Roadmap (parallel) ─────────────
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_rank   = executor.submit(analyze_and_rank_resources, youtube_data, skill, level)
        future_road   = executor.submit(generate_learning_path, skill, level)
        ranking_data  = future_rank.result()
        roadmap_data  = future_road.result()

    final_recommendations = {}
    if ranking_data and "recommendations" in ranking_data:
        for cat, rank_info in ranking_data["recommendations"].items():
            selected_id  = rank_info.get("selected_id")
            verified_item = next((i for i in youtube_data if i["id"] == selected_id), None)
            if not verified_item:
                print(f"[TIER3] Unknown id '{selected_id}', using fallback.")
                verified_item = youtube_data[0] if youtube_data else None
            if not verified_item: continue
            url = verified_item.get("url")
            if validate_url(url, source="youtube_api"):
                rank_info["title"]               = verified_item.get("title")
                rank_info["channel"]             = verified_item.get("channel")
                rank_info["url"]                 = url
                rank_info["verification_status"] = "✅ Verified via YouTube API"
                rank_info.pop("selected_id", None)
                final_recommendations[cat]       = rank_info

    response_data = {
        "tier": 3, "skill": skill,
        "tier_label": "🧠 AI-Ranked Result: Groq Intelligence Engine",
        "recommendations": final_recommendations if final_recommendations else None,
        "fallback_playlists": [],
        "fallback_certs": [], "roadmap": None
    }
    if not final_recommendations:
        for pl in youtube_data:
            pl["verification_status"] = "✅ Verified via YouTube API"
        response_data["fallback_playlists"] = youtube_data
    if roadmap_data:
        response_data["roadmap"] = roadmap_data.get("roadmap")

    # ── STEP 5: Save to DB + init trust scores ────────────────────
    def _persist_yt():
        source = "ai_ranked" if final_recommendations else "youtube_api"
        db_save_skill(skill, level, language, 3, source, response_data)
        db_log_recommendation(skill, 3, source, response_data, sid)
        all_resources = list(final_recommendations.values()) + response_data["fallback_playlists"]
        for r in all_resources:
            db_upsert_trust_score(r.get("url",""), r.get("title",""), r.get("channel",""), skill)
    ThreadPoolExecutor(max_workers=1).submit(_persist_yt)

    return jsonify(response_data)


# ── STEP 6: Click / Save / Ignore Tracking ────────────────────────
@app.route("/track-click", methods=["POST"])
def track_click():
    body         = request.get_json(silent=True) or {}
    resource_url = (body.get("resource_url") or "").strip()
    skill_name   = (body.get("skill_name") or "").strip()
    resource_title = body.get("resource_title", "")
    action       = body.get("action", "click")   # click | save | ignore | complete | roadmap_view
    sid          = body.get("session_id") or "anonymous"

    if not resource_url or not skill_name:
        return jsonify({"error": "resource_url and skill_name required"}), 400
    if action not in ("click", "save", "ignore", "complete", "roadmap_view"):
        return jsonify({"error": "invalid action"}), 400

    try:
        sb = get_sb()
        if sb:
            # Log raw feedback
            sb.table("user_feedback").insert({
                "session_id": sid, "skill_name": skill_name,
                "resource_url": resource_url, "resource_title": resource_title,
                "action": action
            }).execute()
            # Step 7: Auto-adjust trust score
            db_adjust_trust_score(resource_url, action)
        return jsonify({"status": "ok", "action": action})
    except Exception as e:
        print(f"[TRACK] Failed: {e}")
        return jsonify({"status": "error"}), 500


# ── STEP 9: Brutal Mentor Mode ────────────────────────────────────
@app.route("/mentor-mode", methods=["POST"])
def mentor_mode():
    body           = request.get_json(silent=True) or {}
    goal           = (body.get("goal") or "").strip()
    current_skills = (body.get("current_skills") or "").strip()

    if not goal:
        return jsonify({"error": "goal is required"}), 400

    client = Groq()
    system_prompt = """You are a brutally honest, elite Tech Career Mentor.
Your job is to give harsh, direct, actionable career advice.
Be specific. Call out wasted time. Redirect focus.
Never be gentle. Be like a senior engineer who wants the person to actually succeed.

RETURN EXACTLY THIS JSON:
{
  "verdict": "one harsh sentence about their current path",
  "wasted_time": ["skill1", "skill2"],
  "must_learn_now": [{"skill": "", "reason": ""}],
  "priority_order": ["step1", "step2", "step3", "step4", "step5"],
  "brutal_truth": "2-3 sentence reality check paragraph",
  "action_this_week": "exact 1 thing they must do this week"
}
Return only valid JSON."""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"My goal: {goal}\nMy current skills: {current_skills}"}
            ],
            temperature=0.4,
            response_format={"type": "json_object"}
        )
        result = json.loads(completion.choices[0].message.content.strip())
        return jsonify(result)
    except Exception as e:
        print(f"[MENTOR] Groq failed: {e}")
        return jsonify({"error": "Mentor mode unavailable"}), 500



# ──────────────────────────────────────────────
# 5b. Get Real Playlist Videos from YouTube API
# ──────────────────────────────────────────────

@app.route("/get-playlist-videos", methods=["GET"])
def get_playlist_videos():
    """
    Fetch real video titles from a YouTube playlist using the YouTube Data API.
    Query param: playlist_url=https://www.youtube.com/playlist?list=XXXXX
    Returns: { videos: [{id, title, videoId, position}], total: N }
    """
    playlist_url = request.args.get("playlist_url", "")
    if not playlist_url:
        return jsonify({"error": "playlist_url param required"}), 400

    # Extract playlist ID from URL
    import re
    match = re.search(r'list=([A-Za-z0-9_\-]+)', playlist_url)
    if not match:
        return jsonify({"error": "Invalid playlist URL"}), 400

    playlist_id = match.group(1)

    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "your_youtube_api_key_here":
        return jsonify({"error": "YouTube API key not configured"}), 500

    all_videos = []
    next_page_token = None

    try:
        while True:
            params = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": 50,
                "key": YOUTUBE_API_KEY
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/playlistItems",
                params=params,
                timeout=10
            )
            data = resp.json()

            if "error" in data:
                print(f"[YT-VIDEOS] API error: {data['error']}")
                return jsonify({"error": data["error"].get("message", "YouTube API error")}), 500

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                resource = snippet.get("resourceId", {})
                video_id = resource.get("videoId", "")
                title = snippet.get("title", "")
                position = snippet.get("position", len(all_videos))

                # Skip deleted/private videos
                if title in ("Deleted video", "Private video"):
                    continue

                all_videos.append({
                    "id": position + 1,
                    "title": title,
                    "videoId": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "completed": False
                })

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        print(f"[YT-VIDEOS] Fetched {len(all_videos)} videos for playlist {playlist_id}")
        return jsonify({"videos": all_videos, "total": len(all_videos)})

    except Exception as e:
        print(f"[YT-VIDEOS] Error: {e}")
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# 6. Interview Prep (LeetCode)
# ──────────────────────────────────────────────

@app.route("/get-companies", methods=["GET"])
def get_companies():
    """Returns a sorted list of all available companies."""
    try:
        if not os.path.exists(LEETCODE_DIR):
            return jsonify([])
        companies = [d for d in os.listdir(LEETCODE_DIR) if os.path.isdir(os.path.join(LEETCODE_DIR, d))]
        return jsonify(sorted(companies))
    except Exception as e:
        print(f"[ERROR] get-companies: {e}")
        return jsonify([]), 500

@app.route("/get-questions", methods=["GET"])
def get_questions():
    """Returns questions for a specific company."""
    company = request.args.get("company", "").strip()
    if not company:
        return jsonify({"error": "company name is required"}), 400
    
    csv_path = os.path.join(LEETCODE_DIR, company, "all.csv")
    if not os.path.exists(csv_path):
        return jsonify({"error": f"Data for {company} not found"}), 404
    
    try:
        df = pd.read_csv(csv_path)
        questions = []
        for i, row in df.iterrows():
            link = str(row.get("URL", "")).strip()
            if not link: continue
            
            # Enrich with cross-company data from the global index
            global_data = LEETCODE_INDEX.get(link, {})
            other_companies = [c for c in global_data.get("companies", []) if str(c).lower() != str(company).lower()]
            
            questions.append({
                "id":           str(row.get("ID", "")).strip(),
                "title":        str(row.get("Title", "")).strip(),
                "url":          link,
                "difficulty":   str(row.get("Difficulty", "")).strip(),
                "acceptance":   str(row.get("Acceptance %", "")).strip(),
                "frequency":    str(row.get("Frequency %", "")).strip(),
                "other_companies": other_companies
            })
            
        return jsonify({"company": company, "questions": questions})
    except Exception as e:
        print(f"[ERROR] get-questions {company}: {e}")
        return jsonify({"error": str(e)}), 500

# ──────────────────────────────────────────────
# 7. Auth Routes
# ──────────────────────────────────────────────

@app.route("/login-page")
def login_page():
    if session.get("logged_in"):
        return redirect("/")
    return app.send_static_file("login.html")

@app.route("/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    import re
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "Invalid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    session["logged_in"] = True
    session["user_email"] = email

    # Fetch or create profile in Supabase
    sb = get_sb()
    if sb:
        try:
            res = sb.table("profiles").select("id, full_name").eq("email", email).execute()
            if res.data:
                session["user_id"] = res.data[0]["id"]
                session["user_name"] = res.data[0]["full_name"]
            else:
                user_id = str(uuid.uuid4())
                name = email.split("@")[0].capitalize()
                sb.table("profiles").insert({
                    "id": user_id,
                    "full_name": name,
                    "email": email
                }).execute()
                session["user_id"] = user_id
                session["user_name"] = name
        except Exception as e:
            print(f"[AUTH] Supabase profile sync failed: {e}")
            # Fallback to email prefix
            session["user_name"] = email.split("@")[0].capitalize()
    else:
        session["user_name"] = email.split("@")[0].capitalize()

    return jsonify({"success": True})

@app.route("/signup", methods=["POST"])
def signup():
    data     = request.get_json(silent=True) or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not email or not password:
        return jsonify({"error": "All fields are required."}), 400

    import re
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "Invalid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    session["logged_in"] = True
    session["user_email"] = email
    session["user_name"]  = name

    # Create profile in Supabase
    sb = get_sb()
    if sb:
        try:
            user_id = str(uuid.uuid4())
            sb.table("profiles").insert({
                "id": user_id,
                "full_name": name,
                "email": email
            }).execute()
            session["user_id"] = user_id
        except Exception as e:
            print(f"[AUTH] Supabase profile signup failed: {e}")

    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login-page")

@app.route("/get-user-session", methods=["GET"])
def get_user_session():
    if not session.get("logged_in"):
        return jsonify({"logged_in": False}), 401
    return jsonify({
        "logged_in": True,
        "email": session.get("user_email"),
        "name": session.get("user_name") or session.get("user_email").split("@")[0]
    })

@app.route("/get-latest-resume", methods=["GET"])
def get_latest_resume():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify(None)
    sb = get_sb()
    if not sb:
        return jsonify(None)
    try:
        res = sb.table("resume_analysis")\
                .select("*")\
                .eq("user_id", session["user_id"])\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
        if res.data:
            return jsonify({
                "score": res.data[0].get("ats_score", 85),
                "verdict": res.data[0].get("ai_feedback", {}).get("verdict", "Excellent") if isinstance(res.data[0].get("ai_feedback"), dict) else "Excellent",
                "impact": "Strong",
                "match": res.data[0].get("ai_feedback", {}).get("ats_pass_probability", "High") if isinstance(res.data[0].get("ai_feedback"), dict) else "High",
                "ats": res.data[0].get("ats_score", 85)
            })
        return jsonify(None)
    except Exception as e:
        print(f"[RESUME] Get failed: {e}")
        return jsonify(None)

@app.route("/sync-dsa-progress", methods=["POST"])
def sync_dsa_progress():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    solved_list = body.get("solved_list", [])
    
    sb = get_sb()
    if not sb:
        return jsonify({"error": "DB unavailable"}), 500
        
    try:
        total = len(solved_list)
        easy = len([q for q in solved_list if q.get("difficulty") == "Easy"])
        medium = len([q for q in solved_list if q.get("difficulty") == "Medium"])
        hard = len([q for q in solved_list if q.get("difficulty") == "Hard"])
        
        # Sync to learning_progress
        sb.table("learning_progress").upsert({
            "session_id": session["user_id"],
            "skill_name": "dsa",
            "completed_steps": solved_list,
            "completion_pct": min(100.0, float(total) / 500 * 100)
        }, on_conflict="session_id, skill_name").execute()
        
        # Sync to dsa_progress
        dsa_res = sb.table("dsa_progress").select("id").eq("user_id", session["user_id"]).limit(1).execute()
        dsa_row = {
            "user_id": session["user_id"],
            "total_solved": total,
            "easy_solved": easy,
            "medium_solved": medium,
            "hard_solved": hard
        }
        if dsa_res.data:
            sb.table("dsa_progress").update(dsa_row).eq("id", dsa_res.data[0]["id"]).execute()
        else:
            sb.table("dsa_progress").insert(dsa_row).execute()
        
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[DSA] Sync failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get-dsa-progress", methods=["GET"])
def get_dsa_progress():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify([])
    sb = get_sb()
    if not sb:
        return jsonify([])
    try:
        res = sb.table("learning_progress")\
                .select("completed_steps")\
                .eq("session_id", session["user_id"])\
                .eq("skill_name", "dsa")\
                .limit(1)\
                .execute()
        if res.data:
            return jsonify(res.data[0].get("completed_steps", []))
        return jsonify([])
    except Exception as e:
        print(f"[DSA] Get failed: {e}")
        return jsonify([])

@app.route("/sync-user-projects", methods=["POST"])
def sync_user_projects():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    projects_list = body.get("projects_list", [])
    
    sb = get_sb()
    if not sb:
        return jsonify({"error": "DB unavailable"}), 500
        
    try:
        sb.table("learning_progress").upsert({
            "session_id": session["user_id"],
            "skill_name": "user_projects",
            "completed_steps": projects_list,
            "completion_pct": 100.0
        }, on_conflict="session_id, skill_name").execute()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[PROJECTS] Sync failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get-user-projects", methods=["GET"])
def get_user_projects():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify([])
    sb = get_sb()
    if not sb:
        return jsonify([])
    try:
        res = sb.table("learning_progress")\
                .select("completed_steps")\
                .eq("session_id", session["user_id"])\
                .eq("skill_name", "user_projects")\
                .limit(1)\
                .execute()
        if res.data:
            return jsonify(res.data[0].get("completed_steps", []))
        return jsonify([])
    except Exception as e:
        print(f"[PROJECTS] Get failed: {e}")
        return jsonify([])

@app.route("/sync-saved-playlists", methods=["POST"])
def sync_saved_playlists():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    playlists_list = body.get("playlists_list", [])
    
    sb = get_sb()
    if not sb:
        return jsonify({"error": "DB unavailable"}), 500
        
    try:
        # Calculate real completion percentage based on all saved playlists and videos
        total_videos = 0
        completed_videos = 0
        for p in playlists_list:
            videos = p.get("videos", [])
            total_videos += len(videos)
            completed_videos += len([v for v in videos if v.get("completed")])
        
        pct = 0.0
        if total_videos > 0:
            pct = round((completed_videos / total_videos) * 100.0, 2)

        sb.table("learning_progress").upsert({
            "session_id": session["user_id"],
            "skill_name": "saved_playlists",
            "completed_steps": playlists_list,
            "completion_pct": pct
        }, on_conflict="session_id, skill_name").execute()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[PLAYLISTS] Sync failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get-saved-playlists", methods=["GET"])
def get_saved_playlists():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify([])
    sb = get_sb()
    if not sb:
        return jsonify([])
    try:
        res = sb.table("learning_progress")\
                .select("completed_steps")\
                .eq("session_id", session["user_id"])\
                .eq("skill_name", "saved_playlists")\
                .limit(1)\
                .execute()
        if res.data:
            return jsonify(res.data[0].get("completed_steps", []))
        return jsonify([])
    except Exception as e:
        print(f"[PLAYLISTS] Get failed: {e}")
        return jsonify([])

@app.route("/sync-active-roadmap", methods=["POST"])
def sync_active_roadmap():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    
    sb = get_sb()
    if not sb:
        return jsonify({"error": "DB unavailable"}), 500
        
    try:
        if not body:
            # Untrack roadmap by deleting active_roadmap row
            sb.table("learning_progress").delete().eq("session_id", session["user_id"]).eq("skill_name", "active_roadmap").execute()
            return jsonify({"status": "success"})

        skill = body.get("skill")
        level = body.get("level")
        steps = body.get("steps", [])
        pct = float(body.get("completion_pct", 0.0))
        
        roadmap_data = {
            "skill": skill,
            "level": level,
            "steps": steps
        }
        
        sb.table("learning_progress").upsert({
            "session_id": session["user_id"],
            "skill_name": "active_roadmap",
            "completed_steps": roadmap_data,
            "completion_pct": pct
        }, on_conflict="session_id, skill_name").execute()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[ROADMAP] Sync failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get-active-roadmap", methods=["GET"])
def get_active_roadmap():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify(None)
    sb = get_sb()
    if not sb:
        return jsonify(None)
    try:
        res = sb.table("learning_progress")\
                .select("completed_steps, completion_pct")\
                .eq("session_id", session["user_id"])\
                .eq("skill_name", "active_roadmap")\
                .limit(1)\
                .execute()
        if res.data:
            row = res.data[0]
            data = row.get("completed_steps") or {}
            data["completion_pct"] = float(row.get("completion_pct", 0.0))
            return jsonify(data)
        return jsonify(None)
    except Exception as e:
        print(f"[ROADMAP] Get failed: {e}")
        return jsonify(None)

@app.route("/add-milestone", methods=["POST"])
def add_milestone():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    skill_name = body.get("skill_name")
    outcome_type = body.get("outcome_type", "roadmap_complete")
    outcome_detail = body.get("outcome_detail")
    
    if not skill_name:
        return jsonify({"error": "skill_name is required"}), 400
        
    sb = get_sb()
    if not sb:
        return jsonify({"error": "DB unavailable"}), 500
        
    try:
        # Check if duplicate milestone already exists
        res = sb.table("success_metrics")\
                .select("id")\
                .eq("session_id", session["user_id"])\
                .eq("skill_name", skill_name)\
                .eq("outcome_type", outcome_type)\
                .limit(1)\
                .execute()
                
        if res.data:
            return jsonify({"status": "already_exists"})
            
        # Insert new milestone
        sb.table("success_metrics").insert({
            "session_id": session["user_id"],
            "skill_name": skill_name,
            "outcome_type": outcome_type,
            "outcome_detail": outcome_detail
        }).execute()
        
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[MILESTONES] Add failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get-milestones", methods=["GET"])
def get_milestones():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify([])
    sb = get_sb()
    if not sb:
        return jsonify([])
    try:
        res = sb.table("success_metrics")\
                .select("*")\
                .eq("session_id", session["user_id"])\
                .order("created_at", desc=True)\
                .execute()
        return jsonify(res.data or [])
    except Exception as e:
        print(f"[MILESTONES] Get failed: {e}")
        return jsonify([])

@app.route("/generate-competency-audit", methods=["POST"])
def generate_competency_audit():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    sb = get_sb()
    if not sb:
        return jsonify({"error": "Database connection not active"}), 500
        
    try:
        user_id = session["user_id"]
        
        # 1. Fetch DSA progress
        dsa_data = {"total_solved": 0, "easy_solved": 0, "medium_solved": 0, "hard_solved": 0, "weak_topics": []}
        try:
            dsa_res = sb.table("dsa_progress").select("*").eq("user_id", user_id).limit(1).execute()
            if dsa_res.data:
                dsa_data = dsa_res.data[0]
        except Exception as ex:
            print(f"[AUDIT] DSA lookup fail: {ex}")
            
        # 2. Fetch Latest Resume Analysis
        resume_data = {}
        try:
            resume_res = sb.table("resume_analysis").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
            if resume_res.data:
                resume_data = resume_res.data[0]
        except Exception as ex:
            print(f"[AUDIT] Resume lookup fail: {ex}")
            
        # 3. Fetch Learning Progress (playlists, roadmap, custom projects)
        playlists_pct = 0.0
        playlists_count = 0
        try:
            playlists_res = sb.table("learning_progress").select("*").eq("session_id", user_id).eq("skill_name", "saved_playlists").limit(1).execute()
            if playlists_res.data:
                playlists_count = len(playlists_res.data[0].get("completed_steps", []))
                playlists_pct = float(playlists_res.data[0].get("completion_pct", 0.0))
        except Exception as ex:
            print(f"[AUDIT] Playlists lookup fail: {ex}")
            
        roadmap_name = "None"
        roadmap_pct = 0.0
        try:
            roadmap_res = sb.table("learning_progress").select("*").eq("session_id", user_id).eq("skill_name", "active_roadmap").limit(1).execute()
            if roadmap_res.data:
                roadmap_name = (roadmap_res.data[0].get("completed_steps") or {}).get("skill", "None")
                roadmap_pct = float(roadmap_res.data[0].get("completion_pct", 0.0))
        except Exception as ex:
            print(f"[AUDIT] Roadmap lookup fail: {ex}")
            
        projects_count = 0
        try:
            projects_res = sb.table("learning_progress").select("*").eq("session_id", user_id).eq("skill_name", "user_projects").limit(1).execute()
            if projects_res.data:
                projects_count = len(projects_res.data[0].get("completed_steps", []))
        except Exception as ex:
            print(f"[AUDIT] Projects lookup fail: {ex}")
            
        # 4. Fetch Milestones
        milestones = []
        try:
            milestones_res = sb.table("success_metrics").select("*").eq("session_id", user_id).execute()
            milestones = [m.get("outcome_detail") for m in (milestones_res.data or [])]
        except Exception as ex:
            print(f"[AUDIT] Milestones lookup fail: {ex}")
        
        # Prepare context for Groq
        profile_context = {
            "dsa": {
                "solved": dsa_data.get("total_solved", 0),
                "easy": dsa_data.get("easy_solved", 0),
                "medium": dsa_data.get("medium_solved", 0),
                "hard": dsa_data.get("hard_solved", 0),
                "weak_topics": dsa_data.get("weak_topics") or []
            },
            "resume": {
                "ats_score": resume_data.get("ats_score", 0),
                "role": resume_data.get("ai_feedback", {}).get("role", "Software Engineer") if isinstance(resume_data.get("ai_feedback"), dict) else "Software Engineer"
            },
            "learning": {
                "playlists_saved": playlists_count,
                "playlists_overall_completion_pct": playlists_pct,
                "active_roadmap": roadmap_name,
                "roadmap_completion_pct": roadmap_pct,
                "custom_projects_logged": projects_count
            },
            "milestones": milestones
        }

        # Prompt Groq to generate a professional career competency audit
        prompt = f"""
You are a top-tier SaaS Career Intelligence & Technical Assessment engine.
Analyze the following developer prep profile data and produce a structured, high-value competency audit.

DEVELOPER PREP PROFILE DATA:
{json.dumps(profile_context, indent=2)}

You are auditing this candidate against elite global tech standards (e.g., FAANG, tier-1 tech startups, high-end unicorns).
Evaluate them critically based on their DSA portfolio, learning playlist history, custom projects count, and resume ATS score.

OUTPUT STRICTLY A VALID JSON OBJECT WITH THIS STRUCTURE:
{{
  "market_ready_level": "Junior (L3) / Mid-level (L4) / Senior (L5) / Intern",
  "readiness_verdict": "A blunt, professional 2-sentence summary of where they currently stand and their likelihood of passing top-tier interviews.",
  "scores": {{
    "dsa_standing": number (1-100, calculate logically: Easy=1pt, Med=4pt, Hard=10pt, target 500 pts total),
    "learning_depth": number (1-100, based on playlist completion and roadmap progress),
    "project_portfolio": number (1-100, based on custom projects logged and roadmap milestones),
    "ats_readiness": number (1-100, based directly on resume ATS score, default to 30 if no resume)
  }},
  "technical_gaps": [
    "List 3-4 specific technical or practical focus areas they need to fix based on their weak topics and missing items."
  ],
  "action_items": [
    "List 3-4 concrete, highly actionable next steps (e.g., 'Solve 15 more medium recursion problems', 'Upload a tailored resume to improve ATS score')."
  ],
  "estimated_weeks_to_target": number,
  "competency_breakdown": [
    {{ "skill": "Data Structures & Alg.", "candidate_score": number, "benchmark_score": 85 }},
    {{ "skill": "System Design", "candidate_score": number, "benchmark_score": 75 }},
    {{ "skill": "Project Engineering", "candidate_score": number, "benchmark_score": 80 }},
    {{ "skill": "Market Alignment (Resume)", "candidate_score": number, "benchmark_score": 85 }}
  ]
}}

STRICT RULES:
- Do NOT output any markdown, HTML, code fences, or explanations. Respond with the raw JSON object ONLY.
- Candidate scores must be integers between 5 and 100.
- If they have 0 solved questions, 0 custom projects, and 0 resume score, their competency scores must be very low. Be realistic, not overly encouraging.
- The estimated weeks to target should be a realistic integer based on how far behind they are (e.g. if DSA score is low, they need 12-24 weeks).
"""
        
        client = Groq()
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a professional SaaS tech career audit engine. Return JSON only. Be highly precise and critical."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        audit_res = json.loads(completion.choices[0].message.content.strip())
        
        # Save competency audit to Supabase
        try:
            sb.table("learning_progress").upsert({
                "session_id": user_id,
                "skill_name": "competency_audit",
                "completed_steps": audit_res,
                "completion_pct": float(audit_res.get("scores", {}).get("dsa_standing", 0))
            }, on_conflict="session_id, skill_name").execute()
        except Exception as sb_err:
            print(f"[AUDIT] Save to Supabase failed: {sb_err}")

        return jsonify(audit_res)
        
    except Exception as e:
        print(f"[AUDIT] Generation failed: {e}")
        return jsonify({"error": "Failed to generate competency audit. Ensure you are logged in and database connection is active."}), 500

@app.route("/get-competency-audit", methods=["GET"])
def get_competency_audit():
    if not session.get("logged_in") or not session.get("user_id"):
        return jsonify(None)
    sb = get_sb()
    if not sb:
        return jsonify(None)
    try:
        res = sb.table("learning_progress")\
                .select("completed_steps")\
                .eq("session_id", session["user_id"])\
                .eq("skill_name", "competency_audit")\
                .limit(1)\
                .execute()
        if res.data:
            return jsonify(res.data[0].get("completed_steps"))
        return jsonify(None)
    except Exception as e:
        print(f"[AUDIT] Get failed: {e}")
        return jsonify(None)

@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect("/login-page")
    return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
