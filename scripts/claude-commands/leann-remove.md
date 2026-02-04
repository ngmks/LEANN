# LEANN Remove — Désactiver l'indexation automatique pour ce projet

Retire le projet courant de la whitelist LEANN et supprime le hook `SessionStart`.
Les données déjà indexées restent disponibles pour la recherche MCP.

## Instructions

1. Dériver le chemin LEANN_ROOT depuis l'installation pipx :
   ```bash
   LEANN_PYTHON="$(dirname "$(readlink -f "$(which leann)")")/python"
   LEANN_ROOT="$("$LEANN_PYTHON" -c 'from pathlib import Path; import leann; print(Path(leann.__file__).resolve().parents[4])')"
   ```

2. Exécuter le script whitelist :
   ```bash
   python3 "$LEANN_ROOT/scripts/leann-whitelist.py" remove
   ```

3. Confirmer le résultat à l'utilisateur et l'informer :
   **« Relancez Claude Code pour que la désactivation prenne effet. Les données déjà indexées restent consultables via la recherche MCP. »**
