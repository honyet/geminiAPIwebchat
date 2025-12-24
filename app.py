import streamlit as st
from google import genai
from google.genai import types

# 1. 页面配置
st.set_page_config(
    page_title="Gemini Chat (新版SDK)",
    page_icon="✨",
    layout="centered"
)

st.title("✨ Gemini API 对话助手 (v3)")

# --- 修改部分：从 URL 获取参数 ---
# 尝试获取 URL 中名为 'key' 的参数
url_key = st.query_params.get("key", "")

# 2. 侧边栏：配置 API Key
with st.sidebar:
    st.header("配置")
    # 如果 URL 里有 key，则默认填充到输入框中
    api_key = st.text_input(
        "Google Gemini API Key", 
        value=url_key, 
        type="password",
        help="你可以通过 URL ?key=你的API密钥 来自动填充"
    )
    
    st.markdown("[获取 Gemini API Key](https://aistudio.google.com/app/apikey)")
    
    # 模型选择
    model_id = st.selectbox(
        "选择模型", 
        ["gemini-3-pro-image-preview", "gemini-3-flash-preview", "gemini-3-pro-preview"],
        index=1
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

# 5. 初始化客户端 (新版 SDK 方式)
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"客户端初始化失败: {e}")
    st.stop()

# 6. 显示历史聊天记录
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 7. 处理用户输入
if prompt := st.chat_input("输入你的问题..."):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 生成 AI 回复
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # --- 核心变化：构建历史记录 ---
            # 新版 SDK 需要将 Streamlit 的 history 转换为它能理解的格式
            history_contents = []
            for msg in st.session_state.messages[:-1]: # 排除最新的一条，下面单独发
                role = "user" if msg["role"] == "user" else "model"
                history_contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg["content"])]
                    )
                )

            # --- 核心变化：创建聊天会话 ---
            chat = client.chats.create(
                model=model_id,
                history=history_contents,
                config=types.GenerateContentConfig(
                    temperature=0.7, # 可选：控制创造性
                )
            )

            # --- 核心变化：发送消息并流式接收 ---
            response = chat.send_message_stream(prompt)
            
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            # 捕获并显示具体的错误信息，方便调试
            st.error(f"API 请求错误: {e}")
            full_response = "抱歉，生成回答时出现了错误，请检查 API Key 或网络连接。"
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})
