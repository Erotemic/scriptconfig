Quickstart
==========

Minimal `DataConfig` CLI
------------------------

.. code:: python

    import scriptconfig as scfg


    class TrainConfig(scfg.DataConfig):
        """Train a model."""
        lr = scfg.Value(1e-3, type=float, help='learning rate')
        epochs = scfg.Value(10, type=int, help='number of epochs')


    def main(argv=1, **kwargs):
        config = TrainConfig.cli(argv=argv, data=kwargs)
        print(dict(config))


    if __name__ == '__main__':
        main()

CLI use:

.. code:: bash

    python train.py --lr=0.01 --epochs=20

Programmatic use (no CLI parsing):

.. code:: python

    main(argv=False, lr=0.02, epochs=5)

Generate a Starter Script
-------------------------

ScriptConfig includes a template helper CLI:

.. code:: bash

    python -m scriptconfig template single MyTool
    python -m scriptconfig template modal MyApp

See :doc:`manual/patterns_and_recipes` for template-based workflows.

Next Steps
----------

* :doc:`manual/dataconfig` for full configuration patterns.
* :doc:`manual/modal_cli` for subcommands.
* :doc:`manual/nested_configs` for hierarchical configs.
