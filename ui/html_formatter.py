# file: ui/html_formatter.py
import logging
import markdown
import html
from typing import Dict

try:
    from bs4 import BeautifulSoup
    BS_AVAILABLE = True
except ImportError:
    print("WARNING: BeautifulSoup4 not found. Inline styles will be limited. Install: pip install beautifulsoup4")
    BeautifulSoup = None
    BS_AVAILABLE = False

class HTMLFormatter:
    """Separate class for HTML/CSS formatting logic"""
    
    def __init__(self, theme_colors: Dict[str, str]):
        self.colors = theme_colors
        self._style_cache = {}
        self._setup_styles()
    
    def _setup_styles(self):
        """Initialize all CSS styles"""
        self.STYLE_WRAPPER = "margin-bottom: 10px;"
        self.STYLE_P = "margin: 0; padding: 0;"
        self.STYLE_B_LABEL = f"color: {self.colors['text']}; font-weight: bold;"
        self.STYLE_STRONG_EMPHASIS = f"color: {self.colors['link']}; font-weight: bold;"
        
        self.STYLE_PRE = (
            f"background-color: {self.colors['code_bg']}; "
            f"color: {self.colors['text']}; "
            f"padding: 10px; "
            f"border-radius: 5px; "
            f"font-family: 'Courier New', Courier, monospace; "
            f"white-space: pre-wrap; "
            f"word-wrap: break-word; "
            f"overflow-x: auto;"
        )
        
        self.STYLE_CODE = (
            f"background-color: {self.colors['inline_bg']}; "
            f"color: {self.colors['text']}; "
            f"padding: 2px 4px; "
            f"border-radius: 3px; "
            f"font-family: 'Courier New', Courier, monospace;"
        )
        
        self.STYLE_I = "color: #999999; font-style: italic;"
        self.STYLE_ERROR = "color: #FF4444; font-weight: bold;"

        # Header styles (using 'em' for relative sizing)
        self.STYLE_H1 = f"font-size: 2em; font-weight: bold; color: {self.colors['text']}; margin: 0.67em 0;"
        self.STYLE_H2 = f"font-size: 1.5em; font-weight: bold; color: {self.colors['text']}; margin: 0.83em 0;"
        self.STYLE_H3 = f"font-size: 1.17em; font-weight: bold; color: {self.colors['text']}; margin: 1em 0;"
        self.STYLE_H4 = f"font-size: 1em; font-weight: bold; color: {self.colors['text']}; margin: 1.33em 0;"
        self.STYLE_H5 = f"font-size: 0.83em; font-weight: bold; color: {self.colors['text']}; margin: 1.67em 0;"
        self.STYLE_H6 = f"font-size: 0.67em; font-weight: bold; color: {self.colors['text']}; margin: 2.33em 0;"
        
        # List styles
        self.STYLE_UL_OL = "margin-left: 25px; padding-left: 5px;"
        self.STYLE_LI = "margin-bottom: 5px;"
    
    def convert_md_to_html(self, md_content: str) -> str:
        """Convert markdown to HTML with safety"""
        try:
            # --- MODIFIED: Added 'nl2br' to match comment in create_message_html ---
            return markdown.markdown(
                md_content, 
                extensions=['fenced_code', 'nl2br'],
                output_format='html'
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Markdown conversion error: {e}")
            return html.escape(md_content).replace('\n', '<br>')
    
    def sanitize_input(self, text: str) -> str:
        """Sanitize user input to prevent XSS"""
        # Escape HTML entities
        sanitized = html.escape(text)
        # Preserve newlines for display
        return sanitized.replace('\n', '<br>')
    
    def apply_inline_styles(self, html_content: str) -> str:
        """Apply inline CSS styles to HTML with caching and improved readability."""
        if not BS_AVAILABLE or BeautifulSoup is None:
            return html_content

        content_hash = hash(html_content)
        if content_hash in self._style_cache:
            return self._style_cache[content_hash]

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            tag_styles = {
                'b': self.STYLE_B_LABEL,
                'strong': self.STYLE_STRONG_EMPHASIS,
                'p': self.STYLE_P,
                'pre': self.STYLE_PRE,
                'i': self.STYLE_I,
                'h1': self.STYLE_H1,
                'h2': self.STYLE_H2,
                'h3': self.STYLE_H3,
                'h4': self.STYLE_H4,
                'h5': self.STYLE_H5,
                'h6': self.STYLE_H6,
                'ul': self.STYLE_UL_OL,
                'ol': self.STYLE_UL_OL,
                'li': self.STYLE_LI,
            }

            for tag_name, style in tag_styles.items():
                for tag in soup.find_all(tag_name):
                    if not tag.get('style'):
                        tag['style'] = style

            # Special handling for inline <code> vs <pre><code>
            for tag in soup.find_all('code'):
                if not tag.get('style'):
                    if tag.find_parent('pre'):
                        # Code inside pre gets a simpler style override
                        tag['style'] = "font-family: 'Courier New', Courier, monospace;"
                    else:
                        # Standalone inline code
                        tag['style'] = self.STYLE_CODE
            
            styled_html = str(soup)

            # Limit cache size
            if len(self._style_cache) > 50:
                self._style_cache.clear()
            self._style_cache[content_hash] = styled_html
            
            return styled_html

        except Exception as e:
            logging.getLogger(__name__).error(f"Error applying inline styles: {e}")
            return html_content
    
    def create_message_html(self, label: str, content: str, is_error: bool = False) -> str:
        """Create formatted message HTML"""
        
        # 1. Create the label
        label_html = f"<b>{html.escape(label)}:</b>"
        
        # 2. Process the content
        processed_content: str
        if label == "You":
            # User input: Sanitize it to prevent XSS and preserve newlines
            processed_content = self.sanitize_input(content)
        elif is_error:
            # Error message: Sanitize, preserve newlines, and style as error
            sanitized_content = self.sanitize_input(content)
            processed_content = f"<span style='{self.STYLE_ERROR}'>{sanitized_content}</span>"
        else:
            # Agent/System output: Assume it's Markdown and convert it
            # convert_md_to_html already handles newlines with 'nl2br' extension
            processed_content = self.convert_md_to_html(content)
            
        # 3. Combine them with <br> tags for separation
        # We are not running the combined string through markdown parser again
        return f"{label_html}<br><br>{processed_content}"