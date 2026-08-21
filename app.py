import streamlit as st
from google import genai
from google.genai import types
import base64

# 1. 页面配置
st.set_page_config(
    page_title="Gemini Super Chat",
    page_icon="🍌",
    layout="wide"
)

st.title("✨ GeminiAPI v4.1 全能助手 (Pro & Nano)中转站模式")

# --- 从 URL 获取参数 ---
url_key = st.query_params.get("key", "")

# 2. 侧边栏：配置与上传
with st.sidebar:
    st.header("⚙️ 配置")

    # API Key 输入
    api_key = st.text_input(
        "API Key (中转站 Key)",
        value=url_key,
        type="password",
        help="你可以通过 URL ?key=你的API密钥 来自动填充"
    )

    st.divider()
    
    # 查询 Key 使用量的链接
    if api_key:
        query_url = f"https://chaxun.tpkcur.xyz/?{api_key}"
        st.markdown(f"[🔍 查询该 Key 使用量]({query_url})")
    else:
        st.caption("输入 Key 后可查询使用量")

    st.divider()

    # 模型选择
    model_map = {
        "Gemini-3.7-flash": "gemini-3.7-flash",
        "Gemini-3.6-flash": "gemini-3.6-flash",
        "Gemini 3.1 Pro": "gemini-3.1-pro-preview",
    }

    selected_label = st.selectbox(
        "选择模型", 
        list(model_map.keys()),
        index=0
    )
    model_id = model_map[selected_label]

    # 提示用户当前模型是否支持画图
    if "Banana" in selected_label:
        st.caption("ℹ️ 当前模型支持图像生成与编辑")

    st.divider()

    # 文件上传组件（支持多文件）
    st.header("📤 上传文件/图片")
    uploaded_files = st.file_uploader(
        "支持图片、PDF、文本等（可多选）", 
        type=['png', 'jpg', 'jpeg', 'webp', 'pdf', 'txt', 'csv', 'cs', 'c', 'cpp', 'h', 'xaml', 'xml', 'pas'],
        accept_multiple_files=True,  # 关键修改：允许多文件上传
        key="file_uploader"
    )

    if st.button("🗑️ 清空对话历史"):
        st.session_state.messages = []
        st.rerun()

# 3. 初始化 Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 检查 API Key
if not api_key:
    st.info("👈 请在左侧输入 API Key 开始对话。")
    st.stop()

# ==========================================
# 5. 初始化客户端 (核心修改点：接入中转站)
# ==========================================
try:
    client = genai.Client(
        api_key=api_key,
        http_options={
            "base_url": "https://quanzil.com",       # 指向中转站地址
            "headers": {
                "Authorization": f"Bearer {api_key}" # 按要求传入 Bearer 认证头
            }
        }
    )
except Exception as e:
    st.error(f"客户端初始化失败: {e}")
    st.stop()

# --- 辅助函数：显示单个文件内容 ---
def display_content(content_data, mime_type):
    if not content_data:
        return
    if mime_type and mime_type.startswith("image/"):
        st.image(content_data, width=400)
    elif mime_type == "application/pdf":
        st.caption("📄 [PDF 文件]")
    else:
        st.caption(f"📎 [文件: {mime_type}]")

# 6. 显示历史聊天记录
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # 1. 显示用户上传的文件（可能多个）
        if message.get("files"):
            for file_data, mime_type in message["files"]:
                display_content(file_data, mime_type)

        # 2. 显示文本内容
        if message.get("content"):
            st.markdown(message["content"])

        # 3. 显示模型生成的图片
        if message.get("generated_images"):
            for img_data, img_mime in message["generated_images"]:
                st.image(img_data, caption="Generated Image", width=400)

# 7. 处理用户输入
if prompt := st.chat_input("输入你的问题... (例如: 画一只在太空冲浪的猫)"):

    # 准备当前消息的数据结构
    current_msg = {
        "role": "user",
        "content": prompt,
        "files": []  # 改为列表，存储多个文件
    }

    # 构建 API 请求的 parts
    user_parts = [types.Part.from_text(text=prompt)]

    # 处理上传的多个文件
    if uploaded_files:
        for uploaded_file in uploaded_files:
            bytes_data = uploaded_file.getvalue()
            mime_type = uploaded_file.type
            # 保存到当前消息
            current_msg["files"].append((bytes_data, mime_type))
            # 添加为 API 部分
            user_parts.append(types.Part.from_bytes(data=bytes_data, mime_type=mime_type))

    # 显示用户消息 (UI)
    with st.chat_message("user"):
        if current_msg["files"]:
            for file_data, mime_type in current_msg["files"]:
                display_content(file_data, mime_type)
        st.markdown(prompt)

    # 保存用户消息到历史
    st.session_state.messages.append(current_msg)

    # 生成 AI 回复
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response_text = ""
        generated_images = []

        try:
            # --- 构建历史记录 ---
            history_contents = []
            for msg in st.session_state.messages[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                parts = []

                if msg.get("content"):
                    parts.append(types.Part.from_text(text=msg["content"]))

                # 处理历史消息中的多个文件
                if msg.get("files"):
                    for file_data, mime_type in msg["files"]:
                        parts.append(types.Part.from_bytes(data=file_data, mime_type=mime_type))

                if parts:
                    history_contents.append(types.Content(role=role, parts=parts))

            # --- 创建聊天会话 ---
            chat = client.chats.create(
                model=model_id,
                history=history_contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )

            # --- 发送请求 ---
            response = chat.send_message_stream(user_parts)

            # --- 处理流式响应 ---
            for chunk in response:
                if chunk.text:
                    full_response_text += chunk.text
                    message_placeholder.markdown(full_response_text + "▌")

                # 处理非文本内容 (图片)
                if chunk.candidates:
                    for candidate in chunk.candidates:
                        # 👇 增加判断：确保 content 和 parts 都存在
                        if candidate.content and candidate.content.parts: 
                            for part in candidate.content.parts:
                                if part.inline_data:
                                    img_bytes = part.inline_data.data
                                    img_mime = part.inline_data.mime_type
                                    generated_images.append((img_bytes, img_mime))
                                    st.image(img_bytes, caption="✨ 生成预览", width=400)

            # 最终刷新文本
            if full_response_text:
                message_placeholder.markdown(full_response_text)
            else:
                full_response_text = "⚠️ 抱歉，AI 拒绝了回答或未返回有效文本（可能触发了安全审查）。"
                message_placeholder.markdown(full_response_text)

        except Exception as e:
            st.error(f"API 请求错误: {e}")
            full_response_text = f"错误: {str(e)}"

    # 保存助手回复到历史
    st.session_state.messages.append({
        "role": "assistant", 
        "content": full_response_text,
        "generated_images": generated_images
    })
    
    # === 清空文件上传列表 ===
    if "file_uploader" in st.session_state:
        del st.session_state["file_uploader"]
    st.rerun()
