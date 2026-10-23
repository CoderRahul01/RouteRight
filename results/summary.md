# RouteRight Benchmark Results

## Mode Comparison

| Metric | RouteRight | Always Frontier | Always Small |
|--------|-----------|----------------|-------------|
| Accuracy (%) | 90.0 | 50.0 | 50.0 |
| Routed Small (%) | 40.0 | 0.0 | 100.0 |
| Total Cost (USD) | $0.137797 | $0.218481 | $0.003593 |
| P50 Total Latency (ms) | 953.51 | 1541.67 | 393.18 |
| P95 Total Latency (ms) | 2443.45 | 2437.41 | 564.46 |

## Cost Savings vs Always-Frontier
- Cost saved: $0.080684 (36.9%)
- RouteRight cost: $0.137797
- Always-frontier cost: $0.218481

## Decision Latency (RouteRight - Decider 2B)
- P50: 4.74 ms
- P95: 7.24 ms

## Misrouted Questions - routeright

- **Q1**: "What is the capital of Japan?"
  - Label: small, Routed to: frontier, Confidence: 0.637

- **Q3**: "List the days of the week."
  - Label: small, Routed to: frontier, Confidence: 0.633

- **Q11**: "What is the boiling point of water in Celsius?"
  - Label: small, Routed to: frontier, Confidence: 0.634

- **Q23**: "Translate 'hello' to Spanish."
  - Label: small, Routed to: frontier, Confidence: 0.627

- **Q25**: "What programming language is known for its use in data science alongside R?"
  - Label: small, Routed to: frontier, Confidence: 0.732

## Misrouted Questions - always-frontier

- **Q1**: "What is the capital of Japan?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q2**: "Convert 72 degrees Fahrenheit to Celsius."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q3**: "List the days of the week."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q4**: "What year did World War II end?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q5**: "Rewrite this sentence in past tense: She walks to the store."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q6**: "What is the chemical symbol for gold?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q7**: "How many continents are there?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q8**: "Capitalize the first letter of each word: hello world from python."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q9**: "What is 15% of 200?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q10**: "Name three primary colors."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q11**: "What is the boiling point of water in Celsius?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q12**: "Reverse the string: hello."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q13**: "Who wrote Romeo and Juliet?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q14**: "Convert 5 kilometers to miles."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q15**: "What is the plural of mouse?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q16**: "How many hours are in a day?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q17**: "What does HTML stand for?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q18**: "Sort these numbers ascending: 5, 2, 8, 1, 9."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q19**: "What color do you get when you mix red and blue?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q20**: "Define the word ephemeral in one sentence."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q21**: "What is the square root of 144?"
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q22**: "Name the largest ocean on Earth."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q23**: "Translate 'hello' to Spanish."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q24**: "Remove all vowels from the word 'education'."
  - Label: small, Routed to: frontier, Confidence: 1.000

- **Q25**: "What programming language is known for its use in data science alongside R?"
  - Label: small, Routed to: frontier, Confidence: 1.000

## Misrouted Questions - always-small

- **Q26**: "Explain the difference between TCP and UDP protocols, including when you would choose each one and the trade-offs involved in real-time applications."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q27**: "Debug this Python code that should return the second largest element but returns the wrong result:
def second_largest(lst):
    lst.sort()
    return lst[-1]"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q28**: "Design a database schema for a ride-sharing application that handles drivers, riders, trips, payments, and ratings. Include the relationships and explain your normalization choices."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q29**: "Compare and contrast microservices architecture versus monolithic architecture. When would you recommend migrating from monolith to microservices, and what are the hidden costs?"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q30**: "Write a Python function that implements a least recently used (LRU) cache with O(1) get and put operations. Explain your data structure choices."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q31**: "Analyze the time and space complexity of merge sort versus quicksort. Under what conditions does quicksort degrade to O(n^2), and how can you prevent it?"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q32**: "Explain how a transformer model processes a sentence, including the roles of self-attention, positional encoding, and the feed-forward layers. Use a concrete example."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q33**: "A distributed system experiences split-brain during a network partition. Explain the CAP theorem trade-offs and design a strategy to handle this scenario in a banking application."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q34**: "Review this SQL query for performance issues and suggest optimizations:
SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.created_at > '2024-01-01' ORDER BY o.total DESC LIMIT 100;"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q35**: "Explain how garbage collection works in Java versus Python. Compare reference counting, mark-and-sweep, and generational collection approaches."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q36**: "Design an API rate limiter that supports multiple tiers (free, pro, enterprise) with different limits. It should handle distributed deployment across multiple servers. Provide pseudocode."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q37**: "Analyze the security vulnerabilities in this authentication flow: user sends password over HTTPS, server hashes with MD5, stores in database, compares on next login. What should change and why?"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q38**: "Write a recursive descent parser for simple arithmetic expressions (addition, multiplication, parentheses) in Python. Handle operator precedence correctly."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q39**: "Explain the Byzantine Generals Problem and how practical Byzantine Fault Tolerance (pBFT) addresses it. What are the performance trade-offs at scale?"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q40**: "Debug this race condition: two threads increment a shared counter 1000 times each, but the final value is less than 2000. Explain why and provide three different solutions."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q41**: "Compare event-driven architecture versus request-response patterns. Design an event-sourcing system for an e-commerce order pipeline with compensation for failures."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q42**: "Explain how consensus algorithms like Raft work. Walk through a leader election scenario with five nodes where the leader fails mid-term."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q43**: "Given a legacy codebase with no tests and tightly coupled modules, create a step-by-step refactoring plan. How do you add tests safely without breaking production?"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q44**: "Analyze the trade-offs between using a relational database versus a document store for a social media application. Consider read patterns, write patterns, scaling, and schema evolution."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q45**: "Implement a concurrent web crawler in Python that respects robots.txt, handles rate limiting, avoids duplicate URLs, and gracefully handles failures. Outline the architecture."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q46**: "Explain how TLS 1.3 handshake works step by step. What changed from TLS 1.2 and why? How does it achieve forward secrecy?"
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q47**: "Design a real-time collaborative text editor like Google Docs. Explain how you would handle concurrent edits using operational transformation or CRDTs."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q48**: "A Kubernetes pod keeps crashing with OOMKilled. Walk through your debugging process from kubectl commands to code-level memory profiling."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q49**: "Explain the internals of how a B+ tree index works in a database. Why is it preferred over a hash index for range queries? Include the performance characteristics."
  - Label: frontier, Routed to: small, Confidence: 1.000

- **Q50**: "Write a Python decorator that implements exponential backoff with jitter for retrying failed API calls. It should support configurable max retries, base delay, and specific exception types."
  - Label: frontier, Routed to: small, Confidence: 1.000
