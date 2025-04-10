# BeanAI_bot

## 📌 Project Description

**BeanAI_bot** — is an intelligent Telegram bot (BeanAI AI Assistant) designed to help users quickly obtain accurate answers to questions related to cryptocurrencies, finance, and associated topics.

The bot utilizes advanced language models (currently GPT-4o mini via API) and integrates with online sources to deliver up-to-date, relevant, and verified information.

___

## 🔍 What BeanAI_bot Can Do:

- **Q&A Mode:**  
  Get quick, reliable answers to any questions about cryptocurrencies, tokens, exchanges, investments, and financial strategies.

- **Internet Integration:**  
  Real-time access to the latest news, analytical tools, and market trackers to ensure accurate, up-to-date information.

- **Website and Document Analysis:**  
  Automatically processes and summarizes articles, documents, and PDFs—saving users time and effort.

- **Quick YouTube Video Analysis:**  
  Transcribes video content and generates concise summaries with key insights and actionable takeaways.

- **Image Recognition:**  
  Analyzes images (e.g., error screenshots in multiple languages) and provides relevant tips, explanations, and guidance.

___

## ⚙️ How Users Interact with the Bot:

- **Telegram Chat:** Easily added to personal or group chats, the bot delivers instant responses when directly mentioned.
- **Simple and Complex Queries:** Handles everything from quick price checks to in-depth analytics and trend analysis—instantly and accurately.
- **Link and File Processing:** Users can send links to websites, videos, or documents, and the bot will automatically analyze the content and return a summarized result.

___

## 🚀 Benefits and Advantages:

- **Instant Answers Without Long Searches:** Get the information you need right away—no more endless scrolling or digging through sources.
- **Always Up-to-Date Crypto and Finance Data:** Stay informed with the latest insights, powered by real-time, reliable data.
- **Convenient and Comprehensive Functionality:**An all-in-one assistant—no need to juggle multiple apps or platforms.
- **Seamless Integration with Group Chats:** Ideal for collaboration—quick access to analytics and answers directly within Telegram groups.

___

## 📈 Improving Answer Quality:

BeanAI_bot is continuously improving thanks to:

- **User Feedback:** Suggestions for edits and improvements help fine-tune answers and expand capabilities.
- **Expert Content Verification:** Community experts review and validate information to ensure accuracy and trustworthiness..
- **Automated Response Evaluation:**  AI-driven analysis helps quickly identify and improve weak or outdated responses.
- **Monitoring Popular Questions:**  Tracks trending topics and FAQs from crypto communities to proactively enrich the knowledge base.

___

## 🛠️ Technologies and Libraries Used in the Project:

The BeanAI_bot project uses the following technologies and libraries:

### Core Technologies:
- **Python 3.x** — The primary programming language used throughout the project.
- **Telegram Bot API (aiogram 2.25.1)** — An asynchronous Python framework for implementing seamless user interaction within Telegram.
- **OpenAI GPT-4o API (openai 1.57.2)** — A state-of-the-art language model API used to generate accurate, high-quality responses.

### Data Processing and Analysis:
- **LangChain 0.3.11, LangChain Community 0.3.11, LangChain OpenAI 0.2.10** — A suite of libraries for integrating language models with various data sources and streamlining interactions with OpenAI’s APIs.
- **Tiktoken 0.7.0** — A tokenization library used for efficiently managing text input and output with OpenAI models.
- **Pandas 2.2.3** — A powerful library for data analysis, manipulation, and structuring.
- **FAISS-cpu 1.7.4** — A high-performance library for fast similarity search and analysis of textual data.

### Internet Access and Data Parsing:
- **Playwright 1.47.0** — A browser automation library used to navigate and extract data from dynamic websites.
- **Cloudscraper 1.2.71** — A tool for bypassing Cloudflare protection when scraping web content.
- **Requests 2.32.3** — A widely used library for sending HTTP requests and handling responses.
- **BeautifulSoup4 4.13.3** — Used for parsing HTML and extracting structured data from web pages.
- **aiohttp 3.8.6** — Enables asynchronous HTTP requests, ideal for high-performance and non-blocking web applications.
- **google-api-python-client 2.145.0** — A Python client for accessing various Google services and APIs.

### Working with Documents and Media Content:
- **python-docx 1.1.2** — Used for creating, reading, and editing DOCX text documents.
- **python-pptx 1.0.2** — Enables the creation and manipulation of PPTX presentation files.
- **PyPDF2 3.0.1** — A library for reading, extracting, and processing text from PDF documents.
- **youtube-transcript-api 0.6.3** — Retrieves text transcripts from YouTube videos for analysis or summarization.
- **ffmpeg** — A powerful tool for processing, converting, and handling audio and video files.
- **libmagic1** — Identifies file types based on content, enabling intelligent file handling.
- **mimetypes** — Determines MIME types of files for proper content classification and processing.

### Working with Archives:
- **py7zr 0.22.0** — A library for working with 7z archives, supporting both extraction and compression of data.

- **zipfile** — A built-in Python module for reading, writing, and extracting ZIP archive files.

### Working with Databases and Caching:
- **psycopg2-binary 2.9.10** — A PostgreSQL database adapter for Python, used to interact with and manage relational data.

___

## ⚙️ Project Configuration:

Create a `.env` file in the root directory of the project and specify the following environment variables:

```env
GPT_SECRET_KEY_FASOLKAAI=your_OpenAI_secret_key  
MODEL_NAME=primary_model_name 
MODEL_NAME_MEM=memory_model_name

TG_TOKEN=telegram_bot_token
CHANNEL_ID=telegram_channel_id
CHANNEL_LINK=telegram_channel_link  

SERVICE_ACCOUNT_FILE=path_to_Google_service_account_file  
SPREADSHEET_ID=Google_spreadsheet_id

GRASPIL_API_KEY=Graspil_API_key
TARGET_START_ID_LIMIT=target_start_id_limit
TARGET_START_ID_START=target_start_initial_id 
TARGET_START_ID_BLOCK=target_id_block

GOOGLE_API_KEY=Google_API_key
SEARCH_ENGINE_GLOBAL_ID=Google_search_engine_id

LANGCHAIN_TRACING_V2=True_or_False
LANGCHAIN_ENDPOINT=Langchain_endpoint
LANGCHAIN_API_KEY=Langchain_API_key
LANGCHAIN_PROJECT=Langchain_project_name

DB_HOST=database_host 
DB_PORT=database_port
DB_NAME=database_name
DB_USER=database_user
DB_PASSWORD=database_user_password
```

___

## 🚀 Installing and Running the Project Locally:

1. Clone the Repository:
```bash
git@github.com:BeanAIcrypto/FasolkaAI_bot.git
```

2. Create and Activate a Virtual Environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/MacOS
venv\Scripts\activate     # Windows
```

3. Install the dependencies:

```bash 
pip install -r requirements.txt
```
4. Set up the environment variables:  

Described above

5. Run the project:
```bash
python app.py
```

___

## 🚀 Running the Project with Docker:

To run the project in a Docker container, follow these steps:

1. **Build the Docker Image**:

```bash
docker build -t fasolkaai_bot .
```

2. **Create and run the container:**:

```bash
docker run -d fasolkaai_bot
```

The bot is now running inside a Docker container and ready to use.
You can start interacting with it directly in Telegram. If configured correctly, it will respond to your messages and perform all supported tasks as expected.

___

## 🏗️ Project Architecture:

The BeanAI_bot project is built using a modular architecture and includes the following key components:

1. **Bot Backend Logic**  
   - **Language**: Python  
   - **Telegram Framework**: `aiogram`  
   - **Structure** Core business logic is implemented as individual asynchronous event (`handlers`).
   - AI Integration **OpenAI API** (`openai`)  for generating intelligent, context-aware responses.

2. **Database Handling**  
   - **PostgreSQL** (via `psycopg2-binary`) — Used for storing user data, message history, and interaction logs.  

3. **Integration with External Services**  
   - **Google API** (`google-api-python-client`) — Integrates with Google Sheets for data input/output.  
   - **Graspil API** — Processes target IDs and provides specific data lookups.  
   - **FAISS** —  Enables high-performance vector-based search for efficient semantic text processing.

4. **Documents and Media Support**  
   - **Document Handling** (`python-docx`, `python-pptx`, `PyPDF2`) — Process DOCX, PPTX, and PDF files.  
   - **Video/Audio Processing** (`ffmpeg`) — Converts and processes various media formats.

5. **Data Parsing and Automation**  
   - **Playwright** — Automates browser tasks and retrieves content from dynamic websites.  
   - **BeautifulSoup4** — Parses and extracts structured data from HTML pages.

6. **Architectural Decisions**  
   - **Modular Code Structure**: All logic is divided into clearly defined modules (e.g.,`handlers`, `services`, `database`, `utils`) for maintainability and scalability..  
   - **Asynchronous Event Handling:**: Uses `asyncio` and `aiogram`  to manage non-blocking Telegram communication and concurrent operations.  
   - **Environment-Based Configuration** Project settings (API keys, tokens, DB credentials) are managed via `.env` files, allowing flexible deployment without modifying code.

   ___

## 👥 Authors:

The project is developed and maintained by:

- **Berkina Diana** — [GitHub](https://github.com/DIprooger), [Telegram](https://t.me/di_berkina)
- **Founder and CEO of BeanAI:** — GitHub (https://github.com/vladguru), [Telegram] (https://t.me/vladguru_AI)


If you have any questions or suggestions, feel free to contact the authors using the provided contact details.

