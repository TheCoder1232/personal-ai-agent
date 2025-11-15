# file: ui/ui_utils.py
from enum import IntEnum

class UIConstants:
    """Central location for all magic numbers and dimensions"""
    # Input textbox dimensions
    INPUT_MIN_HEIGHT = 60
    INPUT_MAX_HEIGHT = 200
    INPUT_LINE_HEIGHT = 20
    
    # Button dimensions
    BUTTON_WIDTH = 60
    
    # Padding and spacing
    PADDING_SMALL = 5
    PADDING_MEDIUM = 10
    
    # Message limits
    MAX_MESSAGE_LENGTH = 10000
    
    # Timing
    SCROLL_DELAY_MS = 10  # Reduced from 50ms
    UI_UPDATE_BATCH_MS = 100  # Batch UI updates
    
    # Window geometry
    DEFAULT_GEOMETRY = "400x600"


class GridPosition(IntEnum):
    """Enum for grid layout positions"""
    BRANCH_ROW = 0
    CHAT_HISTORY_ROW = 1
    ATTACHMENT_ROW = 2
    INPUT_ROW = 3
    
    MAIN_COLUMN = 0
    CLEAR_BUTTON_COLUMN = 1
    SEND_BUTTON_COLUMN = 2
