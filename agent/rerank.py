"""Vision reranking interface; preserves retrieval order until configured."""
def rerank_shots(ctx, req, shots, k=20):
    return list(shots)
