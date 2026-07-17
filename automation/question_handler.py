import logging
from automation.field_detector import FieldDetector
from automation.form_filler import FormFiller

logger = logging.getLogger("JobApplicationAgent.QuestionHandler")

class QuestionHandler:
    @staticmethod
    async def fill_essays(page, essay_answers: dict) -> list[str]:
        """
        Locates textarea or essay fields on the page, generates answers, and inputs them.
        Returns a list of fields that were filled.
        """
        logger.info("Handling essay inputs and complex application questions...")
        fields = await FieldDetector.detect_fields(page)
        filled = []
        
        for field in fields:
            label = field["label"]
            tag_name = field["type"]
            classification = await FormFiller.classify_field(label, tag_name)
            
            if classification == "essay":
                # Find matching generated answer
                value = ""
                for key, ans in essay_answers.items():
                    if key.lower() in label.lower() or label.lower() in key.lower():
                        value = ans
                        break
                        
                if not value and essay_answers:
                    value = list(essay_answers.values())[0]
                    
                if value:
                    logger.info(f"Answering essay question: '{label}'")
                    success = await FormFiller.fill(page, field["id"], value)
                    if success:
                        filled.append(label or field["id"])
                        
        return filled
