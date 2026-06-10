---
name: llm-application-dev
source: "wshobson/agents (adapted)"
version: "1.0"
description: >
  End-to-end LLM application development: RAG pipelines, prompt engineering patterns,
  structured outputs, vector databases, embeddings, and LangChain/LangGraph orchestration
  with Claude. Triggers: /llm-application-dev, rag implementation, prompt engineering,
  vector database, embeddings, RAG система, промпт инжиниринг, LLM приложение.
triggers: [llm-application-dev, rag-implementation, prompt-engineering-patterns, rag implementation, prompt engineering, vector database, embeddings, langchain, langgraph, RAG система, промпт инжиниринг, LLM приложение]
tokens: ~3500
---

<!-- BSV
Скил   : llm-application-dev
TL;DR  : RAG пайплайны + промпт-инжиниринг для LLM приложений на Claude/LangChain
Вызов  : /llm-application-dev, rag implementation, prompt engineering, RAG система
НЕ для : обучения моделей, fine-tuning, инфраструктуры GPU-кластеров
-->

# LLM Application Development

Build production-grade LLM applications: RAG systems, structured outputs, and optimized prompts.

## When to Use This Skill

- Building RAG (Retrieval-Augmented Generation) systems over private documents
- Optimizing prompts for consistency and reliability in production
- Implementing structured outputs with Pydantic schemas
- Choosing and integrating vector databases (Pinecone, Weaviate, Chroma)
- Selecting embedding models for Claude applications
- Designing chain-of-thought and few-shot learning systems
- Debugging hallucinations, inconsistent outputs, or latency issues
- Building multi-step LLM workflows with LangGraph

---

## Part 1: RAG Implementation

### When RAG Beats Fine-Tuning

| Scenario | Approach |
|---|---|
| Proprietary documents, frequent updates | RAG |
| Stable domain knowledge, latency-critical | Fine-tuning |
| Need citations and source attribution | RAG |
| Behavior/style change | Fine-tuning |

### Vector Database Selection

| DB | Best for | Notes |
|---|---|---|
| **Pinecone** | Production, managed | Serverless tier available |
| **Weaviate** | Hybrid search (dense + sparse) | Open-source, self-hosted option |
| **Chroma** | Development, local | Lightweight, zero-config |
| **pgvector** | Existing Postgres stack | SQL joins with vector search |
| **Qdrant** | High-throughput filtering | Rust core, fast payload filters |

### Embedding Model Selection

| Model | Provider | Dims | Notes |
|---|---|---|---|
| `voyage-3-large` | Voyage AI | 1024 | **Anthropic recommended** for Claude apps |
| `text-embedding-3-large` | OpenAI | 3072 | Strong general-purpose |
| `bge-large-en-v1.5` | BAAI | 1024 | Open-source, competitive quality |
| `embed-english-v3.0` | Cohere | 1024 | Good multilingual |

### Complete RAG Pipeline (LangGraph + Claude)

```python
from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import Chroma
from langchain_voyageai import VoyageAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import START, StateGraph
from typing import TypedDict, List
from langchain_core.documents import Document

# State definition
class RAGState(TypedDict):
    question: str
    context: List[Document]
    answer: str

# Initialize components
embeddings = VoyageAIEmbeddings(model="voyage-3-large")
vectorstore = Chroma(embedding_function=embeddings, persist_directory="./chroma_db")
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
llm = ChatAnthropic(model="claude-sonnet-4-6")

rag_prompt = ChatPromptTemplate.from_messages([
    ("system", """Answer using only the provided context.
    If the answer is not in the context, say "I don't know."
    Always cite the source document.

    Context:
    {context}"""),
    ("human", "{question}")
])

# Graph nodes
def retrieve(state: RAGState) -> RAGState:
    docs = retriever.invoke(state["question"])
    return {"context": docs}

def generate(state: RAGState) -> RAGState:
    context_text = "\n\n".join(doc.page_content for doc in state["context"])
    chain = rag_prompt | llm
    response = chain.invoke({"question": state["question"], "context": context_text})
    return {"answer": response.content}

# Build graph
graph = StateGraph(RAGState)
graph.add_node("retrieve", retrieve)
graph.add_node("generate", generate)
graph.add_edge(START, "retrieve")
graph.add_edge("retrieve", "generate")
rag_app = graph.compile()

# Run
result = rag_app.invoke({"question": "What is our refund policy?"})
print(result["answer"])
```

### Retrieval Strategies

1. **Dense retrieval** — embedding similarity (good for semantic match)
2. **Sparse retrieval** — BM25/keyword (good for exact terms, product names)
3. **Hybrid search** — combine both with RRF (Reciprocal Rank Fusion)
4. **Multi-query** — generate N query variants, union results

### Reranking (improves top-k quality significantly)

```python
from langchain_cohere import CohereRerank
from langchain.retrievers import ContextualCompressionRetriever

compressor = CohereRerank(model="rerank-english-v3.0", top_n=3)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=retriever
)
```

---

## Part 2: Prompt Engineering Patterns

### Few-Shot Learning

```python
from langchain_core.prompts import FewShotChatMessagePromptTemplate

examples = [
    {"input": "The product broke after 2 days", "output": "negative"},
    {"input": "Best purchase I've made this year!", "output": "positive"},
    {"input": "It works, nothing special", "output": "neutral"},
]

example_prompt = ChatPromptTemplate.from_messages([
    ("human", "{input}"), ("ai", "{output}")
])

few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=examples,
    example_prompt=example_prompt,
)
```

### Structured Outputs with Pydantic

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

class SQLQuery(BaseModel):
    query: str = Field(description="The SQL query")
    explanation: str = Field(description="Brief explanation")
    tables_used: list[str] = Field(description="Tables referenced")

llm = ChatAnthropic(model="claude-sonnet-4-6")
structured_llm = llm.with_structured_output(SQLQuery)

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert SQL developer.
    Generate efficient, secure SQL with parameterized queries."""),
    ("user", "Convert this to SQL: {query}")
])

chain = prompt | structured_llm
result = await chain.ainvoke({"query": "Find users registered in the last 30 days"})
print(result.query)        # SELECT * FROM users WHERE created_at > ...
print(result.tables_used)  # ['users']
```

### Chain-of-Thought Patterns

```python
cot_prompt = ChatPromptTemplate.from_messages([
    ("system", """Solve problems step by step.
    Format:
    REASONING: <step-by-step thinking>
    ANSWER: <final answer>"""),
    ("user", "{problem}")
])
```

### System Prompt Design Checklist

- [ ] Role and expertise defined ("You are an expert X")
- [ ] Output format specified (JSON, markdown, plain text)
- [ ] Constraints listed (max length, forbidden topics)
- [ ] Example of desired output included (if non-obvious)
- [ ] Edge case handling specified ("If unsure, say...")

### Prompt Optimization Workflow

1. Baseline: simple zero-shot prompt, measure accuracy on 20 samples
2. Add chain-of-thought — measure delta
3. Add few-shot examples (3-5) — measure delta
4. Add output schema — measure parse failure rate
5. A/B test variants, track: accuracy, consistency, latency, token cost

---

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Hallucinated citations in RAG | Require model to quote exact passage before answering |
| Context window overflow | Rerank + truncate to top-3 docs, max 4K context |
| Inconsistent JSON output | Use `with_structured_output()` instead of text parsing |
| Over-engineered prompts | Start simple; complexity has diminishing returns |
| No error handling on LLM calls | Wrap in retry with exponential backoff |
| Hardcoded prompts in code | Store in version-controlled YAML/JSON files |

## Production Checklist

- [ ] Retry logic with exponential backoff (transient API errors)
- [ ] Token usage logging per request
- [ ] Prompt version tracked in metadata
- [ ] Latency P50/P95/P99 monitored
- [ ] Fallback behavior when retrieval returns nothing
- [ ] PII scrubbing before sending to external APIs
