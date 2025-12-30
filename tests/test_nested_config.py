import textwrap

import pytest

import scriptconfig as scfg


class SGDConfig(scfg.DataConfig):
    lr = scfg.Value(0.01, type=float)
    momentum = scfg.Value(0.9, type=float)


class AdamConfig(scfg.DataConfig):
    lr = scfg.Value(0.001, type=float)
    beta1 = scfg.Value(0.9, type=float)


class BackboneConfig(scfg.DataConfig):
    patch = scfg.Value(4, type=int)


class SegformerConfig(scfg.DataConfig):
    backbone = scfg.SubConfig(BackboneConfig, choices={'vit': BackboneConfig})
    heads = 1


class ModelConfig(scfg.DataConfig):
    name = 'base'


class TrainConfig(scfg.DataConfig):
    optim = scfg.SubConfig(AdamConfig, choices={'adam': AdamConfig, 'sgd': SGDConfig})
    model = scfg.SubConfig(ModelConfig, choices={'base': ModelConfig, 'seg': SegformerConfig})
    epochs = scfg.Value(10, type=int)


def test_flat_fastpath():
    class FlatConfig(scfg.DataConfig):
        foo = 1

    cfg = FlatConfig.cli(argv=['--foo', '3'])
    assert cfg.foo == 3
    assert not cfg._has_subconfigs


def test_nested_leaf_override_via_cli():
    cfg = TrainConfig.cli(argv=['--optim.lr=0.02'])
    assert cfg.optim.lr == pytest.approx(0.02)


def test_selector_via_dunder_class_and_sugar():
    cfg = TrainConfig.cli(argv=['--optim.__class__=sgd', '--optim.momentum=0.7'])
    assert isinstance(cfg.optim, SGDConfig)
    assert cfg.optim.momentum == pytest.approx(0.7)

    cfg2 = TrainConfig.cli(argv=['--optim=sgd', '--optim.momentum=0.5'])
    assert isinstance(cfg2.optim, SGDConfig)
    assert cfg2.optim.momentum == pytest.approx(0.5)


def test_nested_selector_and_deep_leaves():
    cfg = TrainConfig.cli(argv=[
        '--model=seg',
        '--model.backbone=vit',
        '--model.backbone.patch=16',
    ])
    assert isinstance(cfg.model, SegformerConfig)
    assert isinstance(cfg.model.backbone, BackboneConfig)
    assert cfg.model.backbone.patch == 16


def test_variant_aware_help(capsys):
    with pytest.raises(SystemExit):
        TrainConfig.cli(argv=['--model=seg', '--help'])
    out = capsys.readouterr().out
    assert 'model.backbone.patch' in out


def test_precedence_default_file_kwargs_cli(tmp_path):
    cfg_path = tmp_path / 'train.yaml'
    cfg_text = textwrap.dedent(
        '''
        optim:
            __class__: sgd
            lr: 0.2
        epochs: 5
        '''
    )
    cfg_path.write_text(cfg_text)
    kw_overrides = {'epochs': 8}
    cli_overrides = ['--epochs=12']
    cfg = TrainConfig.cli(data=kw_overrides, argv=['--config', str(cfg_path), *cli_overrides])
    assert isinstance(cfg.optim, SGDConfig)
    assert cfg.optim.lr == pytest.approx(0.2)
    assert cfg.epochs == 12


def test_unknown_key_error():
    with pytest.raises(KeyError):
        TrainConfig.cli(argv=['--optim.unknown=1'])


def test_reserved_class_name_error():
    with pytest.raises(ValueError):
        class BadConfig(scfg.DataConfig):
            __default__ = {'__class__': 1}
