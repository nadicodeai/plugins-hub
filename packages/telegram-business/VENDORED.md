# Vendored

- Upstream: https://github.com/NousResearch/hermes-telegram-business
- Commit: `e905f3bc5eeaa5a9dab9bc5155601b3ebec75757`
- Licence: MIT (`LICENSE`, unchanged from upstream)
- Changes: none. Every upstream file is copied as it is at that commit; this
  file and `catalog.yaml` are the only additions.

The plugin needs Hermes's `register_telegram_handler` (an alias of
`register_platform_handler("telegram", …)`), which the Hermes tree Nadia
carries provides. To take a newer upstream version, replace every upstream
file with the new commit's copy and update the commit above.
