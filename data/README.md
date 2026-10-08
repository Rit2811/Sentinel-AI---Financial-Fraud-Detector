# Data

The prototype uses simulated Sparkov-derived authorization events. Raw source,
labels, derived features, caches and model binaries remain Git-ignored. They are
not required for teammate runtime setup when the approved frozen package is supplied.

Raw card numbers, names, addresses and source transaction IDs must not enter
application payloads/logs. Source adapters tokenize card identity with a stable
private HMAC key; preserve that key across a given replay history. Keep labels in
their separate offline lane. Do not repeat reserved evaluation to start the app.
