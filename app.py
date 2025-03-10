import os
import streamlit as st
from dotenv import load_dotenv

# 新しい Pinecone パッケージ (v5系 か 6系) ※ 5系の場合 “import pinecone” だけでOK
import pinecone

# langchain-openai / langchain-pinecone / langchain_community
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.llms import OpenAI
from langchain.chains import ConversationalRetrievalChain

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "")
INDEX_NAME = "concur-index"
NAMESPACE  = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot")

    # 1. Pineconeクライアントを作成
    pinecone.init(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENVIRONMENT
    )

    # 2. 既存のインデックスを取得
    #   pinecone.Index(...) は v5系 もしくは v6系 で違う可能性がありますが、
    #   基本的に “INDEX_NAME” を渡してインデックスを使えるはず
    #   すでに作成済みなら create_index などは不要
    my_index = pinecone.Index(INDEX_NAME)

    # 3. Embeddings (OpenAI)
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

    # 4. PineconeVectorStore で VectorStore を生成
    docsearch = PineconeVectorStore(
        embedding=embeddings,
        index=my_index,
        namespace=NAMESPACE
    )

    # 5. LLM
    llm = OpenAI(api_key=OPENAI_API_KEY, temperature=0)

    # 6. ConversationalRetrievalChain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )

    if "history" not in st.session_state:
        st.session_state["history"] = []

    query = st.text_input("質問を入力してください:")

    if query:
        result = qa_chain({"question": query, "chat_history": st.session_state["history"]})
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
