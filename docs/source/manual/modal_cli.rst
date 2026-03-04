Modal CLI
=========

Use :class:`scriptconfig.ModalCLI` when your application needs subcommands.

Basic Pattern
-------------

.. code:: python

    import scriptconfig as scfg


    class Build(scfg.DataConfig):
        @classmethod
        def main(cls, argv=1, **kwargs):
            config = cls.cli(argv=argv, data=kwargs)
            print('build', dict(config))


    class Deploy(scfg.DataConfig):
        @classmethod
        def main(cls, argv=1, **kwargs):
            config = cls.cli(argv=argv, data=kwargs)
            print('deploy', dict(config))


    class AppCLI(scfg.ModalCLI):
        build = Build
        deploy = Deploy


    if __name__ == '__main__':
        AppCLI.main()

Declarative Registration with `ModalValue`
-------------------------------------------

Use :class:`scriptconfig.ModalValue` to set per-command metadata.

.. code:: python

    class AppCLI(scfg.ModalCLI):
        build = scfg.ModalValue(Build, alias=['b'])
        deploy = scfg.ModalValue(Deploy, command='release', alias=['rel'])

Class attribute name is the default command when `command=` is omitted.

Nested Modals
-------------

Modal commands can themselves be modal CLIs.

.. code:: python

    class AdminCLI(scfg.ModalCLI):
        users = UsersCLI
        roles = RolesCLI

Behavior Controls
-----------------

`ModalCLI` also supports behavior flags such as `__fuzzy_hyphens__`.
For canonical definitions and recommended defaults, see
:doc:`manual/behavior_controls`.
