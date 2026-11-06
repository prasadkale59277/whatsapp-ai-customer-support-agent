
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("SUPABASE_DB_HOST")
DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
DB_PORT = os.getenv("SUPABASE_DB_PORT", "5432")

EMBED_DIMENSION = 384


class SupabaseVectorDB:

    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connect()

        return cls._instance

    def _connect(self):
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT,
            )

            self._connection.autocommit = True

    def search_similar_in_my_embeddings(
        self,
        query_embedding: list[float],
        top_k: int = 3,
    ):

        if len(query_embedding) != EMBED_DIMENSION:
            raise ValueError(
                f"Expected {EMBED_DIMENSION} dimensions, "
                f"got {len(query_embedding)}"
            )

        self._connect()

        embedding_str = "[" + ",".join(
            str(float(value)) for value in query_embedding
        ) + "]"

        sql = """
            SELECT
                id,
                text_content,
                metadata,
                embedding <-> %s::vector(384) AS distance
            FROM my_embeddings
            ORDER BY embedding <-> %s::vector(384)
            LIMIT %s;
        """

        with self._connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                sql,
                (embedding_str, embedding_str, top_k)
            )

            results = cursor.fetchall()

        return results

    def close(self):
        if self._connection and not self._connection.closed:
            self._connection.close()
