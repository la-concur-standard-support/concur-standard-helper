import os
import pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone

# 1. 環境変数からキーを取得 (事前に .env や OSの環境変数でセット)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
PINECONE_ENV     = "us-east-1-aws"  # Pineconeダッシュボードで確認
INDEX_NAME       = "concur-index"
NAMESPACE        = "demo-html"

def main():
    # 2. Pinecone 初期化
    pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)

    # 3. テキストファイル読み込み (例: docs/sample.txt)
    with open("docs/sample.txt", "r", encoding="utf-8") as f:
        text = f.read()

    # 4. チャンク分割
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)

    # 5. Documentにまとめる (メタデータを付与)
    docs = []
    for i, chunk in enumerate(chunks):
        doc_meta = {"source": "sample.txt", "chunk_index": i}
        docs.append(Document(page_content=chunk, metadata=doc_meta))

    # 6. Embedding & Pineconeへアップサート
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    Pinecone.from_documents(
        docs,
        embeddings,
        index_name=INDEX_NAME,
        namespace=NAMESPACE
    )
    print("Ingestion completed!")

if __name__ == "__main__":
    main()
