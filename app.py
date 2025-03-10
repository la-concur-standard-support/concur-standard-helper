import os
import streamlit as st
# .envを読み込む
from dotenv import load_dotenv
load_dotenv()

# 新しいPineconeパッケージ
from pinecone import Pinecone as PineconeClient

# LangChain 新方式: communityパッケージ
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain_community.llms import OpenAI
from langchain_community.vectorstores import Pinecone

# ここで .env に書かれた環境変数を読み出す
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")
INDEX_NAME = "concur-index"
NAMESPACE = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot")

    # Pinecone の新方式: PineconeClient() でインスタンス化
    # environment に “us-east-1-aws” などを指定
    # project_name が必要な場合は `project_name=...` を付けてください
    pc = PineconeClient(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENVIRONMENT
        # project_name="..."
    )

    # Embeddings
    openai_key = os.getenv("OPENAI_API_KEY", "")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_key)

    # VectorStore (Pinecone)
    # pinecone_client=pc を渡す
    docsearch = Pinecone(
        embeddings,
        pinecone_client=pc,
        index_name=INDEX_NAME,
        namespace=NAMESPACE
    )

    # LLM (OpenAI via langchain_community.llms)
    llm = OpenAI(
        openai_api_key=openai_key,
        temperature=0
    )

    # ConversationalRetrievalChain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )

    # 会話履歴を保持
    if "history" not in st.session_state:
        st.session_state["history"] = []

    query = st.text_input("質問を入力してください:")

    if query:
        result = qa_chain({
            "question": query,
            "chat_history": st.session_state["history"]
        })
        answer = result["answer"]

        st.write("### 回答")
        st.write(answer)

        # 参照されたメタデータの表示
        if "source_documents" in result:
            st.write("#### 参照したチャンク:")
            for doc in result["source_documents"]:
                st.write(f"- {doc.metadata}")

        # 履歴を更新
        st.session_state["history"].append((query, answer))

if __name__ == "__main__":
    main()
