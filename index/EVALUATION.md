# Human interior retrieval evaluation

20 human-reviewed live scenes saved:15 held-out test and5 tuning. Labels remain private.

Held-out pooled recall@10: cosine 38.9%; diverse shortlist 30.5%.
Tuning pooled recall@10: cosine 51.3%; diverse shortlist 44.8%.

Scope: human relevance judgments over each scene's top40 cosine candidates, not exhaustive catalog recall. Diversity caps can reduce recall while broadening properties; these results do not establish a general model accuracy score. No tuning was performed from these test labels. Image-heading alignment remains unverified; selected SDK scan navigation is verified.
