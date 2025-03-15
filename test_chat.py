import streamlit as st

st.title("Minimal Chat Test")

# 1) 履歴
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 2) 過去のやりとりを表示
for role, text in st.session_state["messages"]:
    with st.chat_message(role):
        st.write(text)

# 3) 入力
user_input = st.chat_input("何か質問はありますか？")

if user_input:
    # 履歴にユーザー発話
    st.session_state["messages"].append(("user", user_input))
    # ダミーAI応答
    st.session_state["messages"].append(("assistant", "これはダミー回答です。"))
