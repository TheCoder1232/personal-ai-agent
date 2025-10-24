import customtkinter as ctk
from tkhtmlview import HTMLLabel
from customtkinter import CTkScrollableFrame

# --- App Setup ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.geometry("700x550")
app.title("Beautified HTML Viewer (Inline-Style Fix)")

# --- 1. Define Theme-Aware Colors ---
BG_COLOR = "#2B2B2B"
TEXT_COLOR = "#DCE4EE"
LINK_COLOR = "#5DADE2"
CODE_BG = "#333333"

# --- 2. Create a CTkScrollableFrame ---
scroll_frame = CTkScrollableFrame(app, fg_color=BG_COLOR)
scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

# --- 3. Create the HTMLLabel (no changes here) ---
html_view = HTMLLabel(scroll_frame, 
                      background=BG_COLOR,
                      foreground=TEXT_COLOR)
html_view.pack(fill="both", expand=True, padx=15, pady=15)


# --- 4. Define your HTML content (with INLINE styles) ---

# To make this cleaner, let's define the styles we'll reuse
base_font = "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.5;"
code_font = f"font-family: 'Courier New', Courier, monospace; background-color: {CODE_BG}; padding: 2px 5px; border-radius: 4px;"
link_style = f"color: {LINK_COLOR}; text-decoration: none;"

sample_html = f"""
<div style="{base_font} color: {TEXT_COLOR};">

    <h1 style="color: {LINK_COLOR};">Beautifully Integrated HTML</h1>
    
    <p>
        This content is now inside a 
        <strong>CTkScrollableFrame</strong>, 
        which gives us a modern, theme-matching scrollbar.
    </p>
    
    <p>
        The <code style="{code_font}">HTMLLabel</code> 
        widget's colors are set with inline CSS, 
        making it feel native to the app.
    </p>
    
    <h2>Check out these features:</h2>
    <ul>
        <li>Native <code>CTkScrollbar</code></li>
        <li>Theme-matched background</li>
        <li>Theme-matched text and <a href="https://customtkinter.tomschimansky.com/" style="{link_style}">link colors</a></li>
    </ul>

</div>
"""

# --- 5. Set the HTML content ---
html_view.set_html(sample_html)

# --- Run the App ---
app.mainloop()