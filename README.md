# Concur Helper (RAG Chatbot)

SAP Concur の技術文書を Pinecone と OpenAI を使って検索し、チャット形式で回答するボットのプロジェクトです。

## セットアップ

1. Python 3.9+ を用意
2. `pip install -r requirements.txt`
3. `.env` に以下の環境変数を設定: OPENAI_API_KEY=<YourOpenAIKey> PINECONE_API_KEY=<YourPineconeKey>
4. `python ingest.py` で技術文書のチャンクを Pinecone にアップロード
5. `streamlit run app.py` でアプリを起動

## ライセンス

- プロジェクトのライセンスや注意事項を記載
