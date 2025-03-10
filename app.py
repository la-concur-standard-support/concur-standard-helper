import os
import streamlit as st
from dotenv import load_dotenv

# langchain-openai / langchain-pinecone / langchain_community
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import Pinecone
from langchain_community.llms import OpenAI
from langchain.chains import ConversationalRetrievalChain

# .env から環境変数を読み込み
load_dotenv()

# .env に書いてあるキーを取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")

INDEX_NAME = "concur-index"
NAMESPACE  = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot")

    # Embeddings (langchain-openai)
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

    # VectorStore (langchain-pinecone)
    # Pinecone(...) に直接 APIキーや環境を指定する
    docsearch = Pinecone(
        embedding=embeddings,
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENVIRONMENT,
        index_name=INDEX_NAME,
        namespace=NAMESPACE
    )

    # LLM (langchain_community.llms)
    llm = OpenAI(api_key=OPENAI_API_KEY, temperature=0)

    # ConversationalRetrievalChain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )

    # 会話履歴の管理
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

        if "source_documents" in result:
            st.write("#### 参照したチャンク:")
            for doc in result["source_documents"]:
                st.write(f"- {doc.metadata}")

        st.session_state["history"].append((query, answer))

if __name__ == "__main__":
    main()
