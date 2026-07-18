import os
import time
import base64
import requests
import logging
import re

logger = logging.getLogger("VoiceMockInterview.TextToSpeech")

class TextToSpeech:
    @staticmethod
    def synthesize(text: str, user_id: str) -> str:
        """
        Synthesizes text into an audio file using Sarvam AI.
        Falls back to gTTS if SARVAM_API_KEY is not configured.
        """
        # Clean text of markdown formatters or labels for a natural voice output
        clean_text = re.sub(r'[*#_`]', '', text)
        clean_text = re.sub(r'^(Alex|Interviewer|Recruiter|Model)\s*(?:-\s*\w+)?\s*:\s*', '', clean_text, flags=re.IGNORECASE)
        clean_text = clean_text.strip()

        sarvam_key = os.environ.get("SARVAM_API_KEY")
        base_dir = r"c:\PROJECTS\SKILL PATH\AI-CATALYST-main\AI-CATALYST-main"
        audio_dir = os.path.join(base_dir, "static", "audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        filename = f"speak_{user_id}_{int(time.time())}.mp3"
        filepath = os.path.join(audio_dir, filename)

        if sarvam_key:
            try:
                logger.info(f"Synthesizing text via Sarvam AI TTS: '{clean_text[:60]}...'")
                url = "https://api.sarvam.ai/text-to-speech"
                headers = {
                    "api-subscription-key": sarvam_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "text": clean_text,
                    "speaker": "meera",
                    "target_language_code": "en-IN"
                }
                
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    audios = data.get("audios", [])
                    if audios:
                        audio_base64 = audios[0]
                        # Decode and save
                        audio_bytes = base64.b64decode(audio_base64)
                        with open(filepath, "wb") as f:
                            f.write(audio_bytes)
                        logger.info(f"Audio file saved via Sarvam TTS: {filepath}")
                        return f"/static/audio/{filename}"
                logger.warning(f"Sarvam AI TTS returned code {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Error during Sarvam AI Text-to-Speech synthesis: {e}")
 
        # Fallback to gTTS
        try:
            logger.info(f"Using gTTS fallback for text: '{clean_text[:60]}...'")
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang='en', tld='co.uk')
            tts.save(filepath)
            return f"/static/audio/{filename}"
        except Exception as e:
            logger.error(f"Error during gTTS fallback: {e}")
            return ""
