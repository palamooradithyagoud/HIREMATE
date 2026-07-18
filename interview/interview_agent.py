import os
import json
import re
import logging
import google.generativeai as genai
from interview.conversation_memory import ConversationMemory
from interview.resume_agent import ResumeAgent
from interview.project_agent import ProjectAgent
from interview.behavioral_agent import BehavioralAgent
from interview.technical_agent import TechnicalAgent
from interview.feedback_agent import FeedbackAgent
from interview.report_generator import ReportGenerator

logger = logging.getLogger("VoiceMockInterview.InterviewAgent")

def clean_tts_text(text: str) -> str:
    # Remove markdown asterisks, hashtags, underscores, backticks
    text = re.sub(r'[*#_`]', '', text)
    # Remove leading labels like "Alex:", "Interviewer:", "Alex - Recruiter:" (case-insensitive)
    text = re.sub(r'^(Alex|Interviewer|Recruiter|Model)\s*(?:-\s*\w+)?\s*:\s*', '', text, flags=re.IGNORECASE)
    # Strip whitespace
    return text.strip()

class InterviewAgent:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            
        self.memory = ConversationMemory()
        self.resume_agent = ResumeAgent()
        self.project_agent = ProjectAgent()
        self.behavioral_agent = BehavioralAgent()
        self.technical_agent = TechnicalAgent()

    def initialize_interview(self, company: str, role: str, exp_level: str, profile: dict, interview_type: str = "Coding & DSA"):
        """
        Prepares the conversational system context prompt and starts the memory.
        """
        self.memory.clear()
        self.interview_type = interview_type
        
        if interview_type == "Behavioral":
            system_prompt = f"""
            You are Alex, an expert recruiter and behavioral interviewer conducting a mock interview for:
            Company: {company}
            Role: {role}
            Experience Level: {exp_level}
            Round Type: Behavioral Round & STAR Method
            
            Candidate Profile:
            {profile}
            
            Interview Structure Guidelines:
            1. Keep the conversation extremely natural, warm, friendly, and highly conversational.
            2. Focus exclusively on behavioral and situational competencies tailored to {company}'s cultural values:
               - Amazon: Leadership Principles (Ownership, Customer Obsession, Deliver Results, etc.)
               - Google: Googliness, problem solving, and ambiguity.
               - Microsoft: Collaboration, growth mindset.
               - Meta: Speed, scale, and direct impact.
            3. Never ask multiple questions at once. Ask exactly one behavioral question at a time.
            4. Probe the candidate's answers deeply using the STAR method (Situation, Task, Action, Result). If they don't specify the results/metrics or their specific actions, ask follow-up questions to dig deeper.
            5. Speak as an interviewer directly. Do not output instructions, thoughts, markdown formatting (like asterisks or hashtags), or formatting blocks.
            """
            behavioral_q = self.behavioral_agent.formulate_behavioral_question(company, "")
            greeting = f"Hello {profile.get('full_name', 'there')}! My name is Alex, and I'll be your mock interviewer today. Since this is a dedicated behavioral round, we will focus on situational questions and cultural alignment. Let's start: {behavioral_q}"

        elif interview_type == "System Design":
            system_prompt = f"""
            You are Alex, an expert technical lead conducting a mock system design interview for:
            Company: {company}
            Role: {role}
            Experience Level: {exp_level}
            Round Type: System Design & Scalability
            
            Candidate Profile:
            {profile}
            
            Interview Structure Guidelines:
            1. Keep the conversation extremely natural, professional, and technical.
            2. Focus exclusively on software architecture, system design, scalability, and design trade-offs (caching, database choices, load balancers, CDN, replication, etc.).
            3. Never ask multiple questions at once. Present one design scenario or follow-up question at a time.
            4. Probe the candidate on bottleneck analysis, API contracts, database schemas, and scalability constraints.
            5. Speak as an interviewer directly. Do not output instructions, thoughts, markdown formatting, or formatting blocks.
            """
            tech_q = self.technical_agent.formulate_technical_question(role, "")
            greeting = f"Hello {profile.get('full_name', 'there')}! My name is Alex, and I'll be your mock interviewer today. For this system design and scalability round, let's dive into system architecture and scaling. To begin: {tech_q}"

        else:  # Coding & DSA
            system_prompt = f"""
            You are Alex, an expert software engineer conducting a coding and algorithms mock interview for:
            Company: {company}
            Role: {role}
            Experience Level: {exp_level}
            Round Type: Coding & Data Structures (DSA)
            
            Candidate Profile:
            {profile}
            
            Interview Structure Guidelines:
            1. Keep the conversation natural, encouraging, and focused on algorithmic problem-solving.
            2. Focus exclusively on algorithm design, time/space complexity analysis (Big O), edge cases, and code optimization.
            3. Ask the candidate to describe their approach to a challenging coding problem suited for {company}'s engineering bar.
            4. Never ask multiple questions at once. State the problem scenario clearly, and ask for their high-level plan or time complexity before they write code.
            5. Speak as an interviewer directly. Do not output instructions, thoughts, markdown formatting, or formatting blocks.
            """
            greeting = f"Hello {profile.get('full_name', 'there')}! My name is Alex, and I'll be your mock interviewer today. For this Coding and Data Structures round, I'd like to test your algorithm design and problem-solving skills. To start, how would you design an efficient solution to find the longest consecutive sequence of integers in an unsorted array?"

        self.memory.set_system_context(system_prompt)
        self.memory.add_message("assistant", greeting)
        return greeting

    def chat_turn(self, user_response: str, profile: dict, company: str, role: str) -> str:
        """
        Processes user response, updates history, and returns the next conversational question.
        Uses Gemini multimodal model to generate responses.
        """
        if not self.api_key:
            return "Could you explain that decision in more detail? I want to ensure I understand."

        self.memory.add_message("user", user_response)
        
        # Load active history context
        history = self.memory.get_history()
        
        # Extract system prompt and user/model history
        system_instruction = None
        gemini_messages = []
        for msg in history:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role_tag = "user" if msg["role"] == "user" else "model"
                gemini_messages.append({"role": role_tag, "parts": [msg["content"]]})
                
        try:
            # Initialize model with system instruction
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
            
            # Generate next question
            response = model.generate_content(
                contents=gemini_messages,
                generation_config={"temperature": 0.5}
            )
            ai_reply = response.text.strip()
            
            # Sanitize reply for speech & clean presentation
            ai_reply = clean_tts_text(ai_reply)
            
            # Save AI turn in history
            self.memory.add_message("assistant", ai_reply)
            return ai_reply
        except Exception as e:
            logger.error(f"Gemini mock interview generation turn failed: {e}")
            return "That makes sense. Can you expand on the main challenges or decisions you made there?"

    def evaluate_interview(self) -> dict:
        """
        Evaluates the current interview history and returns overall report, scores, and recommendations.
        """
        history = self.memory.get_history()
        feedback = FeedbackAgent.analyze_responses(history)
        recommendations = ReportGenerator.generate_recommendations(feedback["weak_areas"])
        
        return {
            "score": feedback["readiness_score"],
            "feedback": {
                "communication_score": feedback["communication"],
                "technical_score": feedback["technical"],
                "confidence_score": feedback["confidence"],
                "behavior_score": feedback["behavior"],
                "voice_clarity": feedback["voice_clarity"],
                "grammar": feedback["grammar"],
                "weak_areas": feedback["weak_areas"],
                "strong_areas": feedback["strong_areas"]
            },
            "transcript": history,
            "recommendations": recommendations
        }
