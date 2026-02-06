# LEANN Search - Référence Complète

Ce document contient TOUTE la documentation nécessaire pour effectuer des recherches efficaces dans LEANN.

## Architecture LEANN

LEANN est un moteur de recherche sémantique sur les codebases indexées et l'historique des sessions Claude Code. Il utilise une recherche hybride combinant :
- **Recherche vectorielle** (sémantique) : Comprend le sens des requêtes
- **BM25** (keyword) : Correspondance exacte de termes

## Outils MCP disponibles

### 1. `leann_list`
Liste tous les index disponibles. **TOUJOURS l'appeler en premier.**

```bash
mcp-cli call leann-server/leann_list '{}'
```

### 2. `leann_search`
Recherche sémantique dans un index.

## Schéma complet des paramètres

| Paramètre | Type | Défaut | Min | Max | Description |
|-----------|------|--------|-----|-----|-------------|
| `index_name` | string | **requis** | - | - | Nom de l'index (obtenu via `leann_list`) |
| `query` | string | **requis** | - | - | Requête en langage naturel ou termes techniques |
| `top_k` | integer | 5 | 1 | 20 | Nombre de résultats |
| `complexity` | integer | 32 | 16 | 128 | Précision de recherche (32 suffit généralement) |
| `show_metadata` | boolean | false | - | - | Affiche les métadonnées (TOUJOURS activer) |
| `gemma` | number | 0.5 | 0.0 | 1.0 | Poids recherche hybride |
| `expand_turns` | boolean | false | - | - | Retourne le tour complet (sessions uniquement) |
| `project` | string | null | - | - | Filtre par nom de projet (substring match) |
| `sort_by` | string | "relevance" | - | - | Tri: 'relevance', 'date_desc', 'date_asc' |
| `date_from` | string | null | - | - | Date minimum (ISO 8601: YYYY-MM-DD) |
| `date_to` | string | null | - | - | Date maximum (ISO 8601: YYYY-MM-DD) |

## Paramètre `gemma` - Guide détaillé

Le paramètre `gemma` contrôle le mix entre recherche sémantique et keyword :

### gemma = 0.0 (BM25 pur / Keyword)
**Utiliser quand :**
- Recherche d'un terme exact, nom de fonction, variable
- Recherche de messages d'erreur spécifiques
- Correspondance de code literal

**Exemples :**
```bash
# Trouver une fonction spécifique
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "handleAuthentication", "gemma": 0.0, "show_metadata": true}'

# Trouver un message d'erreur exact
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "ECONNREFUSED 127.0.0.1:5432", "gemma": 0.0, "show_metadata": true}'
```

### gemma = 0.5 (Hybride - Défaut recommandé)
**Utiliser quand :**
- Requêtes courtes ou vagues
- Mélange de termes techniques et concepts
- Incertitude sur la formulation exacte

**Exemples :**
```bash
# Requête vague
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "auth bug", "gemma": 0.5, "show_metadata": true}'

# Mélange technique/conceptuel
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "problème performance API", "gemma": 0.5, "show_metadata": true}'
```

### gemma = 1.0 (Sémantique pur)
**Utiliser quand :**
- Questions longues et descriptives
- Recherche de concepts, pas de termes exacts
- Requêtes en langage naturel complet

**Exemples :**
```bash
# Question descriptive longue
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "Comment avons-nous résolu le problème de latence dans les requêtes de base de données?", "gemma": 1.0, "show_metadata": true}'

# Recherche conceptuelle
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "discussions sur les meilleures pratiques pour les tests unitaires", "gemma": 1.0, "show_metadata": true}'
```

## Paramètres de tri et filtrage temporel

### `sort_by` — Ordre de tri des résultats

| Valeur | Description |
|--------|-------------|
| `relevance` | Tri par score de pertinence (défaut) |
| `date_desc` | Plus récent d'abord |
| `date_asc` | Plus ancien d'abord |

⚠️ **Couplage sort_by + gemma** : `sort_by` applique un POST-TRI sur les résultats retournés par la recherche hybride. Avec `gemma=1.0` (sémantique pur), les résultats sont issus du seul index vectoriel — leur timestamp peut être distribué de manière non uniforme, rendant le tri temporel peu fiable. **Utilise `gemma=0.0` (BM25 pur) avec `sort_by=date_desc/asc`** pour un tri temporel fiable, car BM25 retourne un échantillon plus large et mieux distribué temporellement.

**Exemples :**
```bash
# Trouver les discussions les plus récentes (gemma=0.0 obligatoire)
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "session", "sort_by": "date_desc", "gemma": 0.0, "top_k": 10, "show_metadata": true}'

# Voir l'évolution chronologique d'un sujet
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "refactoring API", "sort_by": "date_asc", "gemma": 0.0, "top_k": 10, "show_metadata": true}'
```

### `date_from` / `date_to` — Filtrage par plage de dates

Format : ISO 8601 (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS)

**Exemples :**
```bash
# Résultats d'aujourd'hui uniquement
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "bug fix", "date_from": "2026-02-04", "show_metadata": true}'

# Résultats de la dernière semaine
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "deployment", "date_from": "2026-01-28", "date_to": "2026-02-04", "show_metadata": true}'

# Combiné avec tri par date
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "test", "date_from": "2026-02-01", "sort_by": "date_desc", "show_metadata": true}'
```

**Cas d'usage :**
- Trouver la dernière session sur un sujet
- Explorer l'historique d'un projet sur une période
- Filtrer les résultats aux conversations récentes

## Types d'entrées dans les sessions (`entry_type`)

⚠️ **IMPORTANT** : `entry_type` est une VALEUR dans les métadonnées des résultats, PAS un paramètre de filtrage.
Tu ne peux pas filtrer par `entry_type` dans la requête. Tu dois filtrer les résultats APRÈS la recherche.

Les index de sessions Claude Code contiennent différents types d'entrées (visibles avec `show_metadata: true`) :

### `turn` (le plus courant)
- Échanges user + assistant dans la conversation principale
- Contient le contexte complet de la discussion
- Utiliser `expand_turns=true` pour récupérer le tour complet

### `agent_turn`
- Échanges des sous-agents (Task tool)
- Travail délégué à des agents spécialisés
- Utile pour trouver des recherches/explorations passées

### `summary`
- Résumés de session générés par Claude Code
- Vue d'ensemble condensée d'une session
- Bon point de départ pour comprendre une session

### `insight`
- Blocs `★ Insight` éducatifs extraits des réponses
- Courts résumés pédagogiques
- Liés à leur tour parent via `turn_id`
- **Parfaits pour contexte rapide sans `expand_turns`**

### Comment filtrer par entry_type

```python
# Exemple : filtrer les résultats pour ne garder que les insights
results = leann_search(...)
insights_only = [r for r in results if r.metadata.get("entry_type") == "insight"]
```

## Métadonnées disponibles

Avec `show_metadata=true`, chaque résultat inclut :

| Champ | Description |
|-------|-------------|
| `source` | Chemin du fichier source |
| `session_id` | ID unique de la session |
| `project_name` | Nom du projet (pour filtrage) |
| `session_summary` | Résumé de la session |
| `message_count` | Nombre de messages dans la session |
| `turn_id` | ID du tour (pour lier insights à leurs tours) |
| `entry_type` | Type d'entrée (turn/agent_turn/summary/insight) |
| `timestamp` | Horodatage |
| `git_branch` | Branche git active |
| `model` | Modèle Claude utilisé |

## Stratégies de recherche avancées

### 1. Recherche itérative
Commence large, puis affine :
```bash
# 1. Recherche large
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "authentication", "top_k": 15, "show_metadata": true}'

# 2. Affine avec projet
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "authentication", "project": "mon-projet", "top_k": 10, "show_metadata": true}'

# 3. Explore en détail avec expand_turns
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "authentication JWT", "project": "mon-projet", "expand_turns": true, "top_k": 5, "show_metadata": true}'
```

### 2. Recherche multi-angle
Essaie différentes formulations :
```bash
# Angle technique
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "useEffect dependency array", "gemma": 0.0, "show_metadata": true}'

# Angle conceptuel
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "problème de re-render React hooks", "gemma": 1.0, "show_metadata": true}'

# Angle hybride
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "React hooks infinite loop", "gemma": 0.5, "show_metadata": true}'
```

### 3. Recherche d'insights
Pour un aperçu rapide sans charger les tours complets :
```bash
# Cherche uniquement les insights (via métadonnées)
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "testing strategies", "top_k": 10, "show_metadata": true}'
# Puis filtre manuellement les résultats avec entry_type: "insight"
```

### 4. Recherche temporelle
Utilise les paramètres `sort_by`, `date_from`, `date_to` :
```bash
# Dernière session sur un sujet
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "mon sujet", "sort_by": "date_desc", "top_k": 1, "expand_turns": true, "show_metadata": true}'

# Discussions de la semaine dernière
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "refactoring", "date_from": "2026-01-28", "date_to": "2026-02-03", "show_metadata": true}'

# Évolution chronologique
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "architecture API", "sort_by": "date_asc", "top_k": 15, "show_metadata": true}'
```

## Paramètre `top_k` - Guide

| Valeur | Usage |
|--------|-------|
| 3-5 | Réponses ciblées, questions précises |
| 5-10 | Exploration modérée |
| 10-15 | Exploration large, découverte |
| 15-20 | Recherche exhaustive |

## Paramètre `complexity` - Guide

| Valeur | Usage |
|--------|-------|
| 16 | Recherches simples, rapides |
| 32 | Défaut, bon équilibre (recommandé) |
| 64 | Haute précision, index larges |
| 128 | Rappel maximum, coûteux |

## Guide `expand_turns` — Coûts et bénéfices

| Mode | Taille résultat | Quand utiliser |
|------|----------------|----------------|
| `expand_turns=false` | ~500 car./résultat (chunk) | Exploration rapide, survol, beaucoup de résultats |
| `expand_turns=true` | ~2-5 Ko/résultat (turn complet) | Contexte complet nécessaire (question+réponse+code) |
| `entry_type=insight` (post-filtre) | ~200 car./résultat | Aperçu pédagogique rapide, pas besoin de expand |

**Règle** : Commence sans `expand_turns`, active-le seulement si les chunks manquent de contexte.

**Déduplication** : Avec `expand_turns=true`, les chunks d'un même turn sont fusionnés (via `turn_id`). Le nombre de résultats peut être inférieur à `top_k`.

## Bonnes pratiques

1. **TOUJOURS `show_metadata=true`** - Les métadonnées sont essentielles
2. **Commencer par `leann_list`** - Découvre les index disponibles
3. **Ajuster `gemma` selon la requête** - Pas de one-size-fits-all
4. **`gemma=0.0` obligatoire avec `sort_by`** - Le tri temporel repose sur BM25
5. **`expand_turns` avec parcimonie** - Augmente la taille, utile seulement quand le contexte complet est nécessaire
6. **Filtrer par `project`** quand pertinent - Réduit le bruit (substring match)
7. **Faire plusieurs recherches** - Angles différents = meilleurs résultats

## Exemples de requêtes types

```bash
# "Comment ai-je implémenté X ?"
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "implémentation de X", "gemma": 1.0, "expand_turns": true, "top_k": 5, "show_metadata": true}'

# "Trouve le code qui fait Y"
mcp-cli call leann-server/leann_search '{"index_name": "INDEX", "query": "fonction Y", "gemma": 0.0, "top_k": 10, "show_metadata": true}'

# "Quelles discussions sur Z ?"
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "discussion Z", "gemma": 0.5, "top_k": 15, "show_metadata": true}'

# "Insights sur les tests"
mcp-cli call leann-server/leann_search '{"index_name": "claude-code-sessions", "query": "testing best practices insights", "gemma": 1.0, "top_k": 10, "show_metadata": true}'
```
