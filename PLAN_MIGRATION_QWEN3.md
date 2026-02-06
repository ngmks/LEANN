# Plan de migration : BGE-M3 → Qwen3-Embedding-4B

## Décisions architecturales

### ✅ Migration SANS prompts (Phase 1)
Qwen3-Embedding fonctionne correctement sans prompts. Le gain avec prompts est marginal (1-5%) et nécessiterait de modifier `BaseRAGExample`, impactant tous les autres RAG exemples.

**Stratégie** : Migrer maintenant sans prompts, ajouter les prompts plus tard comme optimisation si nécessaire.

### ✅ Utilisation du nom officiel
Utiliser `qwen3-embedding:4b` (nom Ollama officiel) plutôt qu'un alias custom `leann-qwen3-emb`. Simplifie la maintenance et évite la confusion.

### ✅ Rebuild complet obligatoire
Dimensions incompatibles (1024 → 2560), pas d'upgrade incrémental possible.

---

## Phase 1 : Installation du modèle

### Étape 1.1 : Installer Qwen3-Embedding-4B

```bash
ollama pull qwen3-embedding:4b
```

**Vérification :**
```bash
ollama list | grep qwen3-embedding
# Attendu : qwen3-embedding:4b  (2.7 GB, Q5_K_M)
```

**Temps estimé** : 2-5 minutes selon connexion

---

## Phase 2 : Modification du code source

### Étape 2.1 : `apps/claude_code_rag.py`

**Fichier** : `apps/claude_code_rag.py`
**Ligne** : 86

```python
# AVANT
self.embedding_model_default = "leann-bge-m3"

# APRÈS
self.embedding_model_default = "qwen3-embedding:4b"
```

### Étape 2.2 : `scripts/leann-index-progress.py`

**Fichier** : `scripts/leann-index-progress.py`

**Changement 1** — Ligne 29 (signature `_warmup_ollama`) :
```python
# AVANT
def _warmup_ollama(host: str = "http://localhost:11434", model: str = "leann-bge-m3", rounds: int = 5) -> bool:

# APRÈS
def _warmup_ollama(host: str = "http://localhost:11434", model: str = "qwen3-embedding:4b", rounds: int = 5) -> bool:
```

**Changement 2** — Ligne 117 (args CLI) :
```python
# AVANT
    args = rag.parser.parse_args([
        "--whitelist-file", str(Path.home() / ".leann" / "whitelist.json"),
        "--embedding-mode", "ollama",
        "--embedding-model", "leann-bge-m3",
        "--no-compact",
        "--no-recompute",
    ])

# APRÈS
    args = rag.parser.parse_args([
        "--whitelist-file", str(Path.home() / ".leann" / "whitelist.json"),
        "--embedding-mode", "ollama",
        "--embedding-model", "qwen3-embedding:4b",
        "--no-compact",
        "--no-recompute",
    ])
```

### Étape 2.3 : `packages/leann-core/src/leann/embedding_compute.py`

**Fichier** : `packages/leann-core/src/leann/embedding_compute.py`

**Changement 1** — Ligne 38 (registre token limits) :
```python
# AVANT
EMBEDDING_MODEL_LIMITS = {
    # Nomic models (common across servers)
    "nomic-embed-text": 2048,
    "nomic-embed-text-v1.5": 2048,
    "nomic-embed-text-v2": 512,
    # Other embedding models
    "mxbai-embed-large": 512,
    "all-minilm": 512,
    "bge-m3": 8192,
    "leann-bge-m3": 8192,
    "snowflake-arctic-embed": 512,
    # OpenAI models
    "text-embedding-3-small": 8192,
    "text-embedding-3-large": 8192,
    "text-embedding-ada-002": 8192,
}

# APRÈS
EMBEDDING_MODEL_LIMITS = {
    # Nomic models (common across servers)
    "nomic-embed-text": 2048,
    "nomic-embed-text-v1.5": 2048,
    "nomic-embed-text-v2": 512,
    # Other embedding models
    "mxbai-embed-large": 512,
    "all-minilm": 512,
    "bge-m3": 8192,
    "leann-bge-m3": 8192,
    "qwen3-embedding:4b": 32768,  # ← AJOUT
    "qwen3-embedding:0.6b": 32768,  # ← AJOUT (variante 0.6B)
    "qwen3-embedding": 32768,  # ← AJOUT (sans version)
    "snowflake-arctic-embed": 512,
    # OpenAI models
    "text-embedding-3-small": 8192,
    "text-embedding-3-large": 8192,
    "text-embedding-ada-002": 8192,
}
```

**Changement 2** — Ligne 989-995 (suggestions) :
```python
# AVANT
        suggested_embedding_models = [
            "leann-bge-m3",
            "nomic-embed-text",
            "mxbai-embed-large",
            "bge-m3",
            "all-minilm",
            "snowflake-arctic-embed",
        ]

# APRÈS
        suggested_embedding_models = [
            "qwen3-embedding:4b",  # ← AJOUT en premier (recommandé)
            "leann-bge-m3",
            "nomic-embed-text",
            "mxbai-embed-large",
            "bge-m3",
            "all-minilm",
            "snowflake-arctic-embed",
        ]
```

---

## Phase 3 : Reconstruction de l'index

### Étape 3.1 : Sauvegarder l'ancien index

```bash
mv ~/.leann/indexes/claude-code-sessions ~/.leann/indexes/claude-code-sessions.bge-m3.backup
mkdir -p ~/.leann/indexes/claude-code-sessions
```

### Étape 3.2 : Lancer le rebuild

```bash
cd /home/mks/projects/leann-fork
uv run python scripts/leann-index-progress.py
```

**Temps attendu** :
- Nombre de chunks : ~13 500 (actuel)
- Vitesse BGE-M3 : ~450 chunks/seconde (estimé)
- Vitesse Qwen3-4B : ~100-150 chunks/seconde (3-5× plus lent)
- **Durée totale estimée : 1.5 à 2.5 minutes**

### Étape 3.3 : Vérifier le nouvel index

```bash
cat ~/.leann/indexes/claude-code-sessions/claude_code_sessions_index.leann.meta.json | jq .
```

**Vérifications critiques :**
```json
{
  "embedding_model": "qwen3-embedding:4b",  // ✓ Bon modèle
  "dimensions": 2560,                        // ✓ Bonnes dimensions
  "total_passages": 13479,                   // ✓ Nombre de chunks cohérent
  "embedding_mode": "ollama",                // ✓ Mode correct
  "backend_kwargs": {
    "is_compact": false,                     // ✓ Mode --no-compact
    "is_recompute": false                    // ✓ Mode --no-recompute
  }
}
```

**Taille index attendue :**
```bash
du -sh ~/.leann/indexes/claude-code-sessions/
# Attendu : ~95-110 Mo (vs ~60 Mo actuellement)
# Ratio : 2.5× pour dimensions (1024 → 2560)
```

---

## Phase 4 : Validation qualitative

### Étape 4.1 : Créer un benchmark de requêtes

**Fichier** : `~/test-queries-qwen3.txt`
```
Comment j'ai implémenté l'indexation LEANN
Quelle est la configuration du thermostat
Erreur NaN Ollama flash attention
Skill init-context fonctionnement
Benchmark bge-m3 num_ctx
Migration vers Qwen3-Embedding
Warmup Ollama avant indexation
Mode --no-recompute avantages
Tâches restantes dans MEMORY.md
Comment fonctionne le MCP server LEANN
```

### Étape 4.2 : Tester les requêtes

**Via MCP (recommandé)** :
```bash
# Depuis une session Claude Code, lancer chaque requête :
/leann-search Comment j'ai implémenté l'indexation LEANN
/leann-search Erreur NaN Ollama flash attention
# etc.
```

**Via CLI Python** :
```bash
cd /home/mks/projects/leann-fork

while read query; do
  echo "=== Query: $query ==="
  uv run python apps/claude_code_rag.py --query "$query" --top-k 5
  echo ""
done < ~/test-queries-qwen3.txt | tee ~/qwen3-results.txt
```

### Étape 4.3 : Critères de validation

**✓ Succès** si :
1. Toutes les requêtes retournent des résultats (pas d'erreur)
2. Les résultats sont pertinents (vérification manuelle sur 3-5 requêtes)
3. Pas de valeurs NaN dans les scores
4. Recherche fluide dans Claude Code (latence < 500ms)

**⚠️ Rollback** si :
- Erreurs d'embedding récurrentes
- Résultats nettement moins pertinents que BGE-M3
- Crashes ou timeouts fréquents

---

## Phase 5 : Commit et documentation

### Étape 5.1 : Vérifier les changements

```bash
cd /home/mks/projects/leann-fork

git status
git diff apps/claude_code_rag.py
git diff scripts/leann-index-progress.py
git diff packages/leann-core/src/leann/embedding_compute.py
```

### Étape 5.2 : Créer le commit

```bash
git add \
  apps/claude_code_rag.py \
  scripts/leann-index-progress.py \
  packages/leann-core/src/leann/embedding_compute.py

git commit -m "feat(embedding): migrate from BGE-M3 to Qwen3-Embedding-4B

- Update default embedding model to qwen3-embedding:4b (2560 dimensions)
- Add Qwen3 token limits (32768) to model registry
- Update warmup and indexation scripts

Rationale:
- Better multilingual (French + English) and code retrieval
- 4× context window (32K vs 8K tokens)
- State-of-the-art MMTEB performance (70.58)
- No impact on search speed in --no-recompute mode

Breaking change: requires full index rebuild (1024→2560 dimensions)

Index rebuild completed: 13,479 passages in 2.1 minutes
New index size: 95 MB (vs 59 MB previously, 2.5× ratio as expected)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Étape 5.3 : Mettre à jour MEMORY.md

```bash
# Marquer la migration comme terminée dans MEMORY.md
# (déjà fait automatiquement par Claude)
```

---

## Rollback (si nécessaire)

### En cas de problème critique

```bash
# 1. Restaurer l'ancien index
rm -rf ~/.leann/indexes/claude-code-sessions
mv ~/.leann/indexes/claude-code-sessions.bge-m3.backup ~/.leann/indexes/claude-code-sessions

# 2. Restaurer le code source
cd /home/mks/projects/leann-fork
git restore apps/claude_code_rag.py
git restore scripts/leann-index-progress.py
git restore packages/leann-core/src/leann/embedding_compute.py

# 3. Vérifier le retour à BGE-M3
cat ~/.leann/indexes/claude-code-sessions/claude_code_sessions_index.leann.meta.json | jq '.embedding_model'
# Doit afficher : "leann-bge-m3"
```

---

## Optimisation future : Ajout des prompts (Phase 2)

**Si gain de qualité nécessaire** (après validation de la migration de base) :

### Option retenue : Modifier `BaseRAGExample`

**Fichier à modifier** : `apps/base_rag_example.py`

Ajouter après la ligne 130 (dans `_create_parser`) :

```python
embedding_group.add_argument(
    "--embedding-prompt-template",
    type=str,
    default=None,
    help="Prompt template for documents during indexing (e.g., 'Represent this text: ')",
)
embedding_group.add_argument(
    "--query-prompt-template",
    type=str,
    default=None,
    help="Prompt template for queries during search (e.g., 'Instruct: Retrieve...\nQuery: ')",
)
```

Puis modifier `build_index()` pour passer ces paramètres dans `embedding_options`.

**Prompts Qwen3 recommandés** :
- Build: `"Represent this text: "`
- Query: `"Instruct: Retrieve relevant Claude Code session segments\nQuery: "`

**Gain attendu** : 1-5% sur la pertinence des résultats

---

## Checklist complète

### Installation
- [ ] `ollama pull qwen3-embedding:4b`
- [ ] Vérifier modèle : `ollama list | grep qwen3`

### Code
- [ ] Modifier `apps/claude_code_rag.py:86`
- [ ] Modifier `scripts/leann-index-progress.py:29`
- [ ] Modifier `scripts/leann-index-progress.py:117`
- [ ] Modifier `packages/leann-core/src/leann/embedding_compute.py:38` (3 lignes)
- [ ] Modifier `packages/leann-core/src/leann/embedding_compute.py:989` (1 ligne)

### Index
- [ ] Sauvegarder ancien index : `mv ~/.leann/indexes/claude-code-sessions{,.bge-m3.backup}`
- [ ] Rebuild : `uv run python scripts/leann-index-progress.py`
- [ ] Vérifier meta.json (modèle, dimensions, passages)
- [ ] Vérifier taille disque (~95-110 Mo)

### Tests
- [ ] Créer fichier test-queries : `~/test-queries-qwen3.txt`
- [ ] Tester 10 requêtes via MCP ou CLI
- [ ] Valider pertinence résultats (3-5 requêtes manuelles)
- [ ] Vérifier latence < 500ms

### Git
- [ ] `git diff` (vérifier 5 lignes changées)
- [ ] `git add` (3 fichiers)
- [ ] `git commit` (message détaillé)
- [ ] Mettre à jour MEMORY.md (marquer tâches complètes)

---

## Fichiers modifiés (résumé)

| Fichier | Lignes | Changement |
|---------|--------|------------|
| `apps/claude_code_rag.py` | 86 | Nom modèle : `leann-bge-m3` → `qwen3-embedding:4b` |
| `scripts/leann-index-progress.py` | 29, 117 | Nom modèle (warmup + args) |
| `packages/leann-core/src/leann/embedding_compute.py` | 38-41, 989 | Token limit + suggestion (4 lignes) |

**Total** : 3 fichiers, 5 lignes modifiées + rebuild index

**Temps total estimé** : 10-15 minutes (installation + code + rebuild + tests)
