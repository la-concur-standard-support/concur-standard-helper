import os
import streamlit as st
import pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.llms import OpenAI
from langchain.vectorstores import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
PINECONE_ENV     = "us-east-1-aws"
INDEX_NAME       = "concur-index"
NAMESPACE        = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot")

    # Pinecone 初期化
    pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)

    # VectorStoreを読み込み
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    docsearch = Pinecone(
        embeddings,
        index_name=INDEX_NAME,
        namespace=NAMESPACE
    )

    llm = OpenAI(temperature=0, openai_api_key=OPENAI_API_KEY)
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=docsearch.as_retriever(search_kwargs={"k":3}),
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

        # 参照ドキュメント情報を表示
        if "source_documents" in result:
            st.write("#### 参照したチャンク:")
            for doc in result["source_documents"]:
                st.write(f"- {doc.metadata}")

        # 会話履歴に追加
        st.session_state["history"].append((query, answer))

if __name__ == "__main__":
    main()
