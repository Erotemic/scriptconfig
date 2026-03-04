import scriptconfig as scfg
import ubelt as ub


class OptimizerConfig(scfg.Config):
    __default__ = dict(
        lr=scfg.Value(0.01, type=float),
    )


class SGDConfig(OptimizerConfig):
    __default__ = dict(
        momentum=scfg.Value(0.9, type=float),
    )


class AdamConfig(OptimizerConfig):
    __default__ = dict(
        beta1=scfg.Value(0.9, type=float),
    )


class MuonConfig(OptimizerConfig):
    __default__ = dict(
        ns_coefficients=scfg.Value((3.4445, -4.775, 2.0315), type="smartcast:v1"),
    )


class TrainConfig(scfg.Config):
    __default__ = dict(
        # optim = scfg.SubConfig(SGDConfig, choices={'adam': AdamConfig, 'sgd': SGDConfig}),
        model=scfg.Value("vit", choices=["vit", "resnet50"]),
        epochs=scfg.Value(10, type=int),
    )


def test_python_usage():
    TrainConfig({"optim": "adam"})

    config = TrainConfig()

    ...


def main():
    cases = [
        {"argv": "--optim=sgd"},
        {"argv": "--optim=adam"},
        {"argv": "--optim=sgd --optim.lr=3e-3"},
        {"argv": "--optim=adam  --optim.lr=3e-3"},
        # {'argv': '--optim=MuonConfig  --optim.lr=3e-3 --dumps'},
        {"argv": "--optim.momentum=0.88"},
        {"argv": '--config "{model: resnet50, optim.momentum: 0.88}"'},
        {"argv": '--config "{model: resnet50, optim: {momentum: 0.88}}"'},
        {"argv": '--config "{model: resnet50, optim: adam, optim.beta1: 0.88}"'},
        {
            "argv": '--config "{model: resnet50, optim.__class__: adam, optim.beta1: 0.88}"'
        },
        {"argv": '--config "{model: resnet50, optim: {__class__: adam, beta1: 0.88}}"'},
    ]

    for case in cases:
        print("---")
        print(f"case = {ub.urepr(case, nl=1)}")
        config = TrainConfig.cli(argv=case["argv"], verbose=True, allow_import=True)
        config_dict = config.to_dict()
        print(f"config_dict = {ub.urepr(config_dict, nl=1)}")


if __name__ == "__main__":
    """
    CommandLine:
        python ~/code/scriptconfig/examples/subconfig-simple.py
    """
    main()
