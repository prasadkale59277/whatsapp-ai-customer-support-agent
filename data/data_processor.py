
import csv
import json
import os
import math

import psycopg2
from dotenv import load_dotenv
from groq import Groq
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()


# --------------------------------------------------
# GROQ CONFIGURATION
# --------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing from .env")

groq_client = Groq(api_key=GROQ_API_KEY)

EMBEDDING_MODEL = "nomic-embed-text-v1.5"


# --------------------------------------------------
# POSTGRES CONNECTION CONFIGURATION
# --------------------------------------------------

POSTGRES_HOST = os.getenv("SUPABASE_DB_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("SUPABASE_DB_PORT", 5432))
POSTGRES_DB = os.getenv("SUPABASE_DB_NAME", "postgres")
POSTGRES_USER = os.getenv("SUPABASE_DB_USER", "postgres")
POSTGRES_PASS = os.getenv("SUPABASE_DB_PASSWORD", "")


# --------------------------------------------------
# CSV CONFIGURATION
# --------------------------------------------------

CSV_FILE_PATH = "data/data.csv"


# --------------------------------------------------
# EMBEDDING CONFIGURATION
# --------------------------------------------------

EMBED_DIMENSION = 384

embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

def get_embedding(text):
    """
    Generate embeddings locally using Sentence Transformers.
    Returns a normalized 384-dimensional vector.
    """

    vector = embedding_model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return vector.tolist()

# --------------------------------------------------
# 1. HELPER FUNCTIONS
# --------------------------------------------------

def connect_to_postgres():
    """Connect to PostgreSQL and register pgvector."""

    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASS,
    )

    register_vector(conn)

    return conn


def create_table_if_not_exists(conn):
    """
    Create embeddings table if it does not exist.
    pgvector extension must already be enabled.
    """

    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS my_embeddings (
            id SERIAL PRIMARY KEY,
            source_id TEXT,
            chunk_index INT,
            text_content TEXT,
            metadata JSONB,
            embedding VECTOR({EMBED_DIMENSION})
        );
    """

    create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_my_embeddings_embedding
        ON my_embeddings
        USING ivfflat (embedding vector_l2_ops)
        WITH (lists = 100);
    """

    with conn.cursor() as cur:
        cur.execute(create_table_sql)
        cur.execute(create_index_sql)

    conn.commit()


def chunk_text(text, max_chars=2000):
    """Split text into manageable chunks."""

    chunks = []

    start = 0

    while start < len(text):
        end = start + max_chars

        chunk = text[start:end]

        chunks.append(chunk)

        start = end

    return chunks





# --------------------------------------------------
# 3. INSERT EMBEDDING INTO DATABASE
# --------------------------------------------------

def insert_embedding_row(
    conn,
    source_id,
    chunk_idx,
    text_content,
    metadata_dict,
    embedding_vector,
):
    """Insert one text chunk and its embedding into PostgreSQL."""

    insert_query = """
        INSERT INTO my_embeddings
        (source_id, chunk_index, text_content, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s);
    """

    with conn.cursor() as cur:
        cur.execute(
            insert_query,
            (
                source_id,
                chunk_idx,
                text_content,
                json.dumps(metadata_dict),
                embedding_vector,
            ),
        )


# --------------------------------------------------
# 4. MAIN CSV INGESTION
# --------------------------------------------------

def process_csv_and_store_embeddings(csv_file_path):

    conn = connect_to_postgres()

    try:
        create_table_if_not_exists(conn)

        with open(
            csv_file_path,
            mode="r",
            encoding="utf-8",
        ) as f:

            reader = csv.DictReader(f, delimiter=";")

            for idx, row in enumerate(reader):

                source_id = str(idx)

                # Build structured text
                structured_text = (
                    f"ROBOT MODEL: {row.get('ROBOT_MODEL', '').strip()}\n"
                    f"ISSUE CATEGORY: {row.get('ISSUE_CATEGORY', '').strip()}\n"
                    f"INCIDENT SUMMARY: {row.get('INCIDENT_SUMMARY', '').strip()}\n"
                    f"DESCRIPTION: {row.get('DESCRIPTION', '').strip()}\n"
                    f"PRIORITY: {row.get('PRIORITY', '').strip()}\n\n"
                    "Steps to follow:\n"
                    f"Step 1: {row.get('STEP_1', '').strip()}\n"
                    f"Step 2: {row.get('STEP_2', '').strip()}\n"
                    f"Step 3: {row.get('STEP_3', '').strip()}\n"
                    f"Step 4: {row.get('STEP_4', '').strip()}\n"
                )

                # Build metadata
                metadata_dict = dict(row)

                for key in [
                    "INCIDENT_SUMMARY",
                    "DESCRIPTION",
                    "STEP_1",
                    "STEP_2",
                    "STEP_3",
                    "STEP_4",
                ]:
                    metadata_dict.pop(key, None)

                # Split text into chunks
                text_chunks = chunk_text(
                    structured_text,
                    max_chars=2000,
                )

                # Generate and store embeddings
                for i, chunk in enumerate(text_chunks):

                    embedding_vector = get_embedding(chunk)

                    insert_embedding_row(
                        conn,
                        source_id=source_id,
                        chunk_idx=i,
                        text_content=chunk,
                        metadata_dict=metadata_dict,
                        embedding_vector=embedding_vector,
                    )

                print(f"Processed CSV row: {idx + 1}")

                conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# --------------------------------------------------
# 5. RUN SCRIPT
# --------------------------------------------------

if __name__ == "__main__":

    process_csv_and_store_embeddings(CSV_FILE_PATH)

    print(
        "CSV data successfully processed "
        "and Groq embeddings stored!"
    )
