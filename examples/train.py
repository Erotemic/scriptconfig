import scriptconfig as scfg

class Adam(scfg.DataConfig):
    lr = 1e-3
    beta1 = 0.9

class Sgd(scfg.DataConfig):
    lr = 1e-2
    momentum = 0.9

class TrainCfg(scfg.DataConfig):
    optim = Adam
    epochs = scfg.Value(10, type=int)

if __name__ == '__main__':
    config = TrainCfg.cli()
    print(f'config={config}')
