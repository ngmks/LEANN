---
name: leann-search
description: Recherche sémantique dans l'historique des sessions Claude Code et codebases indexées.
argument-hint: "[query]"
context: fork
agent: general-purpose
allowed-tools: Bash(mcp-cli *)
---

# LEANN Search Agent

Agent de recherche sémantique multi-projet.

## Ta tâche

**$ARGUMENTS**

## Contexte d'exécution

- **Date** : !`date +%Y-%m-%d`
- **Projet courant** : !`basename "$PWD"`
- **Index disponibles** : !`mcp-cli call leann-server/leann_list '{}' 2>/dev/null | jq -r '.content[0].text' | grep -E "• 📄|claude-code-sessions" | head -5`

## ⚠️ BUDGET D'APPELS (NON NÉGOCIABLE)

```
┌─────────────────────────────────────────┐
│  1 × mcp-cli info (schéma)              │
│  1 × leann_search (UNE SEULE recherche) │
│  ────────────────────────────────────── │
│  TOTAL: 2 appels maximum                │
└─────────────────────────────────────────┘
```

Si ta première recherche ne donne pas de résultats, **reformule mentalement** puis fais UNE deuxième tentative. Pas plus.

### Stratégie de requête (IMPORTANT)

**Pour "dernière session" ou recherche temporelle** :
- ⚠️ `query: ""` NE FONCTIONNE PAS — utilise un terme générique
- Utilise `query: "session"` + `sort_by: "date_desc"` + `gemma: 0.0`
- `gemma: 0.0` est OBLIGATOIRE pour que le tri par date fonctionne correctement

```json
{"index_name": "claude-code-sessions", "query": "session", "gemma": 0.0, "sort_by": "date_desc", "top_k": 1, "show_metadata": true, "expand_turns": true}
```

**Pour recherche thématique** ("comment j'ai fait X") :
- Utilise des mots-clés pertinents dans `query`
- `gemma: 1.0` pour questions longues/descriptives
- `gemma: 0.5` (défaut) pour mots-clés courts

### Choix de l'index

| Type de recherche | Index |
|-------------------|-------|
| Sessions/historique | `claude-code-sessions` |
| Code d'un projet | Voir index injectés ci-dessus |

### Paramètres requis

```json
{
  "index_name": "claude-code-sessions",
  "query": "...",
  "show_metadata": true,
  "expand_turns": true
}
```

### Paramètres optionnels selon contexte

| Paramètre | Quand l'utiliser |
|-----------|------------------|
| `sort_by: "date_desc"` | Recherche temporelle ("dernière", "récent") |
| `top_k: 1` | "La dernière session" |
| `top_k: 5-10` | Exploration d'un sujet |
| `project: "..."` | Filtrer par projet |
| `date_from: "YYYY-MM-DD"` | Limiter à une période |
| `gemma: 1.0` | Question longue/descriptive |
| `gemma: 0.0` | Terme exact (fonction, erreur) |

### Ce qu'il ne faut PAS faire

❌ Appeler `leann_list` (les index sont déjà injectés ci-dessus)
❌ Faire plusieurs recherches "pour explorer"
❌ Utiliser `entry_type` comme paramètre (c'est une métadonnée, pas un filtre)
❌ Oublier `show_metadata: true`

## Métadonnées dans les résultats

Les résultats contiennent :
- `entry_type` : "turn" | "agent_turn" | "summary" | "insight"
- `project_name`, `session_id`, `timestamp`, `git_branch`

**Note** : Pour filtrer par `entry_type`, fais-le APRÈS la recherche sur les résultats.

## Format de réponse

1. **Résumé** (2-3 phrases)
2. **Sources** (tableau : session_id, projet, date)
3. **Extraits clés** (citations)
4. **Suggestions** (si pertinent)

Référence complète : [reference.md](reference.md)
