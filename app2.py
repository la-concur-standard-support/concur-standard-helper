import os
import json
import streamlit as st
from dotenv import load_dotenv

# Pinecone v6 (旧バージョン or pinecone-client 2系など、環境に合わせて)
from pinecone import Pinecone

# langchain
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate

from datetime import datetime
from io import StringIO

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")

INDEX_NAME = "concur-index"
NAMESPACE  = "demo-html"

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

    # セッション初期化
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []
    if "history" not in st.session_state:
        st.session_state["history"] = []

    # ▼ Pinecone, VectorStore
    pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
    my_index = pc.Index(INDEX_NAME)
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
    docsearch = PineconeVectorStore(
        embedding=embeddings,
        index=my_index,
        namespace=NAMESPACE,
        text_key="chunk_text"
    )

    # ▼ ChatGPTモデル & Chain
    chat_llm = ChatOpenAI(
        openai_api_key=OPENAI_API_KEY,
        model_name="gpt-4",
        temperature=0
    )
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=chat_llm,
        retriever=docsearch.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True,
        combine_docs_chain_kwargs={
            "prompt": custom_prompt
        }
    )

    # -----------------------------
    # 1) 履歴アップロード (復元)
    # -----------------------------
    st.sidebar.header("会話履歴の管理")
    uploaded_file = st.sidebar.file_uploader("保存していた会話ファイルを選択 (.json)", type="json")
    if uploaded_file is not None:
        # JSONとして読み込んで復元
        uploaded_content = uploaded_file.read()
        try:
            loaded_json = json.loads(uploaded_content)
            # "chat_messages" と "history" を復元 (無ければ空に)
            st.session_state["chat_messages"] = loaded_json.get("chat_messages", [])
            st.session_state["history"] = loaded_json.get("history", [])

            # === ここで "history" をタプル化する処理を挟む ===
            new_history = []
            for item in st.session_state["history"]:
                # もしリスト形式で [user_text, ai_text] を持っている場合 → タプルへ
                if isinstance(item, list) and len(item) == 2:
                    new_history.append(tuple(item))
                else:
                    # すでにタプルか、フォーマット不明の場合はそのまま
                    new_history.append(item)

            st.session_state["history"] = new_history

            st.success("以前の会話履歴を復元しました！")
        except Exception as e:
            st.error(f"アップロードに失敗しました: {e}")

    # -----------------------------
    # 2) 履歴ダウンロードボタン
    # -----------------------------
    def download_chat_history():
        # まとめて辞書化
        data_to_save = {
            "chat_messages": st.session_state["chat_messages"],
            "history": st.session_state["history"]
        }
        return json.dumps(data_to_save, ensure_ascii=False, indent=2)

    if st.sidebar.button("現在の会話を保存"):
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"chat_history_{now_str}.json"
        json_data = download_chat_history()
        st.sidebar.download_button(
            label="ダウンロード (JSON)",
            data=json_data,
            file_name=file_name,
            mime="application/json"
        )

    # -----------------------------
    # メイン画面: チャットUI
    # -----------------------------
    chat_placeholder = st.empty()    # 会話履歴表示領域
    with st.container():             # 入力欄
        user_input = st.text_input("新しい質問を入力してください", "")
        if st.button("送信"):
            if user_input.strip():
                # LangChain呼び出し
                with st.spinner("回答を生成中..."):
                    result = qa_chain({
                        "question": user_input,
                        "chat_history": st.session_state["history"]
                    })
                answer = result["answer"]

                # ソース情報
                source_info = []
                if "source_documents" in result:
                    for doc in result["source_documents"]:
                        source_info.append(doc.metadata)

                # ConversationalRetrievalChainの履歴に追加
                # ここはタプル (ユーザ発話, AI回答) で管理
                st.session_state["history"].append((user_input, answer))

                # 表示用の履歴に追加（辞書形式）
                st.session_state["chat_messages"].append({
                    "user": user_input,
                    "assistant": answer,
                    "sources": source_info
                })

    # -----------------------------
    # 会話履歴を上部に表示
    # -----------------------------
    with chat_placeholder.container():
        st.subheader("=== 会話履歴 ===")
        for chat_item in st.session_state["chat_messages"]:
            user_q = chat_item["user"]
            ai_a   = chat_item["assistant"]
            srcs   = chat_item["sources"]

            # ユーザー発話
            with st.chat_message("user"):
                st.write(user_q)

            # アシスタント発話
            with st.chat_message("assistant"):
                st.write(ai_a)
                if srcs:
                    st.write("##### 参照した設定ガイド:")
                    for meta in srcs:
                        doc_name = meta.get("DocName", "")
                        guide_jp = meta.get("GuideNameJp", "")
                        sec1     = meta.get("SectionTitle1", "")
                        sec2     = meta.get("SectionTitle2", "")
                        link     = meta.get("FullLink", "")

                        st.markdown(f"- **DocName**: {doc_name}")
                        st.markdown(f"  **GuideNameJp**: {guide_jp}")
                        st.markdown(f"  **SectionTitle1**: {sec1}")
                        st.markdown(f"  **SectionTitle2**: {sec2}")
                        st.markdown(f"  **FullLink**: {link}")

if __name__ == "__main__":
    main()
