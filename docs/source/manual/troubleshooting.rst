Troubleshooting
===============

Unrecognized arguments
----------------------

* Verify option names and aliases.
* Confirm strict mode (`strict=True`) expectations.
* For nested modals, check that a command was provided at each level.

Unexpected type conversion
--------------------------

If string values are being smartcast unexpectedly, set explicit field types:

.. code:: python

    item = scfg.Value('a,b,c', type=str)

Alias or naming conflicts
-------------------------

* Check overlaps between command names, aliases, and field names.
* If needed, disable fuzzy behavior (`__fuzzy_hyphens__ = 0`).

Conflicts with special options
------------------------------

If your config has fields named `config`, `dump`, or `dumps`, set
`__special_options__ = False`.
