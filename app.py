import streamlit as st

# Pinecone v6 新方式
from pinecone import Pinecone, ServerlessSpec

# langchain-pinecone と langchain-openai の利用
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.llms import OpenAI
from langchain.chains import ConversationalRetrievalChain

# ストリームリットの Secrets からキーを取得
def get_openai_api_key():
    return st.secrets["OPENAI_API_KEY"]  # Streamlit Cloud のSecretsで定義

def get_pinecone_api_key():
    return st.secrets["PINECONE_API_KEY"]

def get_pinecone_environment():
    return st.secrets.get("PINECONE_ENVIRONMENT", "us-east-1-aws")

INDEX_NAME = "concur-index"
NAMESPACE  = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot")

    # 1. Pineconeクラスを使った初期化 (init() は使わない)
    pc = Pinecone(
        api_key=get_pinecone_api_key(),
        environment=get_pinecone_environment()
    )

    # 2. 既存インデックスを参照 (作成済みなので create_index は不要)
    my_index = pc.Index(INDEX_NAME)

    # 3. Embeddings (langchain-openai)
    embeddings = OpenAIEmbeddings(api_key=get_openai_api_key())

    # 4. PineconeVectorStore (langchain-pinecone)
    docsearch = PineconeVectorStore(
        embedding=embeddings,
        index=my_index,
        namespace=NAMESPACE
    )

    # 5. LLM (langchain_community.llms)
    llm = OpenAI(api_key=get_openai_api_key(), temperature=0)

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
