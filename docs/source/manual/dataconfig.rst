DataConfig
==========

`DataConfig` is the preferred API for new scriptconfig CLIs.

Declaring Options
-----------------

You can declare defaults directly or with :class:`scriptconfig.Value` metadata.

.. code:: python

    import scriptconfig as scfg


    class Example(scfg.DataConfig):
        """Example CLI."""
        name = 'world'
        count = scfg.Value(1, type=int, help='number of repeats')
        verbose = scfg.Flag(False, help='enable verbose output')

Parsing and Invocation
----------------------

Use `cli()` to construct and update the config.

.. code:: python

    config = Example.cli(argv=True)            # parse sys.argv
    config = Example.cli(argv=['--count=2'])   # parse explicit argv list
    config = Example.cli(argv=False, data={'count': 3})

In application entrypoints:

.. code:: python

    @classmethod
    def main(cls, argv=1, **kwargs):
        config = cls.cli(argv=argv, data=kwargs, strict=True)

Merge Precedence
----------------

The effective config is merged in this order:

* class defaults
* config file (`--config` / `config=`)
* explicit `data`/kwargs
* CLI values

Option Forms
------------

For every option, ScriptConfig preserves key/value invocation:

* `--count=3`
* `--count 3`

If an option is positional, keyword form is still available.

Typing and Smartcast
--------------------

By default, scriptconfig smartcasts string inputs. For predictable behavior,
set explicit `type=...` on :class:`scriptconfig.Value`.

See :doc:`manual/argparse_extensions` and :doc:`manual/behavior_controls` for
fuzzy hyphens and parser controls.
