import streamlit as st
import requests
import json
import base64
import io
from PIL import Image
from PIL.PngImagePlugin import PngInfo

# ==========================================
# 1. 網頁基本設定與介面美化
# ==========================================
st.set_page_config(
    page_title="SillyTavern 角色卡生成器", 
    page_icon="🌌",
    layout="wide"
)

st.title("🌌 SillyTavern 角色卡 AI 生成器")
st.caption("專業級 AI 角色扮演人設與卡片設計平台 (局部重骰升級版)")
st.write("---")

# ==========================================
# 2. 影像處理與卡片封裝核心功能
# ==========================================
def generate_default_avatar(name):
    """當沒有上傳圖片時，動態生成一張預設圖片"""
    from PIL import ImageDraw
    import numpy as np
    width, height = 400, 600
    array = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        r = int(20 + (y / height) * 45)
        g = int(10 + (y / height) * 20)
        b = int(50 + (y / height) * 110)
        array[y, :, :] = [r, g, b]
    img = Image.fromarray(array)
    draw = ImageDraw.Draw(img)
    draw.rectangle([15, 15, width-15, height-15], outline=(129, 140, 248), width=3)
    draw.text((width//2 - 45, height//2 - 10), f"★ {name} ★", fill=(255, 255, 255))
    draw.text((width//2 - 50, height//2 + 20), "AI GENERATED", fill=(129, 140, 248, 100))
    return img

def pack_to_png(chara_data, base_image):
    """將 Python 字典封裝進 PNG，並移除專案標籤與註記"""
    full_data = {
        "name": chara_data.get("name", "Unknown"),
        "description": chara_data.get("description", ""),
        "personality": chara_data.get("personality", ""),
        "scenario": chara_data.get("scenario", ""),
        "first_mes": chara_data.get("first_mes", ""),
        "mes_example": chara_data.get("mes_example", ""),
        # 1. 將這裡改為空字串，或換成你想要的專業產品註記
        "creator_notes": "來自 AI 角色卡生成器", 
        "alternate_greetings": [],
        # 2. 這裡移除了 "Taiwan" 標籤，只保留 "AI Generated"（你也可以改成別的，例如 "Anime"）
        "tags": ["AI Generated"], 
        "creator": "AI Card Generator",
        "character_version": "main",
        "extensions": {}
    }
    st_v2_format = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": full_data
    }
    json_bytes = json.dumps(st_v2_format, ensure_ascii=False).encode('utf-8')
    encoded_str = base64.b64encode(json_bytes).decode('utf-8')
    metadata = PngInfo()
    metadata.add_text("chara", encoded_str)
    buf = io.BytesIO()
    base_image.save(buf, format="PNG", pnginfo=metadata)
    buf.seek(0)
    return buf

# ==========================================
# 3. 側邊欄 (Sidebar)：API 設定
# ==========================================
st.sidebar.header("🔑 API 設定基地")
api_provider = st.sidebar.selectbox(
    "選擇 AI 模組來源",
    ["Google Gemini ", "OpenAI ChatGPT ", "Anthropic Claude ", "DeepSeek"]
)
provider_key = api_provider.split(' ')[0]
api_key = st.sidebar.text_input(f"請輸入你的 {provider_key} API Key", type="password")
# 加入信任聲明與開源連結
st.sidebar.write("---") # 加一條分隔線讓畫面更好看
st.sidebar.info("🔒 **隱私與安全聲明**\n\n本網站為開源專案，您的 API Key 僅會在當下發送給 AI 官方伺服器，**絕對不會儲存於任何資料庫或後台**。重新整理網頁後即刻銷毀。")
st.sidebar.markdown("[👉 點此查看本專案 GitHub 開源程式碼](https://github.com/bruhbruhdb2/sillytavern-ai-generator.git)")

# ==========================================
# 4. 整合式多平台 API 呼叫函式 (支援強制純文字模式)
# ==========================================
def call_llm(provider, api_key, user_prompt, uploaded_image=None, require_json=True):
    """動態路由並呼叫各大廠 API，require_json 可控制是否強制輸出 JSON"""
    if require_json:
        system_instruction = "你是一位精通動漫設定、輕小說寫作風格與角色扮演格式的卡片設計大師。請嚴格輸出 JSON 格式，不要有任何 Markdown 引號包裝，並使用「台灣繁體中文」撰寫。"
    else:
        system_instruction = "你是一位精通文字角色扮演的寫作大師。請直接輸出「純文字內容」，絕對不要包裝成 JSON，也不要有額外的解釋廢話，並使用「台灣繁體中文」撰寫。"
    
    image_b64 = None
    mime_type = "image/jpeg"
    if uploaded_image:
        image_bytes = uploaded_image.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        if uploaded_image.name.lower().endswith('.png'):
            mime_type = "image/png"

    def clean_json(text):
        if require_json:
            return text.replace("```json", "").replace("```", "").strip()
        return text.strip()

    if "Gemini" in provider:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        parts = [{"text": user_prompt}]
        if image_b64:
            parts.append({"inlineData": {"mimeType": mime_type, "data": image_b64}})
        payload = {"contents": [{"parts": parts}], "systemInstruction": {"parts": [{"text": system_instruction}]}}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return clean_json(response.json()["candidates"][0]["content"]["parts"][0]["text"])
        else:
            raise Exception(f"Gemini API 錯誤: {response.text}")
            
    elif "OpenAI" in provider:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        user_content = [{"type": "text", "text": user_prompt}]
        if image_b64:
            user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}})
        payload = {"model": "gpt-4o", "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_content}]}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return clean_json(response.json()["choices"][0]["message"]["content"])
        else:
            raise Exception(f"OpenAI API 錯誤: {response.text}")
            
    elif "Anthropic" in provider:
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        user_content = []
        if image_b64:
            user_content.append({"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}})
        user_content.append({"type": "text", "text": user_prompt})
        payload = {"model": "claude-3-5-sonnet-20241022", "max_tokens": 4000, "system": system_instruction, "messages": [{"role": "user", "content": user_content}]}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return clean_json(response.json()["content"][0]["text"])
        else:
            raise Exception(f"Anthropic API 錯誤: {response.text}")
            
    elif "DeepSeek" in provider:
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return clean_json(response.json()["choices"][0]["message"]["content"])
        else:
            raise Exception(f"DeepSeek API 錯誤: {response.text}")

# ==========================================
# 5. 網頁主畫面配置與生成邏輯
# ==========================================
col1, col2 = st.columns([1.2, 1])

# 初始化 Session State
if "parsed_char" not in st.session_state:
    st.session_state.parsed_char = None
if "character_image" not in st.session_state:
    st.session_state.character_image = None
if "character_name" not in st.session_state:
    st.session_state.character_name = "Unknown"

# ---------- 左側：輸入區 ----------
with col1:
    st.header("🛠️ 1. 設定與輸入區")
    tab1, tab2 = st.tabs(["📚 召喚已有角色", "🎲 鍛造原創角色"])
    
    with tab1:
        st.subheader("召喚已有動漫/遊戲/現實人物角色")
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            char_name = st.text_input("請輸入角色名稱 (例如：七海千秋)")
        with row1_col2:
            source = st.text_input("出自哪部作品？ (例如：槍彈辯駁)")
            
        bg_lore = st.text_area("📖 角色百科資料補充 (防幻覺)", height=120)
        uploaded_img = st.file_uploader("🖼️ 上傳角色圖片 (可選)", type=["png", "jpg", "jpeg"], key="img1")
        
        if st.button("✨ 開始召喚靈魂"):
            if not api_key:
                st.error("❌ 請先輸入 API Key！")
            elif not char_name:
                st.warning("⚠️ 請填寫角色名稱！")
            else:
                st.session_state.character_name = char_name
                st.session_state.character_image = Image.open(uploaded_img) if uploaded_img else generate_default_avatar(char_name)

                with st.spinner("🔮 正在分析資料與圖片，請稍候..."):
                    lore_instruction = f"【🚨 參考基準】：\n{bg_lore}\n" if bg_lore else ""
                    image_instruction = "【👁️ 外觀描述指令】：請利用視覺能力觀察我上傳的圖片並描述外觀。" if uploaded_img else ""
                    
                    prompt = f"""請幫我建立作品《{source}》中的角色《{char_name}》設定。
{lore_instruction}
{image_instruction}
嚴格回傳 JSON：
{{
    "name": "{char_name}",
    "description": "包含：【基本背景】、【人際關係】、【性格特質】、【外貌與服裝】、【戰鬥與技能】。",
    "personality": "性格關鍵字",
    "scenario": "初次相遇場景",
    "first_mes": "生動的首發問候語（星號寫動作，雙引號寫對白）",
    "mes_example": "3 段對話範例，以 <START>\\n{{{{char}}}}: 開頭。"
}}"""
                    try:
                        raw_json = call_llm(api_provider, api_key, prompt, uploaded_img, require_json=True)
                        st.session_state.parsed_char = json.loads(raw_json)
                        st.success("🎉 召喚成功！請在右側進行微調或下載。")
                    except Exception as e:
                        st.error(f"💥 發生錯誤：{e}")

    with tab2:
        st.subheader("設定原創角色條件")
        oc_name = st.text_input("原創角色名稱", "莉莉絲")
        selected_world = st.selectbox("世界觀類型", ["日系奇幻", "賽博龐克", "現代校園", "克蘇魯神話", "自定義（手動輸入）"])
        oc_world = st.text_input("手動輸入世界觀") if selected_world == "自定義（手動輸入）" else selected_world
        oc_trait = st.text_area("角色屬性與特徵描述", "傲嬌女僕，私底下極度喜歡吃甜食")
        uploaded_img_oc = st.file_uploader("🖼️ 上傳原創角色立繪 (可選)", type=["png", "jpg", "jpeg"], key="img2")
        
        if st.button("🔥 熔鑄全新靈魂"):
            if not api_key:
                st.error("❌ 請先輸入 API Key！")
            elif not oc_name or not oc_world:
                st.warning("⚠️ 請填寫完整名稱與世界觀！")
            else:
                st.session_state.character_name = oc_name
                st.session_state.character_image = Image.open(uploaded_img_oc) if uploaded_img_oc else generate_default_avatar(oc_name)

                with st.spinner("🔮 正在熔鑄原創角色靈魂，請稍候..."):
                    image_instruction = "【👁️ 外觀描述指令】：請利用視覺能力觀察我上傳的圖片並描述外觀。" if uploaded_img_oc else ""
                    prompt = f"""請幫我原創設計一個全新角色卡。條件：名稱：{oc_name} / 世界觀：{oc_world} / 屬性：{oc_trait}
{image_instruction}
嚴格回傳 JSON：
{{
    "name": "{oc_name}",
    "description": "包含：【世界觀與身分】、【性格特質】、【外貌特徵】、【特殊能力】。",
    "personality": "性格關鍵字",
    "scenario": "初次相遇場景",
    "first_mes": "生動的首發對白（星號寫動作，雙引號寫對白）",
    "mes_example": "3 段對話範例，以 <START>\\n{{{{char}}}}: 開頭。"
}}"""
                    try:
                        raw_json = call_llm(api_provider, api_key, prompt, uploaded_img_oc, require_json=True)
                        st.session_state.parsed_char = json.loads(raw_json)
                        st.success("🎉 全新原創靈魂熔鑄成功！請在右側進行微調或下載。")
                    except Exception as e:
                        st.error(f"💥 發生錯誤：{e}")

# ---------- 右側：預覽、微調與下載區 ----------
with col2:
    st.header("🖥️ 2. 預覽、微調與封裝區")
    
    if st.session_state.parsed_char:
        st.info("💡 你可以直接手動修改下方文字，或使用「🎲 局部重骰」讓 AI 幫你重寫特定區塊！")
        
        # 使用者即時編輯區塊
        st.session_state.parsed_char["name"] = st.text_input("角色名稱", value=st.session_state.parsed_char.get("name", ""))
        st.session_state.parsed_char["description"] = st.text_area("📚 核心設定 (Description)", value=st.session_state.parsed_char.get("description", ""), height=150)
        st.session_state.parsed_char["personality"] = st.text_input("🎭 性格標籤 (Personality)", value=st.session_state.parsed_char.get("personality", ""))
        
        st.write("---")
        
        # 局部重骰區塊：首發問候語
        col_f1, col_f2 = st.columns([4, 1])
        with col_f1:
            st.session_state.parsed_char["first_mes"] = st.text_area("💬 首發問候語 (First Message)", value=st.session_state.parsed_char.get("first_mes", ""), height=150)
        with col_f2:
            st.write("") # 排版對齊用
            st.write("")
            if st.button("🎲 重骰此段", key="reroll_first"):
                with st.spinner("重骰中..."):
                    reroll_prompt = f"""這是角色《{st.session_state.parsed_char['name']}》的基礎設定：
{st.session_state.parsed_char['description']}
性格：{st.session_state.parsed_char['personality']}
請根據上述設定，為她/他「重新撰寫一段全新的首發問候語(First Message)」。
要求：動作神情用星號 `*` 包住，對白用雙引號 `"` 包住。直接回傳純文字，不要解釋。"""
                    try:
                        new_text = call_llm(api_provider, api_key, reroll_prompt, require_json=False)
                        st.session_state.parsed_char["first_mes"] = new_text
                        st.rerun() # 立即刷新網頁畫面
                    except Exception as e:
                        st.error(f"重骰失敗: {e}")

        # 局部重骰區塊：對話範例
        col_m1, col_m2 = st.columns([4, 1])
        with col_m1:
            st.session_state.parsed_char["mes_example"] = st.text_area("🗣️ 對話範例 (Message Example)", value=st.session_state.parsed_char.get("mes_example", ""), height=150)
        with col_m2:
            st.write("")
            st.write("")
            if st.button("🎲 重骰此段", key="reroll_mes"):
                with st.spinner("重骰中..."):
                    reroll_prompt = f"""這是角色《{st.session_state.parsed_char['name']}》的基礎設定：
{st.session_state.parsed_char['description']}
性格：{st.session_state.parsed_char['personality']}
請根據上述設定，為她/他「重新撰寫 3 段全新的對話範例」。
要求：每一段必須以 `<START>\n{{{{char}}}}: ` 開頭，用星號 `*` 寫動作。直接回傳純文字，不要解釋。"""
                    try:
                        new_text = call_llm(api_provider, api_key, reroll_prompt, require_json=False)
                        st.session_state.parsed_char["mes_example"] = new_text
                        st.rerun()
                    except Exception as e:
                        st.error(f"重骰失敗: {e}")

        # 下載區塊
        st.write("---")
        try:
            png_buffer = pack_to_png(st.session_state.parsed_char, st.session_state.character_image)
            st.download_button(
                label=f"💾 封印並下載 {st.session_state.character_name} 角色卡 (PNG)",
                data=png_buffer,
                file_name=f"{st.session_state.character_name}_SillyTavern.png",
                mime="image/png",
                use_container_width=True
            )
            if st.session_state.character_image:
                st.image(st.session_state.character_image, caption="卡片封面", width=150)
        except Exception as e:
            st.error(f"⚠️ 封裝失敗：{e}")

    else:
        st.info("請先在左側生成角色，這裡將顯示可編輯的詳細面板。")
        st.button("💾 下載 PNG 角色卡", disabled=True, use_container_width=True)