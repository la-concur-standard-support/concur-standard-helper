import os
import streamlit as st
from dotenv import load_dotenv

# Pinecone v6 新方式
from pinecone import Pinecone, ServerlessSpec

# langchain-pinecone と langchain-openai の利用
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.llms import OpenAI
from langchain.chains import ConversationalRetrievalChain

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")

INDEX_NAME = "concur-index"
NAMESPACE  = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot")

    # 1. 新しい Pinecone クラスのインスタンスを作る (init() の代わり)
    pc = Pinecone(
        api_key=PINECONE_API_KEY,
        # environment / project_name が必要なら指定
        environment=PINECONE_ENVIRONMENT
        # project_name="xxx" などがあれば追記
    )

    # 2. インデックスを取得
    # すでに作成済みなので create_index() は不要
    my_index = pc.Index(INDEX_NAME)

    # 3. Embeddings (langchain-openai)
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

    # 4. PineconeVectorStore で VectorStore を生成 (langchain-pinecone)
    docsearch = PineconeVectorStore(
        embedding=embeddings,
        index=my_index,
        namespace=NAMESPACE
    )

    # 5. LLM (langchain_community.llms)
    llm = OpenAI(api_key=OPENAI_API_KEY, temperature=0)

    # 6. ConversationalRetrievalChain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )

    # 7. 会話履歴管理
    if "history" not in st.session_state:
        st.session_state["history"] = []

    # 8. ユーザー入力
    query = st.text_input("質問を入力してください:")

    if query:
        result = qa_chain({
            "question": query,
            "chat_history": st.session_state["history"]
        })
        answer = result["answer"]
        st.write("### 回答")
        st.write(answer)

        if "source_documents" in result:
            st.write("#### 参照したチャンク:")
            for doc in result["source_documents"]:
                st.write(f"- {doc.metadata}")

        st.session_state["history"].append((query, answer))

if __name__ == "__main__":
    main()
