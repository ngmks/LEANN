# LEANN Add — Activer l'indexation automatique pour ce projet

Ajoute le projet courant à la whitelist LEANN et configure le hook `SessionStart`
pour l'indexation automatique des sessions Claude Code.

## Instructions

1. Dériver le chemin LEANN_ROOT depuis l'installation pipx :
   ```bash
   LEANN_PYTHON="$(dirname "$(readlink -f "$(which leann)")")/python"
   LEANN_ROOT="$("$LEANN_PYTHON" -c 'from pathlib import Path; import leann; print(Path(leann.__file__).resolve().parents[4])')"
   ```

2. Exécuter le script whitelist :
   ```bash
   python3 "$LEANN_ROOT/scripts/leann-whitelist.py" add
   ```

3. Confirmer le résultat à l'utilisateur et l'informer :
   **« Relancez Claude Code (`/exit` puis `claude`) pour que l'indexation automatique soit active. »**
