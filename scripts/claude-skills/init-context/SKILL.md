---
name: init-context
description: Initialize session working context - LEANN indexation, git state, project memory, session history search, remaining tasks discovery.
disable-model-invocation: true
context: fork
agent: general-purpose
model: haiku
allowed-tools: Bash, Read
---

# Init Context Agent

Initialise le contexte de travail pour une session Claude Code.
Exécute les étapes dans l'ordre. Si une étape échoue, note l'erreur et continue.

## Contexte d'exécution

- **Projet** : !`basename "$PWD"`
- **CWD** : !`echo "$PWD"`
- **Date** : !`date +%Y-%m-%d`
- **Claude dir** : !`python3 -c "import re,os; print(re.sub(r'[^a-zA-Z0-9-]', '-', os.getcwd()))"`
- **LEANN Root** : !`LEANN_PYTHON="$(dirname "$(readlink -f "$(which leann)")")/python" && "$LEANN_PYTHON" -c 'from pathlib import Path; import leann; print(Path(leann.__file__).resolve().parents[4])' 2>/dev/null || echo "NOT_INSTALLED"`

---

## Étape 1 — Indexation LEANN

**Si LEANN Root = `NOT_INSTALLED`** → note "LEANN non installé", skip étapes 1 et 4.

Sinon, lance l'indexation (timeout 600000ms) :

```bash
cd <LEANN_ROOT> && uv run python scripts/leann-index-progress.py
```

Le script gère tout automatiquement :
- Vérifie si des sessions sont à indexer
- Si rien à indexer → `"Index déjà à jour"`
- Si delta > 0 → warmup Ollama + indexation incrémentale avec progression
- Si pas d'index existant → build complet

Note le résultat affiché par le script.

## Étape 2 — Git

Vérifie si on est dans un dépôt git :

```bash
git -C <CWD> rev-parse --git-dir 2>/dev/null && echo "GIT=true" || echo "GIT=false"
```

Si GIT=true, exécute en un seul appel :

```bash
cd <CWD> && echo "=== BRANCH ===" && git branch --show-current && echo "=== LOG ===" && git log --oneline -10 && echo "=== STATUS ===" && git status --short && echo "=== DIFF STAT ===" && git diff --stat && echo "=== STASH ===" && git stash list && echo "=== UNPUSHED ===" && git log --oneline @{upstream}..HEAD 2>/dev/null || echo "(no upstream)"
```

Si GIT=false → note "Pas de dépôt git".

## Étape 3 — Mémoire projet

**OBLIGATOIRE** : Utilise le tool **Read** pour lire ce fichier. Tu n'as PAS ce fichier dans ton contexte (tu es un sous-agent isolé).

Chemin exact : `~/.claude/projects/<CLAUDE_DIR>/memory/MEMORY.md`

Où `<CLAUDE_DIR>` est la valeur injectée dans "Contexte d'exécution" ci-dessus.
Lis les 100 premières lignes.

Si le fichier n'existe pas → note "Aucune mémoire projet".
Extrais les points clés : gotchas, architecture, décisions, travail en cours.

## Étape 4 — Recherche LEANN

**Si LEANN n'est pas disponible** (étape 1 skippée) → skip, note "LEANN non disponible".

Sinon, vérifie d'abord le schéma MCP :

```bash
mcp-cli info leann-server/leann_search
```

Puis exécute UNE recherche pour retrouver le travail récent du projet.

### Stratégie de requête

- `index_name`: `"claude-code-sessions"`
- `query`: terme générique (ex: `"session"`) — `query: ""` ne fonctionne PAS
- `sort_by`: `"date_desc"` pour avoir les plus récentes en premier
- `gemma`: `0.0` (OBLIGATOIRE avec `sort_by: date_desc` pour que le tri fonctionne)
- `top_k`: `15` — important : `sort_by` est un POST-TRI sur les résultats BM25, il faut un `top_k` large pour que les résultats récents soient inclus
- `show_metadata`: `true`
- `expand_turns`: `true` pour voir le contexte complet
- `project`: nom du projet (filtrage par substring)
- `date_from`: date d'il y a 7 jours (format YYYY-MM-DD)

Synthétise les 3-5 résultats les plus récents.

## Étape 5 — Tâches restantes

Identifie les tâches non terminées en croisant toutes les sources collectées.

### 5a. Source primaire : MEMORY.md

Reprends la section `## Tâches` lue à l'étape 3 (si elle existe).
Les tâches `- [ ]` et `- [~]` sont les tâches restantes selon la mémoire projet.

### 5b. Source secondaire : extraction des sessions JSONL

**Si LEANN Root = `NOT_INSTALLED`** → skip cette sous-étape.

Sinon, lance le script d'extraction :

```bash
cd <LEANN_ROOT> && uv run python scripts/leann-extract-tasks.py --claude-dir "<CLAUDE_DIR>" --sessions 5
```

Le script retourne du JSON avec les tâches incomplètes de chaque session récente.
Note les tâches qui ne sont PAS déjà présentes dans MEMORY.md (= filet de sécurité pour sessions interrompues).

### 5c. Source complémentaire : TODO/FIXME dans le code

Si l'étape 2 a montré des fichiers modifiés (git status), cherche les TODO/FIXME dans les 5 premiers fichiers modifiés :

```bash
cd <CWD> && grep -n 'TODO\|FIXME\|HACK\|XXX' <fichier1> <fichier2> ... 2>/dev/null | head -10
```

### 5d. Vérification croisée

Pour chaque tâche restante identifiée (MEMORY.md + script + TODO), vérifie son statut réel :

| Source de vérif. | Règle |
|------------------|-------|
| **Git log** (étape 2) | Si un commit récent correspond clairement au sujet → tâche probablement terminée |
| **MEMORY.md** (étape 3) | Si documenté comme fait/implémenté dans une autre section → terminée |
| **Sessions ultérieures** | Si le `last_message_excerpt` ou `summary` d'une session plus récente mentionne la tâche comme faite → terminée |
| **Git status** (étape 2) | Si des fichiers modifiés semblent liés à une tâche `[~]` → en cours actif |
| **Git stash** (étape 2) | Si un stash existe → mentionner comme travail mis de côté |

Retire les tâches vérifiées comme terminées. Garde celles qui restent à faire.

## Étape 6 — Résumé

Retourne un résumé structuré et compact :

```
## Contexte — <PROJET> (<DATE>)

### Git
- **Branche** : ...
- **Commits récents** : (5 derniers, 1 ligne chacun)
- **État** : clean / N fichiers modifiés (résumé)
- **Non poussé** : N commits en avance sur upstream (ou rien)

### Mémoire projet
- (2-3 points clés du MEMORY.md, ou "Aucune mémoire")

### Sessions récentes
- (2-3 phrases résumant le travail récent depuis LEANN, ou "LEANN non disponible")

### Tâches restantes
- **[sujet]** (source: mémoire) — en cours / à faire
- **[sujet]** (source: session du JJ/MM) — non terminé
- **TODO fichier.py:42** — "Description du TODO"
- (ou "Aucune tâche en suspens détectée")

### Indexation
- (Statut : à jour / N sessions indexées en Xs / skippé)
```

Garde le résumé **compact** (40 lignes max). Pas de citations longues.
