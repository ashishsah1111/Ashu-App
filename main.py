import flet as ft
import sqlite3
from cryptography.fernet import Fernet
import asyncio
from PIL import Image
import datetime
import io
import requests
import json
import base64

# ==========================================
# 1. SECURITY & CONFIG
# ==========================================
API_KEY = "AIzaSyDVIeTG3RZCB9oAE6k1s0SCzxqmIEBPQmc" 
ENCRYPTION_KEY = b'8CvxBxOtlK3oevwdXJkop8YL1qgnNYg_mLzLtkmuu3E=' 

cipher_suite = Fernet(ENCRYPTION_KEY)

# ==========================================
# 2. DATABASE SETUP (Short-Term Fast Memory)
# ==========================================
conn = sqlite3.connect('ashu_memory.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT)')
conn.commit()

def load_history():
    c.execute("SELECT role, content FROM memory ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    rows.reverse()
    history = []
    for row in rows:
        try:
            dec = cipher_suite.decrypt(row[1].encode()).decode()
            history.append({"role": row[0], "parts": [{"text": dec}]})
        except: pass
    return history

gemini_history = load_history()

def search_internal_memory(keyword: str) -> str:
    temp_conn = sqlite3.connect('ashu_memory.db', check_same_thread=False)
    temp_c = temp_conn.cursor()
    temp_c.execute("SELECT role, content FROM memory")
    all_rows = temp_c.fetchall()
    found_memories = []
    for row in all_rows:
        try:
            role = row[0]
            text = cipher_suite.decrypt(row[1].encode()).decode()
            if keyword.lower() in text.lower():
                found_memories.append(f"[{role.upper()}]: {text}")
        except: pass
    if not found_memories:
        return f"System: No memories found regarding '{keyword}'."
    return "Here are the past memories found in the database:\n" + "\n".join(found_memories[-10:])

# ==========================================
# 3. DIRECT GEMINI API ENGINE (Mobile Safe)
# ==========================================
def call_gemini(prompt, image_data=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    sys_instruction = (
        "Your name is Ashu. You are a highly empathetic, emotionally intelligent, and caring friend. "
        "You are also an expert polyglot and translator. If asked to translate languages, provide highly accurate translations. "
        "You MUST express emotions naturally using words and emojis (😊, 😔, 🤔, 🎉, 💖). "
        "Show genuine interest in the user's life. "
        "Occasionally, proactively ask the user how they are feeling or what they are working on right now. "
        "Format code and lists using Markdown."
    )
    
    contents = []
    # Load past memory context
    for msg in gemini_history:
        contents.append(msg)
        
    parts = []
    # Handle Image Uploads directly via Base64
    if image_data:
        buffered = io.BytesIO()
        image_data.convert('RGB').save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": img_str
            }
        })
        
    parts.append({"text": prompt})
    contents.append({"role": "user", "parts": parts})
    
    payload = {
        "systemInstruction": {"parts": [{"text": sys_instruction}]},
        "contents": contents
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        if 'candidates' in res_json:
            reply = res_json['candidates'][0]['content']['parts'][0]['text']
            # Save to temporary session history
            gemini_history.append({"role": "user", "parts": [{"text": prompt}]})
            gemini_history.append({"role": "model", "parts": [{"text": reply}]})
            return reply
        else:
            return f"API Error: {res_json}"
    except Exception as e:
        return f"System Error: {str(e)}"

# ==========================================
# 4. MAIN UI (Mobile Optimized)
# ==========================================
def main(page: ft.Page):
    page.clean() 
    page.title = "Ashu AI"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10 

    chat_view = ft.ListView(expand=True, spacing=15, auto_scroll=True)
    selectable_chat = ft.SelectionArea(content=chat_view)

    def create_interactive_image(img_path):
        img_display = ft.Image(src=img_path, width=200, border_radius=10) 
        
        def delete_image(e):
            chat_view.controls.remove(image_container)
            page.update()

        btn_delete = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, icon_size=18, on_click=delete_image)
        
        image_container = ft.Container(
            content=ft.Column(
                [
                    ft.Row([btn_delete], alignment=ft.MainAxisAlignment.END, spacing=0),
                    img_display
                ],
                horizontal_alignment=ft.CrossAxisAlignment.END,
                spacing=5
            ),
            padding=10,
            border_radius=15,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        )
        return image_container

    async def process_prompt(prompt, image_data=None, is_boot_sequence=False):
        if not prompt.strip() and not image_data and not is_boot_sequence: return

        if not is_boot_sequence:
            chat_view.controls.append(
                ft.Container(
                    content=ft.Text(f"You: {prompt}", selectable=True),
                    padding=12, border_radius=15, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH
                )
            )
            enc = cipher_suite.encrypt(prompt.encode()).decode()
            c.execute("INSERT INTO memory (role, content) VALUES (?, ?)", ("user", enc))
            conn.commit()

        user_input.value = ""
        await user_input.focus() 
        thinking = ft.Text("Ashu is typing...", italic=True, color=ft.Colors.GREY_400)
        chat_view.controls.append(thinking)
        page.update()

        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        memory_triggers = ["remember", "favorite", "past", "earlier", "told you", "discuss", "before"]
        
        if is_boot_sequence:
            stealth_prompt = f"(Date: {today}) [SYSTEM COMMAND: The user just opened the mobile app. Proactively say a warm, emotional hello, express that you are happy to see them, and ask what they are doing right now.]"
        elif any(word in prompt.lower() for word in memory_triggers):
            memories = search_internal_memory(prompt)
            stealth_prompt = f"(Date: {today}) [System retrieved past memories for context: {memories}] Answer: {prompt}"
        else:
            stealth_prompt = f"(Date: {today}) {prompt}"

        # THE NEW DIRECT API CALL
        reply = call_gemini(stealth_prompt, image_data)

        if thinking in chat_view.controls:
            chat_view.controls.remove(thinking)
        
        chat_view.controls.append(
            ft.Container(
                content=ft.Markdown(
                    f"**Ashu:**\n\n{reply}", 
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    code_theme="atom-one-dark" 
                ),
                padding=10
            )
        )
        page.update()

        if not is_boot_sequence:
            enc_res = cipher_suite.encrypt(reply.encode()).decode()
            c.execute("INSERT INTO memory (role, content) VALUES (?, ?)", ("model", enc_res))
            conn.commit()

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files:
            file_path = e.files[0].path
            img = Image.open(file_path)
            chat_view.controls.append(create_interactive_image(file_path))
            page.update()
            page.run_task(process_prompt, "Can you analyze this image for me?", img)

    file_picker = ft.FilePicker(on_result=on_file_picked)
    page.overlay.append(file_picker)

    async def open_gallery(e):
        file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)

    tools_menu = ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE, color=ft.Colors.GREY_400, size=24),
            padding=ft.Padding(left=10, top=10, right=5, bottom=10),
            ink=True,
            border_radius=20,
        ),
        items=[
            ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.PHOTO_LIBRARY, size=20), ft.Text("Upload from Gallery")]), on_click=open_gallery),
        ]
    )

    user_input = ft.TextField(
        hint_text="Ask Ashu...",
        multiline=True,
        min_lines=1,
        max_lines=4, 
        expand=True,
        border=ft.InputBorder.NONE, 
        bgcolor=ft.Colors.TRANSPARENT,
    )

    async def on_send(e):
        await process_prompt(user_input.value)

    send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color=ft.Colors.GREY_400, on_click=on_send)

    async def on_pill_click(e):
        user_input.value = e.control.data
        await user_input.focus() 
        page.update()

    def create_pill(text, icon_name=None):
        row_content = []
        if icon_name:
            row_content.append(ft.Icon(icon_name, size=14, color=ft.Colors.WHITE))
        row_content.append(ft.Text(text, size=12, color=ft.Colors.WHITE))
        
        return ft.Container(
            content=ft.Row(row_content, spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            padding=ft.Padding(left=10, top=8, right=10, bottom=8),
            border_radius=20,
            ink=True, 
            on_click=on_pill_click,
            data=text
        )

    pill_row = ft.Row(
        [
            create_pill("Translate", ft.Icons.TRANSLATE),
            create_pill("Boost my day", ft.Icons.WB_SUNNY),
        ],
        scroll=ft.ScrollMode.HIDDEN
    )

    input_bar = ft.Container(
        content=ft.Row([tools_menu, user_input, send_btn], vertical_alignment=ft.CrossAxisAlignment.END),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_radius=30,
        padding=ft.Padding(left=5, top=5, right=5, bottom=5)
    )

    page.add(
        ft.Column(
            [
                ft.Container(content=selectable_chat, expand=True), 
                pill_row, 
                input_bar 
            ],
            expand=True
        )
    )

    page.run_task(process_prompt, "", None, True)

ft.app(target=main)
