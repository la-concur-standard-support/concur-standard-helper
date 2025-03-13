import os
import streamlit as st
from dotenv import load_dotenv

# Pinecone v6 新方式
from pinecone import Pinecone

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

    # 1. Pineconeクラスのインスタンス
    pc = Pinecone(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENVIRONMENT
    )

    # 2. インデックスを取得
    my_index = pc.Index(INDEX_NAME)

    # 3. Embeddings
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

    # 4. VectorStore
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

        # --- 回答を表示 ---
        st.write("### 回答")
        st.write(answer)

        # --- ソースドキュメントのメタデータ表示 ---
        if "source_documents" in result:
            st.write("### 参照した設定ガイド:")

            for doc in result["source_documents"]:
                meta = doc.metadata
                # 表示したい項目だけ取り出す
                doc_name       = meta.get("DocName", "")
                guide_name_jp  = meta.get("GuideNameJp", "")
                section_title1 = meta.get("SectionTitle1", "")
                section_title2 = meta.get("SectionTitle2", "")
                full_link      = meta.get("FullLink", "")

                # メタデータが無いチャンクはスキップ
                if not doc_name and not full_link:
                    continue

                # 見出し表示
                st.markdown(f"- **DocName**: {doc_name}")
                st.markdown(f"  **GuideNameJp**: {guide_name_jp}")
                st.markdown(f"  **SectionTitle1**: {section_title1}")
                st.markdown(f"  **SectionTitle2**: {section_title2}")
                st.markdown(f"  **FullLink**: {full_link}\n")

        # 9. 会話履歴を更新
        st.session_state["history"].append((query, answer))

if __name__ == "__main__":
    main()
