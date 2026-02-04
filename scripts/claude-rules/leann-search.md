# Règle LEANN Search - Obligatoire

## Recherches LEANN - TOUJOURS déléguer

**OBLIGATOIRE : Utiliser le skill `/leann-search` pour TOUTE recherche dans LEANN.**

### Pourquoi ?
- Économise le contexte principal en déléguant à un sous-agent
- Le sous-agent a accès à la documentation complète des paramètres
- Évite de polluer la conversation avec les résultats bruts

### Déclencheurs
Invoquer `/leann-search` quand l'utilisateur demande :
- "cherche dans mes sessions"
- "trouve comment j'ai fait X"
- "quels insights sur Y"
- "recherche dans LEANN"
- "dans l'historique des conversations"
- Toute question sur l'historique des sessions Claude Code

### Interdit
- Ne JAMAIS appeler `mcp-cli call leann-server/leann_search` directement
- Ne JAMAIS charger les résultats LEANN bruts dans le contexte principal
