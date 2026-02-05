# Règle : Maintenance des tâches dans MEMORY.md

## Obligation

**Tu DOIS maintenir une section `## Tâches` dans le fichier MEMORY.md du projet.**

Cette section est la source de vérité persistante pour le suivi du travail entre sessions.

## Format

```markdown
## Tâches

### <Sujet/Thème>
- [ ] Tâche à faire
- [~] Tâche en cours
- [x] Tâche terminée
```

- Utilise des **checkboxes markdown** : `- [ ]` (à faire), `- [~]` (en cours), `- [x]` (fait)
- Organise par **sujet/thème** (sous-titres `###`)
- Garde la section **compacte** : max ~30 lignes (MEMORY.md est tronqué à 200 lignes)
- Retire les tâches `[x]` terminées quand la section devient trop longue

## Quand mettre à jour

- **Début de travail** : si tu crées des `TaskCreate` internes, reflète-les dans MEMORY.md
- **Fin de tâche** : quand une tâche est terminée, coche `[x]`
- **Fin de session** : avant de terminer un travail significatif, mets à jour la section
- **Nouvelle découverte** : si tu identifies du travail à faire (TODO, bug, amélioration), ajoute-le

## Règles

- Ne duplique pas : si une tâche existe déjà, mets à jour son statut au lieu d'en créer une nouvelle
- Sois concis : un sujet de tâche = une ligne courte et actionnable
- Supprime les thèmes vides (sans tâches restantes)
- Cette mise à jour ne nécessite PAS de confirmation utilisateur — fais-le silencieusement via le tool Edit
