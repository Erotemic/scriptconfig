Argparse Extensions
===================

ScriptConfig builds on argparse and adds config-oriented behavior.

Key Additions
-------------

* Stable key/value configuration mapping across CLI and Python calls.
* Uniform support for `--key=value` style options.
* Optional fuzzy hyphen handling (`__fuzzy_hyphens__`).
* Built-in special options (`--config`, `--dump`, `--dumps`).
* Optional argcomplete integration through modal/data CLI parsing flow.
* Better error routing for nested modal/subparser usage.

Argcomplete
-----------

`ModalCLI.main(..., autocomplete='auto')` attempts argcomplete integration if
installed. If argcomplete is unavailable, behavior degrades gracefully in
`auto` mode.

Recommendation
--------------

For non-trivial or long-lived CLIs, define explicit `type=` on
:class:`scriptconfig.Value` fields and use strict parsing in entrypoints.
