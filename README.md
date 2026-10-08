# NadicodeAI Agent packages

This repository contains reviewed Agent packages for Nadia. Each directory
under `packages/` is one portable Agent Plugins v1 package. Nadia installs a
package from its directory and pins the installation to a full Git commit.

## Packages

| Package | Contents | External connections |
| --- | --- | --- |
| `research-brief` | One skill for decision-ready, source-backed research briefs | None |
| `appalti-lombardia` | One skill and its scanner for the daily report of public works tenders published on Lombardy's comuni websites; the map of the province of Bergamo's 243 comuni | The comuni's public websites |

Validate a package with the Hermes release that Nadia carries:

```text
hermes plugins validate packages/research-brief --json
```

The package is complete only when validation reports no failed check and
Hermes discovers every declared skill. A package must not contain credentials,
customer data, runtime state, or commands copied from an external source.

## Publication

The canonical private repository is `nadicodeai/plugins-hub`, which is the repository
Nadia's package installer reads. Publish reviewed changes through a pull
request. Record the resulting 40-character commit SHA in the Portal catalog;
the package version is descriptive metadata and does not replace the commit
pin.

Protect `main` with a GitHub ruleset that requires a pull request, one approval,
and resolved review conversations. Block force pushes and branch deletion.
Use the organization's existing GitHub or SSH authentication for publication;
do not create or document a repository token.
