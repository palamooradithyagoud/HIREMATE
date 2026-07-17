import logging
from agents.field_mapping_agent import FieldMappingAgent
from automation.field_detector import FieldDetector

logger = logging.getLogger("JobApplicationAgent.FieldMapper")

class FieldMapper:
    def __init__(self):
        self.agent = FieldMappingAgent()

    async def get_field_mappings(self, page, profile: dict) -> dict:
        """
        Detects fields from the active page, matches them using AI Field Mapping Agent,
        and returns a dictionary mapping field IDs to profile keys.
        """
        logger.info("Starting candidate attribute mapping loop...")
        fields = await FieldDetector.detect_fields(page)
        return self.agent.map_fields(fields, profile)
