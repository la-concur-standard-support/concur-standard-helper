import os
from pinecone import Pinecone as PineconeClient, ServerlessSpec
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

INDEX_NAME    = "concur-index"    # 例
NAMESPACE     = "demo-html"       # 例
DOC_FILENAME  = "Exp_SG_Account_Codes-jp.txt"  # 適宜変更
DOCS_FOLDER   = "../concur-docs"

def main():
    # 1. APIキー（環境変数から読み取り）
    pinecone_api_key  = os.getenv("PINECONE_API_KEY", "")
    openai_api_key    = os.getenv("OPENAI_API_KEY", "")
    # 例: dimension = 1536 (OpenAI Embedding)
    dimension         = 1536

    # 2. Pinecone クライアント作成
    #    pinecone.init() の代わりに Pinecone() インスタンスを使う
    pc = PineconeClient(
        api_key=pinecone_api_key
        # project_name="xxxxx"  # 必要に応じて指定
        # environment / region は ServerlessSpec で指定する場合も。
    )

    # 3. 必要なら index を作成 (すでに存在する場合スキップ)
    #    例えば “cosine” を使うなら:
    index_list = pc.list_indexes().names()
    if INDEX_NAME not in index_list:
        print(f"Creating index {INDEX_NAME} ...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",      # or "gcp"
                region="us-east-1"  # your region
            )
        )
    else:
        print(f"Index {INDEX_NAME} already exists.")

    # 4. ドキュメント読み込み
    file_path = f"{DOCS_FOLDER}/{DOC_FILENAME}"
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 5. テキスト分割
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)

    # 6. Documentオブジェクトに変換
    docs = []
    for i, chunk_text in enumerate(chunks):
        metadata = {"filename": DOC_FILENAME, "chunk_index": i}
        d = Document(page_content=chunk_text, metadata=metadata)
        docs.append(d)

    # 7. Embeddings
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

    # 8. Pinecone VectorStore へアップサート
    #    pinecone_client=pc を指定する
    vectorstore = Pinecone.from_documents(
        docs,
        embeddings,
        pinecone_client=pc,
        index_name=INDEX_NAME,
        namespace=NAMESPACE
    )

    print("Ingestion completed!")

if __name__ == "__main__":
    main()
