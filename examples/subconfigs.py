import scriptconfig as scfg
import ubelt as ub


class OptimizerConfig(scfg.DataConfig):
    lr = scfg.Value(0.01, type=float)


class SGDConfig(OptimizerConfig):
    momentum = scfg.Value(0.9, type=float)


class AdamConfig(OptimizerConfig):
    beta1 = scfg.Value(0.9, type=float)


class MuonConfig(OptimizerConfig):
    ns_coefficients = scfg.Value((3.4445, -4.775, 2.0315), type='smartcast:v1')


class BackboneConfig(scfg.DataConfig):
    patch = scfg.Value(4, type=int)


class SegformerConfig(scfg.DataConfig):
    backbone = scfg.SubConfig(BackboneConfig, choices={'vit': BackboneConfig})
    heads = 1


class ModelConfig(scfg.DataConfig):
    name = 'base'


class TrainConfig(scfg.DataConfig):
    optim = scfg.SubConfig(AdamConfig, choices={'adam': AdamConfig, 'sgd': SGDConfig})
    # optim = scfg.SubConfig(AdamConfig)
    model = scfg.SubConfig(ModelConfig, choices={'base': ModelConfig, 'seg': SegformerConfig})
    epochs = scfg.Value(10, type=int)


def main():
    cases = [
        {'argv': '--optim=sgd'},
        {'argv': '--optim=MuonConfig'},
    ]

    for case in cases:
        print('---')
        print(f'case = {ub.urepr(case, nl=1)}')
        config = TrainConfig.cli(argv=case['argv'], verbose=True, allow_import=True)
        config_dict = config.to_dict()
        print(f'config_dict = {ub.urepr(config_dict, nl=1)}')


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/scriptconfig/examples/subconfigs.py
    """
    main()
