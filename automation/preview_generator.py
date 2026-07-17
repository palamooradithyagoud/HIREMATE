import os
import time
import logging

logger = logging.getLogger("JobApplicationAgent.PreviewGenerator")

class PreviewGenerator:
    @staticmethod
    async def generate_preview(page, screenshot_dir: str) -> str:
        """
        Takes a full page screenshot and returns the file path.
        """
        logger.info("Generating visual form preview screenshot...")
        os.makedirs(screenshot_dir, exist_ok=True)
        filename = f"preview_{int(time.time())}.png"
        filepath = os.path.join(screenshot_dir, filename)
        await page.screenshot(path=filepath)
        return f"/static/screenshots/{filename}"
