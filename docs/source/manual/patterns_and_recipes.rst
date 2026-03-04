Patterns and Recipes
====================

Pattern: Testable Entrypoint
----------------------------

Use `argv` + `kwargs` control in `main` for both CLI and Python invocation.

.. code:: python

    @classmethod
    def main(cls, argv=1, **kwargs):
        config = cls.cli(argv=argv, data=kwargs)
        return run(config)

Pattern: Subcommand Apps
------------------------

Create one `DataConfig` per command and compose with `ModalCLI`.
Keep shared utilities outside config classes.

Pattern: Template Bootstrap
---------------------------

Use built-in templates to start new tools quickly:

.. code:: bash

    python -m scriptconfig template single Train
    python -m scriptconfig template modal Toolkit

Pattern: Config-Driven Pipelines
--------------------------------

For multi-stage systems, use :class:`scriptconfig.SubConfig` for nested nodes
and dotted overrides for leaf values.

Pattern: Explicit Casting
-------------------------

For reproducibility, define `Value(type=...)` for fields that should not rely
on smartcast heuristics.
