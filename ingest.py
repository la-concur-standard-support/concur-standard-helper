import os
from dotenv import load_dotenv
load_dotenv()  # .envファイルの内容をos.environ に反映

import pinecone  # pineconeパッケージ（client v5系 or 6系で統一）
from langchain_openai import OpenAIEmbeddings  # langchain-openai
from langchain_pinecone import PineconeVectorStore  # langchain-pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

INDEX_NAME    = "concur-index"
NAMESPACE     = "demo-html"
DOC_FILENAME  = "Exp_SG_Account_Codes-jp.txt"  # 適宜変更
DOCS_FOLDER   = "../concur-docs"

def main():
    # 1. 環境変数取得
    pinecone_api_key = os.getenv("PINECONE_API_KEY", "")
    openai_api_key   = os.getenv("OPENAI_API_KEY", "")
    pinecone_env     = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")

    dimension = 1536  # OpenAI Embedding のベクトル次元

    # 2. Pinecone初期化
    pinecone.init(
        api_key=pinecone_api_key,
        environment=pinecone_env
    )

    # 3. インデックスが無ければ作成 or すでに存在すればスキップ
    #    v5系 pinecone: pinecone.list_indexes() などを使う
    index_list = pinecone.list_indexes()
    if INDEX_NAME not in index_list:
        print(f"Creating index {INDEX_NAME} ...")
        pinecone.create_index(
            name=INDEX_NAME,
            dimension=dimension,
            metric="cosine"
        )
    else:
        print(f"Index {INDEX_NAME} already exists.")

    # 4. ローカルファイル読み込み
    file_path = f"{DOCS_FOLDER}/{DOC_FILENAME}"
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 5. テキスト分割
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)

    # 6. Documentリストを生成
    docs = []
    for i, chunk_text in enumerate(chunks):
        meta = {"filename": DOC_FILENAME, "chunk_index": i}
        doc = Document(page_content=chunk_text, metadata=meta)
        docs.append(doc)

    # 7. Embeddings
    embeddings = OpenAIEmbeddings(api_key=openai_api_key)

    # 8. インデックスオブジェクトを取得
    my_index = pinecone.Index(INDEX_NAME)

    # 9. PineconeVectorStore へアップサート
    #    from_documents(...) を使って docs をベクトル化し、一括で Pinecone に登録
    vectorstore = PineconeVectorStore.from_documents(
        documents=docs,
        embedding=embeddings,
        index=my_index,
        namespace=NAMESPACE
    )

    print("Ingestion completed!")

if __name__ == "__main__":
    main()

