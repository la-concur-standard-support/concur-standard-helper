import streamlit as st

st.title("Minimal Chat Test")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 表示
for role, text in st.session_state["messages"]:
    with st.chat_message(role):
        st.write(text)

# 入力
user_input = st.chat_input("何か質問はありますか？")
if user_input:
    st.session_state["messages"].append(("user", user_input))
    st.session_state["messages"].append(("assistant", "これはダミー回答です。"))
