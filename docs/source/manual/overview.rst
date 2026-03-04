Overview
========

What ScriptConfig Solves
------------------------

ScriptConfig helps you define configuration once and use it in three places:

* Python calls (kwargs / dictionaries)
* command-line interfaces
* config files (YAML / JSON)

The central design goal is a stable key/value contract across all entry points.

Choose the Right API
--------------------

For new code, use these in order:

* :class:`scriptconfig.DataConfig` for most CLIs.
* :class:`scriptconfig.ModalCLI` when you need subcommands.
* :class:`scriptconfig.SubConfig` when you need nested config trees.

For older behavior and compatibility notes, see
:doc:`manual/legacy_and_deprecated`.

Core Ideas
----------

* Defaults are declared in the class body.
* Parsing can be enabled or disabled (`argv=True` / `argv=False`).
* CLI, kwargs, and config-file updates merge into one final config object.
* Each option always has a key/value form (`--key=value`).

Recommended Reading Order
-------------------------

1. :doc:`manual/quickstart`
2. :doc:`manual/dataconfig`
3. :doc:`manual/modal_cli`
4. :doc:`manual/nested_configs`
5. :doc:`manual/behavior_controls`
