# base.py — AbstractStore Protocol (Round 3 实现)
# See SPEC v2.0 §5.3
#
# Note: CoreStore and RecallStore have different enough interfaces
# (JSON flat file vs SQLite+FTS5) that a shared Protocol adds complexity
# without clear benefit at v0.1. If a common interface is needed later
# (e.g. for generic storage routing), a Protocol can be extracted then.
