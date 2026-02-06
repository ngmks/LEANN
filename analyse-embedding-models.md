# Analyse : Modèle d'embedding optimal pour LEANN / Claude Code RAG

## Contexte du projet

**Contenu indexé** : sessions Claude Code (fichiers JSONL) — mélange de français naturel (instructions, discussions) et de code/anglais technique (snippets, messages d'erreur, commandes shell).

**Infrastructure** : Ollama, GPU avec 12 Go de VRAM, mode `--no-compact --no-recompute` (LEANN stocke tous les embeddings dans l'index et les lit directement à la recherche, sans recalcul via le modèle).

**Modèle actuel** : `bge-m3:latest` via Ollama (alias `leann-bge-m3`), flash attention désactivée, `num_ctx=8192`.

**Pourquoi `--no-recompute` ?** L'innovation de LEANN est de ne stocker qu'un graphe de voisinage compressé et de recalculer les embeddings à la volée lors de la recherche (mode `--recompute`, activé par défaut). Cela économise ~97% de stockage mais nécessite un appel au modèle d'embedding pour chaque nœud traversé. Le benchmark interne de LEANN (HNSW, 5000 textes) montre l'impact :

| Mode | Temps de recherche | Taille de l'index |
|------|-------------------|-------------------|
| `--recompute` (défaut) | 0.818s | 1.1 Mo |
| `--no-recompute` | 0.012s | 16.6 Mo |

Le mode `--no-recompute` est **68× plus rapide** à la recherche, ce qui est critique pour un usage interactif dans Claude Code (requêtes MCP en temps réel). Le coût est un stockage ~15× plus élevé, ce qui reste modeste en valeur absolue.

**Implication clé pour le choix du modèle** : en mode `--no-recompute`, la taille du modèle d'embedding n'affecte **pas** la latence de recherche (les vecteurs sont simplement lus depuis le disque). Elle n'affecte que la vitesse d'indexation (moment où Ollama génère les embeddings) et le stockage disque (proportionnel aux dimensions du vecteur : N × D × 4 octets en float32).

---

## 1. Évaluation du modèle actuel : BGE-M3

BGE-M3 (BAAI, 2024) est un modèle de ~568M paramètres basé sur XLM-RoBERTa. Il a été conçu pour être "Multi-Lingual, Multi-Functional, Multi-Granularity".

**Points forts pour ton cas d'usage :**

- Supporte 100+ langues dont le français, fenêtre de 8192 tokens.
- Tri-fonctionnel : dense, sparse (lexical), et ColBERT (multi-vecteur). Via Ollama tu n'utilises que le mode dense, mais c'est suffisant pour LEANN.
- Score MTEB global de ~63.0, solide en retrieval multilingue (nDCG@10 de ~70.0 sur MIRACL en combinant les modes).
- Score MMTEB (multilingue) très compétitif pour sa taille.
- Latence d'inférence <30ms pour un batch unitaire — rapide à l'indexation.

**Limites identifiées :**

- Le français n'est pas une langue prioritaire dans l'entraînement de BGE-M3 : les données sont dominées par l'anglais et le chinois. Le papier MTEB-French (Ciancone et al., 2024) montre une forte corrélation entre les performances et le volume de données d'entraînement dans la langue cible.
- Pas d'instruction-awareness : BGE-M3 ne tire pas parti de préfixes/instructions adaptés à la tâche (contrairement aux modèles instruction-tuned comme E5-instruct ou Qwen3-Embedding).
- Via Ollama, tu utilises le format GGUF qui quantifie le modèle. La perte de qualité dépend du niveau de quantification, mais elle reste modérée en Q4_K_M/Q5_K_M.

---

## 2. Candidats analysés

### 2.1 Qwen3-Embedding-0.6B

| Critère | Valeur |
|---------|--------|
| Paramètres | 0.6B |
| Dimensions | 1024 (configurable via MRL, de 32 à 1024) |
| Context | 32 768 tokens |
| MMTEB | Compétitif avec BGE-M3 à taille équivalente |
| Langues | 100+ (naturelles + langages de programmation) |
| Instruction-aware | Oui — amélioration de 1-5% avec instructions personnalisées |
| Ollama | Disponible (`ollama pull qwen3-embedding:0.6b`, ~493 Mo) |
| VRAM estimée | ~0.6-0.8 Go (Q4), ~1.2-1.5 Go (FP16) |

**Pourquoi c'est intéressant :**

Le Qwen3-Embedding-0.6B a le même nombre de paramètres que BGE-M3 (~0.6B) mais bénéficie d'une architecture plus récente (Qwen3 foundation, 2025) et d'un entraînement avec des données synthétiques multilingues massives. Son entraînement en deux étapes (pre-training contrastif sur données synthétiques + fine-tuning supervisé) le rend plus performant que BGE-M3 sur les benchmarks MMTEB récents.

L'instruction-awareness est un avantage concret pour ton cas : tu pourrais différencier les requêtes de recherche (ex: "Instruct: Retrieve relevant Claude Code session segments about authentication bugs") des documents indexés, ce qui améliore la précision du retrieval.

La fenêtre de contexte de 32K tokens (vs 8K pour BGE-M3) est un bonus si tes chunks sont longs, mais avec un chunk_size de 256 chez LEANN, ce n'est pas critique.

**Point d'attention majeur :**

Qwen3-Embedding utilise un pooling de type "last token" avec un token `<|endoftext|>` à ajouter manuellement. Via Ollama, cela est normalement géré par le template du modèle, mais il faut vérifier que LEANN/Ollama envoie correctement ce token. Sans lui, les embeddings seront dégradés.

De plus, ce modèle est "instruction-aware", ce qui signifie que pour une performance optimale, il faudrait préfixer les requêtes avec une instruction. LEANN ne gère pas nativement cette asymétrie query/document — il faudrait adapter le code au niveau du search dans `base_rag_example.py` ou du MCP server pour injecter le préfixe côté query.

### 2.2 Qwen3-Embedding-4B ⭐ Recommandation principale

| Critère | Valeur |
|---------|--------|
| Paramètres | 4B |
| Dimensions | 2560 (configurable via MRL, de 32 à 2560) |
| Context | 32 768 tokens |
| MMTEB | Très proche du 8B, nettement supérieur à BGE-M3 |
| VRAM estimée | ~3.0 Go (Q4_K_M), ~3.5-4.0 Go (Q5_K_M), ~5.0-5.5 Go (Q8_0) |
| Ollama | `ollama pull qwen3-embedding:4b` (~2.7 Go, Q5_K_M par défaut) |

**Pourquoi c'est le meilleur choix :**

Le saut de qualité du 0.6B au 4B est significatif, surtout en retrieval multilingue. Le papier MTEB-French (Ciancone et al., 2024) documente une forte corrélation entre taille de modèle et performance en français : les modèles >1B paramètres surpassent significativement les ~600M. Passer de 0.6B à 4B représente un changement de catégorie de performance.

Avec tes 12 Go de VRAM, le 4B en Q5_K_M tient largement (~3.5-4.0 Go), laissant ~8 Go de marge pour un LLM parallèle.

En mode `--no-recompute`, la taille du modèle n'affecte pas la vitesse de recherche. Le seul impact est sur l'indexation : le 4B est ~3-5× plus lent par chunk que le 0.6B lors de la génération des embeddings. Ce coût est atténué par le pipeline incrémental (`leann-index-progress.py`) qui ne traite que les sessions nouvelles ou modifiées.

**Impact sur le stockage disque :** Le passage de 1024 dimensions (BGE-M3) à 2560 dimensions (Qwen3-4B) multiplie par 2.5× la taille des embeddings stockés. Pour un index de 2700 chunks, cela représente ~27 Mo (2700 × 2560 × 4 octets) contre ~11 Mo actuellement — une différence de ~16 Mo, négligeable. Si le corpus grandit significativement, le support MRL de Qwen3 permet de réduire les dimensions (ex: 1024 au lieu de 2560) pour contenir la croissance de stockage avec une perte de qualité mineure.

### 2.3 Qwen3-Embedding-8B

| Critère | Valeur |
|---------|--------|
| Paramètres | 8B |
| Dimensions | 4096 (configurable via MRL) |
| MMTEB | N°1 mondial (score 70.58, juin 2025) |
| VRAM estimée | ~5.5-6.5 Go (Q4_K_M), ~6.5-7.5 Go (Q5_K_M), ~9.5-10.5 Go (Q8_0) |
| Ollama | `ollama pull qwen3-embedding:8b` (~5.2 Go) |

**Analyse :**

Le 8B en Q5_K_M (~7.0 Go + overhead CUDA ~0.5 Go ≈ 7.5 Go) laisserait ~4.5 Go libres sur tes 12 Go — suffisant mais sans grande marge pour un LLM parallèle.

En mode `--no-recompute`, la latence de recherche n'est **pas** affectée par la taille du modèle. Le 8B offrirait donc la même vitesse de recherche que le 0.6B. Les vrais trade-offs sont :

- **Indexation plus lente** : ~6-10× par rapport au 0.6B, ce qui allonge le temps de build initial et les mises à jour incrémentales. Avec des centaines de sessions, le premier build complet pourrait prendre significativement plus longtemps.
- **Stockage plus élevé** : 4096 dimensions = 4× plus que BGE-M3. Pour 2700 chunks : ~43 Mo d'embeddings (vs ~11 Mo actuellement). Reste modeste en valeur absolue, mais le delta grandit linéairement avec le corpus.
- **VRAM** : ~7.5 Go en Q5_K_M, ce qui laisse peu de marge pour d'autres tâches GPU.

**Verdict** : Envisageable si la qualité maximale est prioritaire et que la latence d'indexation est acceptée. Le MRL permettrait de réduire à 2560 ou 1024 dimensions pour économiser le stockage sans changer de modèle.

### 2.4 multilingual-e5-large-instruct

| Critère | Valeur |
|---------|--------|
| Paramètres | ~560M |
| Dimensions | 1024 |
| Context | 512 tokens |
| MMTEB | Bon mais inférieur à BGE-M3 et Qwen3 sur le multilingue |
| Instruction-aware | Oui (préfixes query/passage) |
| Ollama | Non disponible nativement |

**Verdict : Éliminé.** Le contexte de seulement 512 tokens est un deal-breaker pour des sessions Claude Code contenant de longs blocs de code. De plus, il n'est pas disponible sur Ollama, ce qui nécessiterait un changement de stack (PyTorch + sentence-transformers au lieu de l'API Ollama), incompatible avec l'architecture actuelle.

### 2.5 Sentence-CamemBERT-large

| Critère | Valeur |
|---------|--------|
| Paramètres | ~335M |
| Dimensions | 1024 |
| Context | 512 tokens |
| Spécificité | Modèle spécialement entraîné pour le français |
| Ollama | Non disponible |

**Verdict : Éliminé.** Mentionné comme modèle de référence pour le français dans la littérature MTEB-French. Cependant, étant monolingue français, il gérerait mal le code et l'anglais technique omniprésent dans les sessions Claude Code. De plus, il n'est pas disponible sur Ollama et sa fenêtre de 512 tokens est insuffisante.

### 2.6 nomic-embed-text v1.5

| Critère | Valeur |
|---------|--------|
| Paramètres | ~137M |
| Dimensions | 768 (Matryoshka, réductible) |
| Context | 8192 tokens |
| MTEB global | ~59.4 |
| Ollama | `ollama pull nomic-embed-text` |

**Verdict : Éliminé.** Léger et rapide mais performances multilingues nettement inférieures à BGE-M3. Entraîné principalement sur anglais. Ce serait une régression pour le français.

---

## 3. Analyse croisée pour ton cas d'usage

### Nature du contenu

Les sessions Claude Code contiennent un mix spécifique : français naturel (instructions, questions, discussions sur l'architecture), anglais technique (messages d'erreur, noms de fonctions, documentation), code (Python, bash, JSON, YAML), et métadonnées (noms de projets, branches git, timestamps).

Un modèle purement français (CamemBERT) serait inadapté. Un modèle purement anglais aussi. Il faut un modèle véritablement multilingue **et** capable de comprendre le code.

### Critères pondérés

Les poids reflètent le mode `--no-recompute` : la vitesse d'inférence ne compte que pour l'indexation (pas pour la recherche), et le stockage disque est directement impacté par les dimensions du modèle.

| Critère | Poids | BGE-M3 (actuel) | Qwen3-0.6B | Qwen3-4B |
|---------|-------|------------------|-------------|-----------|
| Qualité retrieval français | 25% | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| Qualité retrieval code | 15% | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| Multilingue (fr+en mélangé) | 20% | ★★★★☆ | ★★★★☆ | ★★★★★ |
| Vitesse d'indexation | 10% | ★★★★★ | ★★★★★ | ★★★☆☆ |
| VRAM (sur 12 Go) | 10% | ★★★★★ | ★★★★★ | ★★★★☆ |
| Stockage disque (mode no-recompute) | 10% | ★★★★★ | ★★★★★ | ★★★★☆ |
| Facilité d'intégration Ollama | 10% | ★★★★★ | ★★★★☆ | ★★★★☆ |

### Résumé des scores pondérés

- **BGE-M3** : ~3.8/5 — solide, mais pas optimisé pour le français ni instruction-aware
- **Qwen3-Embedding-0.6B** : ~4.2/5 — meilleur en qualité à taille équivalente, architecture plus récente
- **Qwen3-Embedding-4B** : ~4.5/5 — meilleur absolu en qualité, indexation plus lente mais recherche aussi rapide que les autres en mode `--no-recompute`

---

## 4. Recommandation

### Choix recommandé : Qwen3-Embedding-4B ⭐

**Pourquoi :**

1. **Saut qualitatif majeur pour le français** : passer de ~600M à 4B paramètres représente un changement de catégorie de performance documenté par MTEB-French (Ciancone et al., 2024). La famille Qwen3 domine les benchmarks multilingues 2025.
2. **Code retrieval natif** : contrairement à BGE-M3, Qwen3-Embedding est explicitement entraîné sur du code en plus du texte multilingue — crucial pour des sessions Claude Code.
3. **Aucun impact sur la latence de recherche** : en mode `--no-recompute`, les embeddings sont pré-stockés. La recherche lit des vecteurs depuis le disque et calcule des distances, indépendamment du modèle qui les a générés. Un index Qwen3-4B se recherche aussi vite qu'un index BGE-M3.
4. **VRAM confortable** : ~3.5-4.0 Go en Q5_K_M sur 12 Go disponibles, laissant ~8 Go de marge.
5. **Fenêtre 4× plus large** : 32K tokens vs 8K pour BGE-M3.
6. **Instruction-awareness** : potentiel d'amélioration de 1-5% si tu adaptes les requêtes avec un préfixe d'instruction.
7. **MRL (Matryoshka)** : permet de réduire les dimensions (ex: 1024 au lieu de 2560) si le stockage devient un enjeu à grande échelle.
8. **Écosystème Ollama** : `ollama pull qwen3-embedding:4b` — zéro changement de stack.

**Trade-off accepté** : l'indexation est ~3-5× plus lente par chunk. Avec le pipeline incrémental de `leann-index-progress.py`, seuls les nouveaux chunks sont traités à chaque session, ce qui atténue significativement l'impact.

### Alternative légère : Qwen3-Embedding-0.6B

Si la vitesse d'indexation est critique (très gros volume de sessions à indexer fréquemment) ou si la VRAM est partagée avec d'autres processus lourds, le 0.6B offre un upgrade qualitatif par rapport à BGE-M3 (architecture plus récente, instruction-awareness, fenêtre 32K) avec une empreinte comparable.

### Alternative qualité maximale : Qwen3-Embedding-8B

Si la qualité de retrieval est la priorité absolue et que l'indexation peut être lente, le 8B (N°1 mondial MMTEB avec 70.58) offre le meilleur retrieval possible. En Q5_K_M (~7.5 Go VRAM), il tient dans 12 Go mais laisse peu de marge. En mode `--no-recompute`, la recherche reste tout aussi rapide.

---

## 5. Changements nécessaires dans LEANN

### Migration minimale (drop-in replacement)

**Étape 1 : Tirer le modèle**

```bash
ollama pull qwen3-embedding:4b
```

**Étape 2 : Modifier la configuration**

Dans `apps/claude_code_rag.py`, changer le modèle par défaut :

```python
# Ligne ~32 dans ClaudeCodeRAG.__init__
self.embedding_model_default = "qwen3-embedding:4b"  # Avant: "leann-bge-m3"
```

Dans `scripts/leann-index-progress.py`, mettre à jour les arguments passés à `parse_args` :

```python
# Dans _run_indexation()
args = rag.parser.parse_args([
    "--whitelist-file", str(Path.home() / ".leann" / "whitelist.json"),
    "--embedding-mode", "ollama",
    "--embedding-model", "qwen3-embedding:4b",  # Avant: "leann-bge-m3"
    "--no-compact",
    "--no-recompute",
])
```

**Étape 3 : Reconstruire l'index**

Changer de modèle d'embedding invalide l'index existant (dimensions incompatibles : 1024 → 2560). Le code de `_incremental_load` détecte automatiquement le changement de modèle via le manifest et affiche "Full rebuild required." Il faut donc supprimer l'index existant et relancer un build complet :

```bash
rm -rf ~/.leann/indexes/claude-code-sessions/*
# Puis relancer leann-index-progress.py ou le build via claude_code_rag.py
```

### Migration optimale (avec instructions)

Pour tirer parti de l'instruction-awareness, il faudrait que LEANN envoie un préfixe différent selon que le texte est un document (indexation) ou une requête (recherche). Actuellement, le CLI LEANN ne propose pas de paramètre dédié pour cela.

L'implémentation nécessiterait de modifier le code au niveau de la recherche, par exemple dans `base_rag_example.py` ou dans le MCP server `leann_mcp`, pour injecter un préfixe côté query uniquement :

```python
# Exemple d'injection côté query
query_prefix = "Instruct: Given a developer question, retrieve relevant Claude Code session segments\nQuery: "
prefixed_query = query_prefix + user_query
```

Les documents (côté indexation) ne reçoivent pas de préfixe — c'est l'asymétrie recommandée par Qwen.

Cette optimisation n'est pas critique pour un premier déploiement. Le modèle fonctionne correctement sans instructions, le préfixe apporte un gain marginal de 1-5%.

### Gestion du token `<|endoftext|>`

Qwen3-Embedding utilise un pooling "last token" et nécessite que `<|endoftext|>` soit ajouté à la fin de chaque input. Via Ollama, cela devrait être géré automatiquement par le template du modèle (le Modelfile inclut normalement cette configuration). À vérifier après installation avec un test simple de comparaison d'embeddings.

### Modelfile personnalisé (optionnel)

Si tu veux créer un alias `leann-qwen3-emb` comme tu l'as fait pour `leann-bge-m3`, crée un Modelfile :

```
FROM qwen3-embedding:4b
PARAMETER num_ctx 8192
```

Puis : `ollama create leann-qwen3-emb -f Modelfile`

Note : la désactivation du flash attention (`/no_flash_attn`) que tu as faite pour BGE-M3 n'est probablement pas nécessaire pour Qwen3-Embedding. À tester — si les embeddings sont cohérents sans, garde le défaut.

---

## 6. Plan de validation

Avant de migrer en production :

1. **Bench comparatif** : utilise ton `benchmark/bench_run.py` existant pour comparer le temps d'indexation entre `leann-bge-m3` et `qwen3-embedding:4b`. Note : seul le temps d'indexation changera, pas la vitesse de recherche (mode `--no-recompute`).
2. **Test qualitatif** : lance 10-15 requêtes représentatives en français et en anglais technique sur les deux index, compare la pertinence des résultats (top-5).
3. **Vérification du token EOS** : compare les embeddings d'un même texte entre Ollama et la référence HuggingFace pour vérifier que le pipeline est correct.
4. **Vérification du stockage** : compare la taille de l'index sur disque entre BGE-M3 (dim 1024) et Qwen3-4B (dim 2560) pour confirmer les estimations (~2.5× plus gros pour les embeddings).

---

## Sources

- MTEB-French (Ciancone et al., 2024) : https://arxiv.org/html/2405.20468v1
- MMTEB (Enevoldsen et al., 2025) : https://arxiv.org/abs/2502.13595
- Qwen3-Embedding paper : https://arxiv.org/pdf/2506.05176
- BGE-M3 (BAAI) : https://huggingface.co/BAAI/bge-m3
- MTEB Leaderboard : https://huggingface.co/spaces/mteb/leaderboard
- Qwen3-Embedding sur Ollama : https://ollama.com/library/qwen3-embedding
- LEANN Configuration Guide : docs/configuration-guide.md (benchmarks --no-recompute vs --recompute)
- Guide Lyon NLP (bonnes pratiques MTEB) : https://huggingface.co/blog/lyon-nlp-group/mteb-leaderboard-best-practices
