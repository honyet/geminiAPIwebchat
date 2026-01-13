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

st.title("✨ Gemini 全能助手 (Pro & Nano)")

# --- 从 URL 获取参数 ---
url_key = st.query_params.get("key", "")

# 2. 侧边栏：配置与上传
with st.sidebar:
    st.header("⚙️ 配置")

    # API Key 输入
    api_key = st.text_input(
        "Google Gemini API Key",
        value=url_key,
        type="password",
        help="在 URL 后加 ?key=YOUR_KEY 可自动填入"
    )
    st.markdown("[获取 API Key](https://aistudio.google.com/app/apikey)")

    st.divider()

    # 模型选择 (映射用户想要的名称到真实 Model ID)
    # 注意：Gemini 3 尚未发布，这里映射到最新的 Gemini 2.0 Pro Experimental
    model_map = {
        "Gemini 3 Pro (2.0 Pro Exp)": "gemini-2.0-pro-exp-02-05",
        "Nano Banana (2.0 Flash)": "gemini-2.0-flash",
    }

    selected_label = st.selectbox(
        "选择模型", 
        list(model_map.keys()),
        index=0
    )
    model_id = model_map[selected_label]

    st.divider()

    # 文件上传组件
    st.header("📤 上传文件/图片")
    uploaded_file = st.file_uploader(
        "支持图片、PDF、文本等", 
        type=['png', 'jpg', 'jpeg', 'webp', 'pdf', 'txt', 'csv'],
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

# 5. 初始化客户端
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"客户端初始化失败: {e}")
    st.stop()

# --- 辅助函数：显示图片 ---
def display_content(content_data, mime_type):
    if mime_type.startswith("image/"):
        st.image(content_data, width=300)
    elif mime_type == "application/pdf":
        st.caption("📄 [已上传 PDF 文件]")
    else:
        st.caption(f"📎 [已上传文件: {mime_type}]")

# 6. 显示历史聊天记录
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # 如果该条消息包含文件数据，先显示文件
        if "file_data" in message and message["file_data"]:
            display_content(message["file_data"], message["mime_type"])

        # 显示文本内容
        st.markdown(message["content"])

# 7. 处理用户输入
if prompt := st.chat_input("输入你的问题..."):

    # 准备当前消息的数据结构
    current_msg = {
        "role": "user",
        "content": prompt,
        "file_data": None,
        "mime_type": None
    }

    # 处理上传的文件
    user_parts = [types.Part.from_text(text=prompt)]

    if uploaded_file:
        bytes_data = uploaded_file.getvalue()
        mime_type = uploaded_file.type

        # 保存到 session state 以便回显
        current_msg["file_data"] = bytes_data
        current_msg["mime_type"] = mime_type

        # 构建 API 请求部分 (将文件转为 Bytes Part)
        file_part = types.Part.from_bytes(data=bytes_data, mime_type=mime_type)
        user_parts.append(file_part)

        # 提示：Streamlit 的上传器会在交互后重置，这里我们处理完就无需手动清除，
        # 但用户下次输入如果不重新上传，就是纯文本对话。

    # 显示用户消息 (UI)
    with st.chat_message("user"):
        if current_msg["file_data"]:
            display_content(current_msg["file_data"], current_msg["mime_type"])
        st.markdown(prompt)

    # 保存用户消息到历史
    st.session_state.messages.append(current_msg)

    # 生成 AI 回复
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            # --- 构建历史记录 (转换为 Google SDK 格式) ---
            history_contents = []

            # 遍历历史记录（排除刚才最新的一条，因为那是我们要发送的）
            for msg in st.session_state.messages[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                parts = []

                # 如果历史消息里有文本
                if msg["content"]:
                    parts.append(types.Part.from_text(text=msg["content"]))

                # 如果历史消息里有文件
                if "file_data" in msg and msg["file_data"]:
                    parts.append(types.Part.from_bytes(
                        data=msg["file_data"], 
                        mime_type=msg["mime_type"]
                    ))

                history_contents.append(types.Content(role=role, parts=parts))

            # --- 创建聊天会话 ---
            chat = client.chats.create(
                model=model_id,
                history=history_contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )

            # --- 发送当前消息 (包含文本和可能的图片) ---
            # 注意：send_message_stream 接受 str 或 list[Part]
            response = chat.send_message_stream(user_parts)

            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")

            message_placeholder.markdown(full_response)

        except Exception as e:
            st.error(f"API 请求错误: {e}")
            full_response = "抱歉，生成回答时出现了错误。请检查 API Key、网络或模型是否支持该文件类型。"

    # 保存助手回复
    st.session_state.messages.append({
        "role": "assistant", 
        "content": full_response
    })
