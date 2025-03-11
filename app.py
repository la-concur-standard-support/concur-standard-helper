import os
import streamlit as st
from dotenv import load_dotenv
import pinecone  # ← v5系での利用

# langchain の各種拡張パッケージ
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.llms import OpenAI
from langchain.chains import ConversationalRetrievalChain

# .env からキーを読み込み（ローカルテスト用 / Streamlit Cloud 上は st.secrets が推奨）
load_dotenv()

# 環境変数
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")

# Pinecone で使うインデックス名と Namespace
INDEX_NAME = "concur-index"
NAMESPACE  = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot (Pinecone v5)")

    # 1. pinecone.init(...) を使う（v5 系）
    pinecone.init(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENVIRONMENT
    )

    # 2. 既存インデックスを参照
    #    すでに作成済みの "concur-index" を取得
    my_index = pinecone.Index(INDEX_NAME)

    # 3. Embeddings
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

    # 4. PineconeVectorStore
    docsearch = PineconeVectorStore(
        embedding=embeddings,
        index=my_index,
        namespace=NAMESPACE
    )

    # 5. LLM (OpenAI)
    llm = OpenAI(api_key=OPENAI_API_KEY, temperature=0)

    # 6. ConversationalRetrievalChain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )

    # 7. 会話履歴の管理
    if "history" not in st.session_state:
        st.session_state["history"] = []

    # 8. 質問入力
    query = st.text_input("質問を入力してください:")

    # 9. 質問があれば Pinecone 検索 & LLM 回答
    if query:
        result = qa_chain({
            "question": query,
            "chat_history": st.session_state["history"]
        })
        answer = result["answer"]
        st.write("### 回答")
        st.write(answer)

        # 参照したチャンクのメタデータを表示
        if "source_documents" in result:
            st.write("#### 参照したチャンク:")
            for doc in result["source_documents"]:
                st.write(f"- {doc.metadata}")

        st.session_state["history"].append((query, answer))

if __name__ == "__main__":
    main()
