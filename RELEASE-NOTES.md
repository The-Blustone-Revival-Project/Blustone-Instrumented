# 2.8.0.1+15: Correct CDN table-size recovery

Corrects CDN bootstrap compression and manifest file-size compatibility. The manifest now rewrites the existing table-size field; it does not delete and re-add the same table number.

A narrowly gated pre-native migration preserves a complete second backup while retaining the earlier original backup. Only the already-released bootstrap table and manifest metadata are bundled; all other live encrypted files remain app-private. Unknown cache snapshots are left unchanged.

Validation: host LevelDB recovery with checksum verification and all 384 live entries preserved; negative control reproduces the prior bad-magic failure. Migration backup, mismatch, interruption, rollback, ancillary-file and repeat-launch tests pass; independent review passes. Native validation passed on the local replica: first repaired launch completed 139 package HTTP206 requests and persisted header/items/PVC at stamp1634683. A second same-profile launch reached Village with zero package requests and no download confirmation. Native sticky corruption is absent on both launches; wallet, cards, decks, progression and claims are preserved. Only normal AP/BP clock anchors changed between the two launches.

Only the instrumented package is affected; no app data clear or original app change. Game revival remains incomplete.
