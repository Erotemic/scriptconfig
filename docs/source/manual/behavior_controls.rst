Behavior Controls
=================

ScriptConfig supports class-level controls for parser behavior.

`__fuzzy_hyphens__`
-------------------

Available on both :class:`scriptconfig.DataConfig` and
:class:`scriptconfig.ModalCLI`.

When enabled, names with underscores accept hyphen variants on the CLI.
Example: `my_option` also accepts `my-option`.

Use this when you want ergonomic CLI spelling while keeping Pythonic key names.

`__allow_abbrev__`
------------------

Supported in parser configuration to control argparse abbreviation behavior.
Disable for strict, explicit CLI interfaces.

`__special_options__`
---------------------

Controls special scriptconfig options (`--config`, `--dump`, `--dumps`).
Setting it to `False` can avoid naming conflicts with your own fields.

Guidance
--------

* Prefer explicit and predictable parser behavior for automation.
* If changing controls in existing CLIs, document the behavior change in help
  text and release notes.
