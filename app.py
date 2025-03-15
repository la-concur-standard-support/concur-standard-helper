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
以下のドキュメント情報(検索結果)とユーザーの質問を踏まえて、
ChatGPT-4モデルとして詳しくかつ分かりやすい回答を行ってください。

【要件】
- 回答は十分な説明を含み、原理や理由も分かるように解説してください。
- ユーザーが疑問を解消できるよう、段階的な説明や背景情報も交えてください。
- ただしドキュメントの原文を不要に繰り返すのは避け、ポイントのみを的確に述べてください。
- “Context:” などの文言は出さず、テキストの重複や冗長表現を可能な限り減らしてください。
- 答えが分からない場合は「わかりません」と述べてください。

ドキュメント情報:
{context}

ユーザーの質問: {question}

上記を踏まえ、ChatGPT-4モデルとして、詳しくかつ要点を押さえた回答をお願いします:
"""
custom_prompt = PromptTemplate(
    template=CUSTOM_PROMPT_TEMPLATE,
    input_variables=["context", "question"]
)

def main():
    st.title("Concur Helper ‐ 開発者支援ボット")

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
        text_key="chunk_text"
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

    # ★ 会話履歴(Chain用)
    #    ConversationalRetrievalChainは (human_message, ai_message) のタプルのリストを期待
    if "history" not in st.session_state:
        st.session_state["history"] = []

    # ★ 表示用のチャットメッセージ履歴
    #    辞書 { "user": 質問, "assistant": 回答, "sources": 参照情報 } を持つリスト
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    # 7. ユーザーの質問入力
    query = st.text_input("質問を入力してください:")

    if st.button("送信"):
        if query.strip():
            # 7-1) QAチェーンの実行
            result = qa_chain({
                "question": query,
                "chat_history": st.session_state["history"]  # 前回までの会話を渡す
            })
            answer = result["answer"]

            # 7-2) ソースドキュメントのメタデータをリスト化
            source_info = []
            if "source_documents" in result:
                for doc in result["source_documents"]:
                    source_info.append(doc.metadata)  # ここでは metadata のみ保存

            # 7-3) 会話履歴を更新 (Chain用: (ユーザー発話, AI回答) のタプル)
            st.session_state["history"].append((query, answer))

            # 7-4) 表示用のチャットメッセージ履歴を追加
            st.session_state["chat_messages"].append({
                "user": query,
                "assistant": answer,
                "sources": source_info
            })

    # 8. これまでの会話をチャット形式で表示
    #    (Streamlit 1.23+ の st.chat_message を使用)
    for chat_item in st.session_state["chat_messages"]:
        user_q = chat_item["user"]
        ai_a   = chat_item["assistant"]
        srcs   = chat_item["sources"]

        # ユーザーのメッセージ
        with st.chat_message("user"):
            st.write(user_q)

        # アシスタントのメッセージ
        with st.chat_message("assistant"):
            st.write(ai_a)

            # 参照したドキュメント情報を表示 (お好みで省略可)
            if srcs:
                st.write("##### 参照した設定ガイド:")
                for meta in srcs:
                    doc_name       = meta.get("DocName", "")
                    guide_name_jp  = meta.get("GuideNameJp", "")
                    sec1           = meta.get("SectionTitle1", "")
                    sec2           = meta.get("SectionTitle2", "")
                    full_link      = meta.get("FullLink", "")

                    st.markdown(f"- **DocName**: {doc_name}")
                    st.markdown(f"  **GuideNameJp**: {guide_name_jp}")
                    st.markdown(f"  **SectionTitle1**: {sec1}")
                    st.markdown(f"  **SectionTitle2**: {sec2}")
                    st.markdown(f"  **FullLink**: {full_link}\n")

if __name__ == "__main__":
    main()
