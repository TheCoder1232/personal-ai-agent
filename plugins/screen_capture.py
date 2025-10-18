# file: plugins/screen_capture.py

import logging
import asyncio
import mss
import io
import base64
from PIL import Image
from typing import Tuple, Optional
from plugins import PluginBase
from core.service_locator import ServiceLocator
from core.event_dispatcher import EventDispatcher

class ScreenCapturePlugin(PluginBase):
    """
    A plugin to capture the screen, resize, and encode it.
    """
    
    def __init__(self, service_locator: ServiceLocator):
        super().__init__(service_locator)
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config_loader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_width = 2000 # Max width for resized image

    def get_metadata(self):
        return {
            "name": "ScreenCapture",
            "version": "1.0.0",
            "description": "Captures the screen on command."
        }

    def initialize(self):
        """Called when the plugin is first loaded."""
        self.events.subscribe("PLUGIN_EVENT.SCREEN_CAPTURE", self.on_capture_request)
        self.logger.info("ScreenCapturePlugin initialized and subscribed to SCREEN_CAPTURE event.")

    async def on_capture_request(self, *args, **kwargs):
        """
        Event handler for the capture request (e.g., from hotkey).
        This runs in the asyncio thread.
        """
        self.logger.info("Screen capture request received.")
        
        try:
            # 1. Capture Screen (this is a sync, I/O bound call)
            # We run it in a thread to avoid blocking the async loop
            image_bytes, original_size = await asyncio.to_thread(self.capture_screen)
            if not image_bytes or not original_size:
                return

            # 2. Resize and Encode (this is CPU bound)
            # Also run in a thread
            encoded_image = await asyncio.to_thread(self.process_image, image_bytes, original_size)
            
            self.logger.info(f"Screen captured and encoded (Base64 length: {len(encoded_image)}).")
            
            # 3. Emit event with image data for the agent
            await self.events.publish(
                "PLUGIN_EVENT.SCREEN_CAPTURED", 
                image_data=encoded_image,
                format="base64"
            )
            
            # 4. Notify user and open chat
            await self.events.publish(
                "NOTIFICATION_EVENT.INFO",
                title="Screen Captured",
                message="Screenshot attached. Opening chat..."
            )
            await self.events.publish("UI_EVENT.OPEN_CHAT")

        except Exception as e:
            self.logger.error(f"Failed to capture screen: {e}", exc_info=True)
            await self.events.publish("NOTIFICATION_EVENT.ERROR", title="Capture Failed", message=str(e))

    def capture_screen(self) -> Tuple[Optional[bytes], Optional[tuple]]:
        """Takes a screenshot of all monitors."""
        try:
            with mss.mss() as sct:
                # Get a screenshot of all monitors combined
                sct_img = sct.grab(sct.monitors[0])
                # Convert to raw bytes in PNG format
                img_bytes = sct_img.bgra
                return img_bytes, sct_img.size
        except Exception as e:
            self.logger.error(f"MSS capture failed: {e}")
            return None, None

    def process_image(self, image_bytes: bytes, original_size: tuple) -> str:
        """Resizes, compresses, and base64 encodes the image."""
        
        # Load image from bytes into PIL
        img = Image.open(io.BytesIO(image_bytes))
        
        # Resize if it's too large
        width, height = original_size
        if width > self.max_width:
            self.logger.debug(f"Resizing image from {width}px to {self.max_width}px width.")
            scale = self.max_width / width
            new_height = int(height * scale)
            img = img.resize((self.max_width, new_height), Image.Resampling.LANCZOS)

        # Save to a new in-memory buffer, with compression
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=85) # Use JPEG for better compression
        
        # Get bytes and Base64 encode
        img_bytes = output_buffer.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')