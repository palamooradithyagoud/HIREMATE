import os
import requests
import logging

logger = logging.getLogger("VoiceMockInterview.SpeechToText")

class SpeechToText:
    def __init__(self):
        self.sarvam_key = os.environ.get("SARVAM_API_KEY")

    def transcribe_audio(self, file_path: str) -> str:
        """
        Transcribes local audio recording files using Sarvam AI Speech-to-Text.
        Falls back to Gemini transcription if Sarvam key is missing.
        """
        if self.sarvam_key:
            try:
                logger.info(f"Transcribing audio via Sarvam AI STT: {file_path}")
                url = "https://api.sarvam.ai/speech-to-text"
                headers = {
                    "api-subscription-key": self.sarvam_key
                }
                
                with open(file_path, "rb") as f:
                    files = {
                        "file": (os.path.basename(file_path), f, "audio/wav")
                    }
                    data = {
                        "model": "saaras:v3",
                        "language_code": "en-IN"
                    }
                    
                    response = requests.post(url, headers=headers, files=files, data=data)
                    
                if response.status_code == 200:
                    res_data = response.json()
                    transcript = res_data.get("transcript", "").strip()
                    logger.info(f"Sarvam STT transcription successful: {transcript[:80]}...")
                    return transcript
                    
                logger.warning(f"Sarvam STT failed with status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Error during Sarvam STT: {e}")

        # Fallback to Gemini transcription
        try:
            logger.info("Using Gemini fallback transcription...")
            import google.generativeai as genai
            gemini_key = os.environ.get("GEMINI_API_KEY")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                audio_file = genai.upload_file(path=file_path)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content([
                    audio_file,
                    "Transcribe the audio speech exactly as spoken. Do not include notes or commentary."
                ])
                transcript = response.text.strip()
                genai.delete_file(audio_file.name)
                return transcript
        except Exception as e:
            logger.error(f"Gemini fallback transcription failed: {e}")
            
        return ""
