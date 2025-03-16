import os
import streamlit as st

# ▼ 追加
import streamlit_authenticator as stauth

from dotenv import load_dotenv
# Pinecone v6
from pinecone import Pinecone
# langchain
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")

INDEX_NAME = "concur-index"
NAMESPACE  = "demo-html"

CUSTOM_PROMPT_TEMPLATE = """あなたはConcurドキュメントの専門家です。
以下のドキュメント情報(検索結果)とユーザーの質問を踏まえて、
ChatGPT-4モデルとして詳しくかつ分かりやすい回答を行ってください。

【要件】
- 回答は十分な説明を含み、原理や理由も分かるように解説してください。
- ユーザーが疑問を解消できるよう、段階的な説明や背景情報も交えてください。
- ただしドキュメントの原文を不要に繰り返すのは避け、ポイントのみを的確に述べてください。
- “Context:” などの文言は出さず、テキストの重複や冗長表現を可能な限り減らしてください。
- 答えが分からない場合は「わかりません」と述べてください。

ドキュメント情報:
{context}

ユーザーの質問: {question}

上記を踏まえ、ChatGPT-4モデルとして、詳しくかつ要点を押さえた回答をお願いします:
"""
custom_prompt = PromptTemplate(
    template=CUSTOM_PROMPT_TEMPLATE,
    input_variables=["context", "question"]
)

# ▼ 例: 認証用のデータ (開発・テスト用に直書き)
credentials = {
    "usernames": {
        "demo_user": {
            "email": "[email protected]",
            "name": "Demo User",
            "password": "$2b$12$N2V0...（生成したハッシュを貼る）"
        },
        "another_user": {
            "email": "[email protected]",
            "name": "Another User",
            "password": "$2b$12$8GSe...（生成したハッシュを貼る）"
        }
    }
}

# ▼ 例: 認証オブジェクトを作成
authenticator = stauth.Authenticate(
    credentials,
    "my_cookie_name",  # Cookieの名前（任意）
    "my_signature_key",  # Cookie署名用の秘密鍵（任意の文字列）
    cookie_expiry_days=30
)

def main():
    # ▼ ログイン画面を表示
    name, authentication_status, username = authenticator.login("Login", "main")

    if authentication_status is False:
        st.error("ユーザ名またはパスワードが間違っています")

    if authentication_status is None:
        st.warning("ユーザ名とパスワードを入力してください")

    # --------------------------------------------
    # 認証が成功したユーザーだけチャット画面を表示
    # --------------------------------------------
    if authentication_status:
        st.title("Concur Helper ‐ 開発者支援ボット")
        st.write(f"ようこそ {name} さん！")

        # ▼ 以下、あなたの元々のコードを配置
        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = []
        if "history" not in st.session_state:
            st.session_state["history"] = []

        pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
        my_index = pc.Index(INDEX_NAME)
        embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
        docsearch = PineconeVectorStore(
            embedding=embeddings,
            index=my_index,
            namespace=NAMESPACE,
            text_key="chunk_text"
        )

        chat_llm = ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model_name="gpt-4",
            temperature=0
        )
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=chat_llm,
            retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True,
            combine_docs_chain_kwargs={
                "prompt": custom_prompt
            }
        )

        chat_placeholder = st.empty()
        with st.container():
            user_input = st.text_input("新しい質問を入力してください", "")
            if st.button("送信"):
                if user_input.strip():
                    with st.spinner("回答を生成中..."):
                        result = qa_chain({
                            "question": user_input,
                            "chat_history": st.session_state["history"]
                        })
                    answer = result["answer"]

                    source_info = []
                    if "source_documents" in result:
                        for doc in result["source_documents"]:
                            source_info.append(doc.metadata)

                    st.session_state["history"].append((user_input, answer))

                    st.session_state["chat_messages"].append({
                        "user": user_input,
                        "assistant": answer,
                        "sources": source_info
                    })

        with chat_placeholder.container():
            st.subheader("=== 会話履歴 ===")
            for chat_item in st.session_state["chat_messages"]:
                user_q = chat_item["user"]
                ai_a   = chat_item["assistant"]
                srcs   = chat_item["sources"]

                with st.chat_message("user"):
                    st.write(user_q)

                with st.chat_message("assistant"):
                    st.write(ai_a)
                    if srcs:
                        st.write("##### 参照した設定ガイド:")
                        for meta in srcs:
                            doc_name = meta.get("DocName", "")
                            guide_jp = meta.get("GuideNameJp", "")
                            sec1     = meta.get("SectionTitle1", "")
                            sec2     = meta.get("SectionTitle2", "")
                            link     = meta.get("FullLink", "")
                            st.markdown(f"- **DocName**: {doc_name}")
                            st.markdown(f"  **GuideNameJp**: {guide_jp}")
                            st.markdown(f"  **SectionTitle1**: {sec1}")
                            st.markdown(f"  **SectionTitle2**: {sec2}")
                            st.markdown(f"  **FullLink**: {link}")

if __name__ == "__main__":
    main()

