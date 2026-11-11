# Requests

Saved API requests used for manual testing, exploration and the agents' runtime validation against the local instance.

- Prefer `.http` files (plain text, one request block per endpoint, with `{{baseUrl}}` and `{{token}}` variables): humans run them from the editor, and agents read them to build the request they send to the local instance. Postman/Insomnia collections are fine when the team already uses them.
- Keep requests in sync with the API as endpoints change - a stale collection is worse than none. Agents list new or changed endpoints in `needs_docs`, and the documentation pass updates this folder.
- Name files after the API/service they cover, e.g. `<service-name>.http`.
- Never store real credentials or tokens here; reference the dev/seed user from the root `CLAUDE.md` `Local runtime` section.
