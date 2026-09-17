# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
#!/usr/bin/env python3
"""
Pathfinder GM Agent — unified RAG with 2e→1e fallback.
Local Ollama models only.
"""
import requests, time, argparse
import pysqlite3 as sqlite3
from pathlib import Path

DB = Path("pathfinder_rag.db")

# ---- LLM Backends ----
def ask_ollama(prompt, model):
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 300}
        }
    )
    if resp.status_code == 200:
        return resp.json()["response"]
    return f"[Ollama Error {resp.status_code}]"

# ---- RAG Search ----
def search(query, edition=None, limit=3):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    if edition:
        cur.execute(
            "SELECT system, category, name, source_book, raw_content FROM rules WHERE system=? AND rules MATCH ? LIMIT ?",
            (edition, query, limit)
        )
    else:
        cur.execute(
            "SELECT system, category, name, source_book, raw_content FROM rules WHERE rules MATCH ? LIMIT ?",
            (query, limit)
        )
    results = cur.fetchall()
    conn.close()
    return results

def main():
    parser = argparse.ArgumentParser(description="Pathfinder GM Agent")
    parser.add_argument("question", nargs="+", help="Your rules question")
    parser.add_argument("--model", default="phi4-mini:latest",
                        help="Ollama model name to use")
    args = parser.parse_args()

    question = " ".join(args.question)
    print(f"[GM] Searching: {question}")

    # 2e first, fallback to 1e
    results = search(question, edition="2e")
    if not results:
        print("  No 2e results, trying 1e...")
        results = search(question, edition="1e")

    if not results:
        print("No rules found.")
        return

    # Build prompt
    context = "\n\n".join(
        f"[{r[0].upper()} | {r[2]}]\n{r[4][:300]}" for r in results
    )
    prompt = f"""You are a Pathfinder GM. Answer from the rules below. Cite edition and name.

{context}

Question: {question}
Answer:"""

    model = args.model
    print(f"[GM] Using local model: {model}")
    start = time.time()
    answer = ask_ollama(prompt, model)
    elapsed = time.time() - start
    print(f"[Generated in {elapsed:.1f}s]")

    print(answer)

if __name__ == "__main__":
    main()
