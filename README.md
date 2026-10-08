# NadicodeAI Agent packages

This repository contains reviewed Agent plugins for Nadia. Every directory
under `packages/` is one plugin, and the Portal syncs every one of them into
its Library: within 15 minutes of a merge to `main`, each folder appears (or
changes, or leaves) in the Library at the new commit. A folder the Portal
cannot read keeps the entry it had, and the sync lists the file to fix.

## Packages

| Package | Kind | Contents | External connections |
| --- | --- | --- | --- |
| `research-brief` | portable | One skill for decision-ready, source-backed research briefs | None |
| `agent-mail-gateway` | portable, vendored | The `agent-mail` skill for an Agent's own mailbox | An Agent Mail Gateway MCP server, configured in Hermes as `mail` |
| `telegram-business` | native Hermes, vendored | Drafts replies to Telegram Business customers; the owner approves each one | A Telegram bot with Business Mode, and a Telegram Business account |

A vendored package carries a `VENDORED.md` naming its upstream repository and
commit, and the upstream licence. Vendor only code under MIT, Apache-2.0 or BSD.

## A package folder

The folder's name is the plugin's name: lowercase letters, digits and dashes,
at most 64 characters. A folder is one of two kinds:

- Portable (Agent Plugins v1): a `plugin.json` whose `$schema` is
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` and whose `name`
  equals the folder. It holds only `$schema`, `name`, `version`,
  `description`, `author` (`name`, `email`, `url`), `homepage`, `repository`,
  `license`, `keywords` and `extensions`. Optional `skills/<skill>/SKILL.md`
  and `mcp.json`.
- Native Hermes: a `plugin.yaml` whose `name` equals the folder, with
  `description`, `author`, `provides_tools` and `requires_env`, beside its
  Python code.

## The Library card: `catalog.yaml`

A folder may carry a `catalog.yaml` with how the Library shows it. Every key
is optional and no other key is accepted:

```yaml
title: { en: "Telegram secretary", it: "Segretaria su Telegram" }   # at most 60 characters each
description: { en: "One sentence.", it: "Una frase." }              # at most 300 characters each
category: messaging   # sales finance office email calendar documents people legal messaging voice web other
icon: send            # book-open briefcase calculator calendar file-check file-search file-text globe inbox landmark languages list-checks mail message-circle mic notebook-pen phone presentation receipt scale send shield-check sparkles truck users wallet
audience: everyone    # or chosen: arrives visible to no company until staff choose which
```

Without a card the Library titles the plugin after its folder and describes
it with the manifest's `description`.

## Validate

Validate a package with the Hermes release that Nadia carries:

```text
hermes plugins validate packages/<name> --json
```

The package is complete only when validation reports no failed check and
Hermes discovers every declared skill. A package must not contain credentials,
customer data, runtime state, or commands copied from an external source.

## Publication

The canonical private repository is `nadicodeai/plugins-hub`, which is the
repository the Portal's Library and Nadia's package installer read. Publish
reviewed changes through a pull request. Nadia pins each installation to the
40-character commit the Library entry was published at; the package version is
descriptive metadata and does not replace the commit pin.

`main` is protected by a GitHub ruleset that requires a pull request, one
approval, and resolved review conversations, and blocks force pushes and
branch deletion. Use the organization's existing GitHub or SSH authentication
for publication; do not create or document a repository token.
