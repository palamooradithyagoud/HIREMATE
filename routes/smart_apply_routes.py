import logging
from flask import Blueprint, request, jsonify, g
from services.smart_apply_service import SmartApplyService, AUTOMATION_TASKS

smart_apply_routes_bp = Blueprint("smart_apply_routes", __name__)
logger = logging.getLogger("VoiceMockInterview.SmartApplyRoutes")

# ──────────────────────────────────────────────
# Resume Management CRUD Endpoints
# ──────────────────────────────────────────────

@smart_apply_routes_bp.route("/api/apply/resumes", methods=["GET"])
def get_user_resumes():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        try:
            res = sb.table("user_resumes").select("*").eq("user_id", g.user_id).execute()
            return jsonify(res.data)
        except Exception as e:
            logger.error(f"Error fetching resumes: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

@smart_apply_routes_bp.route("/api/apply/resumes", methods=["POST"])
def save_user_resume():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        body = request.get_json(silent=True) or {}
        name = body.get("name", "").strip()
        url = body.get("resume_url", "").strip()
        ats_score = body.get("ats_score", 0)

        if not name or not url:
            return jsonify({"error": "Name and resume_url are required"}), 400

        try:
            data = {
                "user_id": g.user_id,
                "name": name,
                "resume_url": url,
                "ats_score": ats_score
            }
            res = sb.table("user_resumes").insert(data).execute()
            return jsonify(res.data[0])
        except Exception as e:
            logger.error(f"Error saving resume: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

@smart_apply_routes_bp.route("/api/apply/resumes/<resume_id>", methods=["DELETE"])
def delete_user_resume(resume_id):
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        try:
            sb.table("user_resumes").delete().eq("id", resume_id).eq("user_id", g.user_id).execute()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"Error deleting resume: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

# ──────────────────────────────────────────────
# Cover Letter Management CRUD Endpoints
# ──────────────────────────────────────────────

@smart_apply_routes_bp.route("/api/apply/cover-letters", methods=["GET"])
def get_user_cover_letters():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        try:
            res = sb.table("user_cover_letters").select("*").eq("user_id", g.user_id).execute()
            return jsonify(res.data)
        except Exception as e:
            logger.error(f"Error fetching cover letters: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

@smart_apply_routes_bp.route("/api/apply/cover-letters", methods=["POST"])
def save_user_cover_letter():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        body = request.get_json(silent=True) or {}
        name = body.get("name", "").strip()
        content = body.get("content", "").strip()

        if not name or not content:
            return jsonify({"error": "Name and content are required"}), 400

        try:
            data = {
                "user_id": g.user_id,
                "name": name,
                "content": content
            }
            res = sb.table("user_cover_letters").insert(data).execute()
            return jsonify(res.data[0])
        except Exception as e:
            logger.error(f"Error saving cover letter: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

@smart_apply_routes_bp.route("/api/apply/cover-letters/<letter_id>", methods=["DELETE"])
def delete_user_cover_letter(letter_id):
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        try:
            sb.table("user_cover_letters").delete().eq("id", letter_id).eq("user_id", g.user_id).execute()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"Error deleting cover letter: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

# ──────────────────────────────────────────────
# Smart Apply AI Analysis and Automation Control
# ──────────────────────────────────────────────

@smart_apply_routes_bp.route("/api/apply/analyze", methods=["POST"])
def analyze_job():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
            
        body = request.get_json(silent=True) or {}
        job_desc = body.get("job_description", "").strip()
        job_url = body.get("job_url", "").strip()
        
        if not job_desc:
            return jsonify({"error": "Job description is required"}), 400
            
        try:
            # Get candidate profile
            prof_res = sb.table("profiles").select("*").eq("id", g.user_id).limit(1).execute()
            profile = prof_res.data[0] if prof_res.data else {}
            
            # Get resumes
            res_res = sb.table("user_resumes").select("*").eq("user_id", g.user_id).execute()
            resumes = res_res.data
            
            analysis = SmartApplyService.deep_analyze_job(profile, job_desc, resumes)
            return jsonify(analysis)
        except Exception as e:
            logger.error(f"Job analysis failed: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

@smart_apply_routes_bp.route("/api/apply/start-automation", methods=["POST"])
def start_automation():
    from app import token_required
    @token_required
    def handler():
        body = request.get_json(silent=True) or {}
        job_url = body.get("job_url", "").strip()
        resume_url = body.get("resume_url", "").strip()
        resume_name = body.get("resume_name", "").strip()
        cover_letter_text = body.get("cover_letter_text", "").strip()
        company = body.get("company", "").strip()
        role = body.get("role", "").strip()

        if not job_url:
            return jsonify({"error": "job_url is required"}), 400

        data = {
            "job_url": job_url,
            "resume_url": resume_url,
            "resume_name": resume_name,
            "cover_letter_text": cover_letter_text,
            "company": company or "Employer",
            "role": role or "Software Engineer"
        }

        try:
            task_id = SmartApplyService.start_apply_automation(g.user_id, data)
            return jsonify({"task_id": task_id})
        except Exception as e:
            logger.error(f"Failed to start automation: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

@smart_apply_routes_bp.route("/api/apply/status/<task_id>", methods=["GET"])
def get_automation_status(task_id):
    from app import token_required
    @token_required
    def handler():
        status_data = SmartApplyService.get_task_status(task_id)
        if "error" in status_data:
            return jsonify(status_data), 404
        return jsonify(status_data)
    return handler()

@smart_apply_routes_bp.route("/api/apply/resume-automation", methods=["POST"])
def resume_automation():
    from app import token_required
    @token_required
    def handler():
        body = request.get_json(silent=True) or {}
        task_id = body.get("task_id")
        action = body.get("action") # e.g. "continue"

        if not task_id or task_id not in AUTOMATION_TASKS:
            return jsonify({"error": "Task not found"}), 404

        # If paused, update status to resume the wait loop
        current_status = AUTOMATION_TASKS[task_id]["status"]
        if current_status in ["PAUSED_LOGIN", "PAUSED_CAPTCHA"]:
            AUTOMATION_TASKS[task_id]["status"] = "Autofilling form..."
            SmartApplyService.log_message(task_id, "User indicated problem is resolved. Resuming automation.")
            return jsonify({"success": True})
        
        return jsonify({"error": "Task is not in a paused state"}), 400
    return handler()

@smart_apply_routes_bp.route("/api/apply/confirm-submit", methods=["POST"])
def confirm_submit():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
            
        body = request.get_json(silent=True) or {}
        task_id = body.get("task_id")
        action = body.get("action", "submit") # "submit" or "cancel"
        edited_answers = body.get("fields", [])

        if not task_id or task_id not in AUTOMATION_TASKS:
            return jsonify({"error": "Task not found"}), 404

        task = AUTOMATION_TASKS[task_id]
        
        # Store custom answers if they were edited
        if edited_answers:
            task["preview"]["fields"] = edited_answers

        task["confirm_action"] = action
        
        # Trigger the event to let Playwright resume and execute submit/cancel
        loop = task["loop"]
        event = task["event"]
        
        # Thread-safe event trigger
        if loop and loop.is_running():
            loop.call_soon_threadsafe(event.set)
        else:
            event.set()

        # Save to Supabase job tracking upon submit
        if action == "submit":
            try:
                tracker_data = {
                    "user_id": g.user_id,
                    "company": task["data"].get("company"),
                    "role": task["data"].get("role"),
                    "job_url": task["data"].get("job_url"),
                    "resume_version": task["data"].get("resume_name", "Primary Resume"),
                    "cover_letter_version": "Tailored Cover Letter" if task["data"].get("cover_letter_text") else "None",
                    "match_score": 85, # Default or generated
                    "status": "Applied",
                    "notes": "Applied via AI-Assisted Smart Apply."
                }
                sb.table("job_applications").insert(tracker_data).execute()
            except Exception as db_err:
                logger.error(f"Error saving tracking info to DB: {db_err}")

        return jsonify({"success": True})
    return handler()

# ──────────────────────────────────────────────
# Application Tracking Dashboard Endpoints
# ──────────────────────────────────────────────

@smart_apply_routes_bp.route("/api/apply/list", methods=["GET"])
def get_job_applications():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        try:
            res = sb.table("job_applications").select("*").eq("user_id", g.user_id).order("date_applied", desc=True).execute()
            return jsonify(res.data)
        except Exception as e:
            logger.error(f"Error fetching job applications tracker list: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()

@smart_apply_routes_bp.route("/api/apply/update-status", methods=["POST"])
def update_application_status():
    from app import token_required, get_sb
    @token_required
    def handler():
        sb = get_sb()
        if not sb:
            return jsonify({"error": "Database service offline"}), 500
        body = request.get_json(silent=True) or {}
        app_id = body.get("application_id")
        status = body.get("status")
        notes = body.get("notes")

        if not app_id or not status:
            return jsonify({"error": "application_id and status are required"}), 400

        try:
            update_data = {
                "status": status,
            }
            if notes is not None:
                update_data["notes"] = notes
                
            res = sb.table("job_applications").update(update_data).eq("id", app_id).eq("user_id", g.user_id).execute()
            return jsonify(res.data[0])
        except Exception as e:
            logger.error(f"Error updating application status: {e}")
            return jsonify({"error": str(e)}), 500
    return handler()
