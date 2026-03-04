Legacy and Deprecated Features
==============================

This page collects non-primary APIs and migration notes.

Legacy `Config`
---------------

:class:`scriptconfig.Config` remains available for compatibility, but new code
should prefer :class:`scriptconfig.DataConfig`.

Migration Guidance
------------------

When moving from legacy patterns:

* migrate to class-attribute defaults in `DataConfig`
* keep explicit `Value(type=...)` annotations for critical fields
* keep entrypoint signatures compatible (`main(argv=1, **kwargs)`)

`Path` and `PathList`
---------------------

:class:`scriptconfig.Path` and :class:`scriptconfig.PathList` are available,
but are not part of the recommended core workflow. Prefer `Value(type=...)`
plus explicit path handling unless your existing code already depends on these
wrappers.

Why This Is Separate
--------------------

Primary docs focus on stable, preferred interfaces (`DataConfig`, `ModalCLI`,
`SubConfig`). This page exists to keep legacy details discoverable without
making them the default path for new users.
