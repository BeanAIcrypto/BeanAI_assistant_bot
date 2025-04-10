import os
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()


def read_markdown(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


define_headers = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
    ("####", "Header 4"),
]

splitter = MarkdownHeaderTextSplitter(define_headers)

md_file_path = "БЗ _Фасолька_ (для загрузки в модель).txt"
text = read_markdown(md_file_path)
chunks = splitter.split_text(text)

openai_api_key = os.getenv("GPT_SECRET_KEY_FASOLKAAI", "")
if not openai_api_key:
    raise ValueError(
        "Не найден OPENAI_API_KEY. Укажите его в .env или системе."
    )


embeddings = OpenAIEmbeddings(
    openai_api_key=openai_api_key, model="text-embedding-ada-002"
)

faiss_db = FAISS.from_documents(chunks, embeddings)
faiss_db.save_local("faiss_index_RU")

print("Индекс успешно сохранён в faiss_index_US")


from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings

openai_api_key = os.getenv("OPENAI_API_KEY", "")
if not openai_api_key:
    raise ValueError(
        "Не найден OPENAI_API_KEY. Укажите его в .env или системе."
    )

embeddings_check = OpenAIEmbeddings(
    openai_api_key=openai_api_key, model="text-embedding-ada-002"
)

db_check = FAISS.load_local(
    "faiss_index_US", embeddings_check, allow_dangerous_deserialization=True
)

documents = db_check.docstore._dict
print(f"Количество документов в базе: {len(documents)}")

for doc_id, document in documents.items():
    print(f"ID документа: {doc_id}")
    print(f"Содержимое: {document.page_content}")
    print(f"Метаданные: {document.metadata}")
    print("--------")
