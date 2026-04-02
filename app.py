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

st.title("✨ GeminiAPI v4 全能助手 (Pro & Nano)")

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
        help="你可以通过 URL ?key=你的API密钥 来自动填充中转站(jeniya.cn)提供的 API Key"
    )
    st.markdown("[获取 API Key](https://aistudio.google.com/app/apikey)")

    st.divider()

    # 模型选择
    model_map = {
        "Gemini 3 Pro": "gemini-3-pro-preview",
        "Gemini-3 flash": "gemini-3-flash-preview",
        "Nano Banana (标准版)": "gemini-2.5-flash-image",
        "Nano Banana Pro (增强版)": "gemini-3-pro-image-preview",
    }

    selected_label = st.selectbox(
        "选择模型", 
        list(model_map.keys()),
        index=1
    )
    model_id = model_map[selected_label]
    
    # 提示用户当前模型是否支持画图
    if "Banana" in selected_label:
        st.caption("ℹ️ 当前模型支持图像生成与编辑")

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
    # 修改点：添加 http_options 来指定中转站地址
    client = genai.Client(
        api_key=api_key,
        http_options={
            "base_url": "https://api.jeniya.cn"  # 填入中转站提供的 API 基础地址
        }
    )
except Exception as e:
    st.error(f"客户端初始化失败: {e}")
    st.stop()

# --- 辅助函数：显示内容 (增强版) ---
def display_content(content_data, mime_type):
    if not content_data:
        return
    if mime_type and mime_type.startswith("image/"):
        st.image(content_data, width=400) # 适当放大图片宽度
    elif mime_type == "application/pdf":
        st.caption("📄 [PDF 文件]")
    else:
        st.caption(f"📎 [文件: {mime_type}]")

# 6. 显示历史聊天记录
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # 1. 显示用户上传的文件 (User message 里的 file_data)
        if message.get("file_data"):
             display_content(message["file_data"], message.get("mime_type"))
        
        # 2. 显示文本内容
        if message.get("content"):
            st.markdown(message["content"])
            
        # 3. 显示模型生成的图片 (Assistant message 里的 generated_images)
        # 修复点：这里用于回显历史记录中模型生成的图片
        if message.get("generated_images"):
            for img_data, img_mime in message["generated_images"]:
                st.image(img_data, caption="Generated Image", width=400)

# 7. 处理用户输入
if prompt := st.chat_input("输入你的问题... (例如: 画一只在太空冲浪的猫)"):

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

        # 构建 API 请求部分
        file_part = types.Part.from_bytes(data=bytes_data, mime_type=mime_type)
        user_parts.append(file_part)

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
        full_response_text = ""
        generated_images = [] # 临时列表，用于存储本次生成的图片

        try:
            # --- 构建历史记录 ---
            history_contents = []
            for msg in st.session_state.messages[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                parts = []
                
                # 文本
                if msg.get("content"):
                    parts.append(types.Part.from_text(text=msg["content"]))
                
                # 用户上传的文件
                if msg.get("file_data"):
                    parts.append(types.Part.from_bytes(
                        data=msg["file_data"], 
                        mime_type=msg["mime_type"]
                    ))
                
                # 暂时不将模型生成的图片放入 Context (目前上下文多模态输入主要支持用户侧)
                # 如果需要模型基于上次生成的图修改，需要复杂的处理逻辑，这里暂略
                
                if parts:
                    history_contents.append(types.Content(role=role, parts=parts))

            # --- 创建聊天会话 ---
            # 如果是纯画图模型，通常不建议用 history，但为了兼容性保留
            chat = client.chats.create(
                model=model_id,
                history=history_contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )

            # --- 发送请求 ---
            response = chat.send_message_stream(user_parts)

            # --- 核心修复：处理流式响应中的图片数据 ---
            for chunk in response:
                # 1. 处理文本
                if chunk.text:
                    full_response_text += chunk.text
                    message_placeholder.markdown(full_response_text + "▌")
                
                # 2. 处理非文本内容 (图片)
                # 检查 candidates 中的 parts 是否包含 inline_data
                if chunk.candidates:
                    for candidate in chunk.candidates:
                        for part in candidate.content.parts:
                            if part.inline_data:
                                # 获取图片二进制数据和类型
                                img_bytes = part.inline_data.data
                                img_mime = part.inline_data.mime_type
                                
                                # 存入列表
                                generated_images.append((img_bytes, img_mime))
                                
                                # 立即在界面显示
                                st.image(img_bytes, caption="✨ 生成预览", width=400)

            # 最终刷新文本（去掉光标）
            message_placeholder.markdown(full_response_text)

        except Exception as e:
            st.error(f"API 请求错误: {e}")
            full_response_text = f"错误: {str(e)}"

    # 保存助手回复到历史
    # 我们增加了一个 generated_images 字段来存储图片数据
    st.session_state.messages.append({
        "role": "assistant", 
        "content": full_response_text,
        "generated_images": generated_images # 保存生成的图片列表
    })
