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
    cfg = TrainConfig.cli(argv=['--optim.lr=0.02'], allow_subconfig_overrides=True)
    assert cfg.optim.lr == pytest.approx(0.02)


def test_selector_via_dunder_class_and_sugar():
    cfg = TrainConfig.cli(
        argv=['--optim.__class__=sgd', '--optim.momentum=0.7'],
        allow_subconfig_overrides=True,
    )
    assert isinstance(cfg.optim, SGDConfig)
    assert cfg.optim.momentum == pytest.approx(0.7)

    cfg2 = TrainConfig.cli(argv=['--optim=sgd', '--optim.momentum=0.5'], allow_subconfig_overrides=True)
    assert isinstance(cfg2.optim, SGDConfig)
    assert cfg2.optim.momentum == pytest.approx(0.5)


def test_nested_selector_and_deep_leaves():
    cfg = TrainConfig.cli(argv=[
        '--model=seg',
        '--model.backbone=vit',
        '--model.backbone.patch=16',
    ], allow_subconfig_overrides=True)
    assert isinstance(cfg.model, SegformerConfig)
    assert isinstance(cfg.model.backbone, BackboneConfig)
    assert cfg.model.backbone.patch == 16


def test_variant_aware_help(capsys):
    with pytest.raises(SystemExit):
        TrainConfig.cli(argv=['--model=seg', '--help'], allow_subconfig_overrides=True)
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
    cfg = TrainConfig.cli(
        data=kw_overrides,
        argv=['--config', str(cfg_path), *cli_overrides],
        allow_subconfig_overrides=True,
    )
    assert isinstance(cfg.optim, SGDConfig)
    assert cfg.optim.lr == pytest.approx(0.2)
    assert cfg.epochs == 12


def test_unknown_key_error():
    with pytest.raises(KeyError):
        TrainConfig.cli(argv=['--optim.unknown=1'], allow_subconfig_overrides=True)


def test_reserved_class_name_error():
    with pytest.raises(ValueError):
        class BadConfig(scfg.DataConfig):
            __default__ = {'__class__': 1}


def test_dotted_access_for_config_and_dataconfig():
    class Inner(scfg.Config):
        __default__ = {'leaf': 1}

    class Outer(scfg.Config):
        __default__ = {'inner': Inner()}

    cfg = Outer()
    cfg['inner.leaf'] = 5
    assert cfg['inner.leaf'] == 5
    assert cfg.inner.leaf == 5

    class InnerDC(scfg.DataConfig):
        leaf = 1

    class OuterDC(scfg.DataConfig):
        inner = InnerDC()

    dcfg = OuterDC()
    dcfg['inner.leaf'] = 9
    assert dcfg['inner.leaf'] == 9
    assert dcfg.inner.leaf == 9


def test_dump_and_load_roundtrip(tmp_path):
    class ChoiceA(scfg.DataConfig):
        x = 1

    class ChoiceB(scfg.DataConfig):
        x = 2

    class Outer(scfg.Config):
        __default__ = {
            'inner': scfg.SubConfig(ChoiceA, choices={'a': ChoiceA, 'b': ChoiceB}),
            'root': 3,
        }

    cfg = Outer.cli(argv=['--inner=b', '--inner.x=10'], allow_subconfig_overrides=True)
    out_path = tmp_path / 'cfg.yaml'
    with open(out_path, 'w') as file:
        cfg.dump(stream=file)

    cfg2 = Outer()
    cfg2.load(out_path, cmdline=False)
    assert isinstance(cfg2['inner'], ChoiceB)
    assert cfg2['inner'].x == 10
    assert cfg2['root'] == 3


def test_subconfig_overrides_disabled(capsys):
    cfg = TrainConfig.cli(argv=['--optim.beta1=0.3'], allow_subconfig_overrides=False)
    assert cfg.optim.beta1 == pytest.approx(0.3)

    with pytest.raises(SystemExit):
        TrainConfig.cli(argv=['--optim=sgd'], allow_subconfig_overrides=False)
    err = capsys.readouterr().err
    assert 'allow_subconfig_overrides=True' in err
    with pytest.raises(SystemExit):
        TrainConfig.cli(argv=['--optim.__class__=sgd'], allow_subconfig_overrides=False)


def test_subconfig_class_in_dict():
    cfg = TrainConfig.cli(argv=[], allow_subconfig_overrides=False)
    data = cfg.to_dict()
    assert data['optim']['__class__'] == 'adam'
    assert data['model']['__class__'] == 'base'
