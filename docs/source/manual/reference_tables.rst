Reference Tables
================

Core Classes
------------

+---------------------------+---------------------------------------------+
| Class                     | Purpose                                     |
+===========================+=============================================+
| ``DataConfig``            | Preferred declarative config + CLI class    |
+---------------------------+---------------------------------------------+
| ``ModalCLI``              | Subcommand router / command group           |
+---------------------------+---------------------------------------------+
| ``ModalValue``            | Declarative modal command metadata wrapper  |
+---------------------------+---------------------------------------------+
| ``SubConfig``             | Nested selectable config nodes              |
+---------------------------+---------------------------------------------+
| ``Value`` / ``Flag``      | Field metadata and behavior control         |
+---------------------------+---------------------------------------------+

Common Controls
---------------

+-------------------------+-----------------------------------------------+
| Control                 | Effect                                        |
+=========================+===============================================+
| ``__fuzzy_hyphens__``   | Allow underscore-name options as hyphen form  |
+-------------------------+-----------------------------------------------+
| ``__allow_abbrev__``    | Enable/disable argparse abbreviation behavior  |
+-------------------------+-----------------------------------------------+
| ``__special_options__`` | Enable/disable ``--config/--dump/--dumps``    |
+-------------------------+-----------------------------------------------+

See :doc:`manual/behavior_controls` for details.
