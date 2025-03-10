import os
from dotenv import load_dotenv
load_dotenv()  # これで .env 内のキーが os.environ に取り込まれる

import streamlit as st
from pinecone import Pinecone as PineconeClient, ServerlessSpec
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.llms import OpenAI
from langchain_community.vectorstores import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
# Pineconeの環境は "us-east-1", "us-west-2" など。
# 新しいSDKでは project_name や region を ServerlessSpec で指定する方法を推奨
PINECONE_ENV     = "us-east-1"  # 例: "us-east-1"
INDEX_NAME       = "concur-index"
NAMESPACE        = "demo-html"

def main():
    st.title("Concur Helper - RAG Chatbot")

    # 1. Pinecone クライアントを作成（init() は使わず）
    pc = PineconeClient(api_key=PINECONE_API_KEY)
    
    # （オプション）region を指定
    # 既存のIndexへアクセスするだけなら configure_serverless は必須ではありませんが、
    # "us-east-1-aws" 等を使うなら下記のように指定可能
    pc.configure_serverless(
        cloud="aws",
        region=PINECONE_ENV  # 例: "us-east-1"
    )

    # 2. Embeddings
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

    # 3. VectorStore（Pinecone）をロード
    docsearch = Pinecone(
        embeddings,
        pinecone_client=pc,      # pineconeクライアントを指定
        index_name=INDEX_NAME,
        namespace=NAMESPACE
    )

    # 4. LLM & Chain
    llm = OpenAI(
        temperature=0,
        openai_api_key=OPENAI_API_KEY
    )
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )

    # 5. 会話履歴を保持
    if "history" not in st.session_state:
        st.session_state["history"] = []

    # 6. ユーザー入力
    query = st.text_input("質問を入力してください:")

    if query:
        # Pinecone検索→LLM回答
        result = qa_chain({
            "question": query,
            "chat_history": st.session_state["history"]
        })
        answer = result["answer"]

        st.write("### 回答")
        st.write(answer)

        # 参照したドキュメントを表示
        if "source_documents" in result:
            st.write("#### 参照したチャンク:")
            for doc in result["source_documents"]:
                st.write(f"- {doc.metadata}")

        # 会話履歴に追加
        st.session_state["history"].append((query, answer))

if __name__ == "__main__":
    main()
