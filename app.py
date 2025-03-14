import os
import streamlit as st
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

# --- カスタムプロンプト (不要なら省略OK) ---
CUSTOM_PROMPT_TEMPLATE = """あなたはConcurドキュメントの専門家です。
以下のドキュメント情報とユーザーの質問を踏まえ、GPT-4モデルとして、簡潔で正確な回答をしてください。
不要な繰り返しを避け、要点のみを示してください。答えが不明なら「わかりません」と述べてください。

ドキュメント情報:
{context}

ユーザーの質問: {question}

最適な回答:
"""
custom_prompt = PromptTemplate(
    template=CUSTOM_PROMPT_TEMPLATE,
    input_variables=["context", "question"]
)


def main():
    st.title("Concur Helper - RAG Chatbot (GPT-4)")

    # 1. Pinecone インスタンス
    pc = Pinecone(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENVIRONMENT
    )

    # 2. インデックスを取得
    my_index = pc.Index(INDEX_NAME)

    # 3. Embeddings
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

    # 4. VectorStore (★ text_key="chunk_text" を指定 ★)
    docsearch = PineconeVectorStore(
        embedding=embeddings,
        index=my_index,
        namespace=NAMESPACE,
        text_key="chunk_text"   # これで doc.page_content = chunk_text となり、他は metadata に入る
    )

    # 5. ChatGPT-4 モデル
    chat_llm = ChatOpenAI(
        openai_api_key=OPENAI_API_KEY,
        model_name="gpt-4",
        temperature=0
    )

    # 6. ConversationalRetrievalChain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=chat_llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True,
        combine_docs_chain_kwargs={
            "prompt": custom_prompt
        }
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
                doc_name       = meta.get("DocName", "")
                guide_name_jp  = meta.get("GuideNameJp", "")
                section_title1 = meta.get("SectionTitle1", "")
                section_title2 = meta.get("SectionTitle2", "")
                full_link      = meta.get("FullLink", "")

                if not doc_name and not full_link:
                    continue

                st.markdown(f"- **DocName**: {doc_name}")
                st.markdown(f"  **GuideNameJp**: {guide_name_jp}")
                st.markdown(f"  **SectionTitle1**: {section_title1}")
                st.markdown(f"  **SectionTitle2**: {section_title2}")
                st.markdown(f"  **FullLink**: {full_link}\n")

        # 9. 会話履歴を更新
        st.session_state["history"].append((query, answer))


if __name__ == "__main__":
    main()
