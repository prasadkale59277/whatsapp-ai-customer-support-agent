
import os
import math

import logfire
from dotenv import load_dotenv
from groq import Groq

from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.exceptions import UsageLimitExceeded

from database.pg_vector import SupabaseVectorDB


load_dotenv()


# --------------------------------------------------
# ENVIRONMENT CONFIGURATION
# --------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing from .env")

logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

# --------------------------------------------------
# GROQ CHAT MODEL
# --------------------------------------------------

model = GroqModel(
    "openai/gpt-oss-20b",
    provider=GroqProvider(
        api_key=GROQ_API_KEY
    ),
)

# --------------------------------------------------
# LOCAL EMBEDDING MODEL
# --------------------------------------------------

from sentence_transformers import SentenceTransformer

EMBED_DIMENSION = 384

embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)


def get_embedding(text: str):
    """
    Generate normalized 384-dimensional embeddings
    using the local Sentence Transformers model.
    """

    vector = embedding_model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    if len(vector) != EMBED_DIMENSION:
        raise ValueError(
            f"Expected {EMBED_DIMENSION} dimensions, "
            f"got {len(vector)}"
        )

    return vector.tolist()

# --------------------------------------------------
# SYSTEM PROMPT
# --------------------------------------------------


system_prompt = """
You are a technical support assistant for agricultural equipment.

IMPORTANT RULES:

1. Use the supplied COMPANY DATABASE CONTEXT as the
   authoritative source for technical troubleshooting.

2. Never invent troubleshooting instructions.

3. Do not use general knowledge to create solutions
   for equipment problems.

4. If relevant database information is available:
   - Identify the matching problem.
   - Follow the database instructions.
   - Give only ONE troubleshooting step at a time.
   - Do not mix solutions from different problems.

5. If no relevant database information is available:
   - Clearly say that verified information is unavailable.
   - Ask for additional equipment details if necessary.
   - Offer escalation to a human technician.

6. If the customer reports that a step did not work,
   continue with the next available database step.

7. WhatsApp formatting:
   - Bold: *this text*
   - Italics: _this text_
"""



# --------------------------------------------------
# CREATE PYDANTIC AI AGENT
# --------------------------------------------------

assistant = Agent(
    model,
    system_prompt=system_prompt,
    model_settings={
        "temperature": 0.0,
        "max_tokens": 500,
    },
)


# --------------------------------------------------
# RAG TOOL
# --------------------------------------------------


# --------------------------------------------------
# RAG RETRIEVAL FUNCTION
# --------------------------------------------------

def retrieve_knowledge(query: str) -> str:

    print("\n========== RAG RETRIEVAL STARTED ==========")
    print("Customer query:", query)

    db = SupabaseVectorDB()

    query_embedding = get_embedding(query)

    print("Embedding dimensions:", len(query_embedding))

    docs = db.search_similar_in_my_embeddings(
        query_embedding,
        top_k=3,
    )

    print("Retrieved documents:", len(docs))

    if not docs:
        print("No matching documents found.")
        return ""

    retrieved_context = []

    for index, doc in enumerate(docs):

        print(f"\nRetrieved document {index + 1}:")
        print("Distance:", doc["distance"])
        print(doc["text_content"])

        retrieved_context.append(
            doc["text_content"]
        )

    return "\n\n---\n\n".join(retrieved_context)
