import matplotlib.pyplot as plt
import numpy as np
import theano
import theano.tensor as T

from nn.ActivationLayer import ActivationLayer
from nn.HiddenLayer import HiddenLayer
from nn.Conv1DLayer import Conv1DLayer
from nn.Pool1DLayer import Pool1DLayer
from nn.NoiseLayer import NoiseLayer
from nn.BatchNormLayer import BatchNormLayer
from nn.DropoutLayer import DropoutLayer
from nn.Network import Network, AutoEncodingNetwork, InverseNetwork
from nn.AdversarialAdamTrainer import AdversarialAdamTrainer
from nn.ReshapeLayer import ReshapeLayer

from nn.AnimationPlotLines import animation_plot

from tools.utils import load_cmu, load_cmu_small, load_locomotion

rng = np.random.RandomState(23455)

shared = lambda d: theano.shared(d, borrow=True)

dataset, std, mean = load_locomotion(rng)
E = shared(dataset[0][0])

BATCH_SIZE = 40

generatorNetwork = Network(
    DropoutLayer(rng, 0.15),
    HiddenLayer(rng, (800, 64*30)),
    BatchNormLayer(rng, (800, 64*30)),
    ActivationLayer(rng, f='elu'),
    ReshapeLayer(rng, (BATCH_SIZE, 64, 30)),

    InverseNetwork(Pool1DLayer(rng, (2,), (BATCH_SIZE, 64, 60))),
    DropoutLayer(rng, 0.15),    
    Conv1DLayer(rng, (64, 64, 25), (BATCH_SIZE, 64, 60)),
    ActivationLayer(rng, f='elu'),

    InverseNetwork(Pool1DLayer(rng, (2,), (BATCH_SIZE, 64, 120))),
    DropoutLayer(rng, 0.25),  
    Conv1DLayer(rng, (64, 64, 25), (BATCH_SIZE, 64, 120)),
    ActivationLayer(rng, f='elu'),

    InverseNetwork(Pool1DLayer(rng, (2,), (BATCH_SIZE, 64, 240))),
    DropoutLayer(rng, 0.25),    
    Conv1DLayer(rng, (66, 64, 25), (BATCH_SIZE, 64, 240)),
    ActivationLayer(rng, f='elu'),
)

discriminatorNetwork = Network(
    DropoutLayer(rng, 0.15),    
    Conv1DLayer(rng, (64, 66, 25), (BATCH_SIZE * 2, 66, 240)),
    ActivationLayer(rng, f='elu'),
    Pool1DLayer(rng, (2,), (BATCH_SIZE * 2, 64, 240)),

    DropoutLayer(rng, 0.25),    
    Conv1DLayer(rng, (128, 64, 25), (BATCH_SIZE * 2, 64, 120)),
    ActivationLayer(rng, f='elu'),
    Pool1DLayer(rng, (2,), (BATCH_SIZE * 2, 128, 120)),
    
    ReshapeLayer(rng, (BATCH_SIZE * 2, 128*60)),
    DropoutLayer(rng, 0.25),    
    HiddenLayer(rng, (128*60, 1)),
    BatchNormLayer(rng, (128*60, 1)),
)

def generative_cost(disc_fake_out):
    return T.nnet.binary_crossentropy(disc_fake_out, np.ones(1, dtype=theano.config.floatX)).mean()

def discriminative_cost(disc_fake_out, disc_real_out):
    disc_cost = T.nnet.binary_crossentropy(disc_fake_out, np.zeros(1, dtype=theano.config.floatX)).mean()
    disc_cost += T.nnet.binary_crossentropy(disc_real_out, np.ones(1, dtype=theano.config.floatX)).mean()
    disc_cost /= np.float32(2.0)
    
    return disc_cost

trainer = AdversarialAdamTrainer(rng=rng, 
                                batchsize=BATCH_SIZE, 
                                gen_cost=generative_cost, 
                                disc_cost=discriminative_cost,
                                epochs=750, mean = mean, std = std)

trainer.train(gen_network=generatorNetwork, 
                                disc_network=discriminatorNetwork, 
                                train_input=E,
                                filename=[None, '../models/locomotion/adv/v_4/layer_0.npz',
                                        '../models/locomotion/adv/v_4/layer_1.npz', 
                                        None, None,
                                        None, None, '../models/locomotion/adv/v_4/layer_2.npz', None,
                                        None, None, '../models/locomotion/adv/v_4/layer_3.npz', None,
                                        None, None, '../models/locomotion/adv/v_4/layer_4.npz', None,])

BATCH_SIZE = 50

generatorNetwork = Network(
    DropoutLayer(rng, 0.25),    
    HiddenLayer(rng, (800, 64*30)),
    BatchNormLayer(rng, (800, 64*30)),
    ActivationLayer(rng, f='elu'),
    ReshapeLayer(rng, (BATCH_SIZE, 64, 30)),

    InverseNetwork(Pool1DLayer(rng, (2,), (BATCH_SIZE, 64, 60))),
    DropoutLayer(rng, 0.15),    
    Conv1DLayer(rng, (64, 64, 25), (BATCH_SIZE, 64, 60)),
    ActivationLayer(rng, f='elu'),

    InverseNetwork(Pool1DLayer(rng, (2,), (BATCH_SIZE, 64, 120))),
    DropoutLayer(rng, 0.25),  
    Conv1DLayer(rng, (64, 64, 25), (BATCH_SIZE, 64, 120)),
    ActivationLayer(rng, f='elu'),

    InverseNetwork(Pool1DLayer(rng, (2,), (BATCH_SIZE, 64, 240))),
    DropoutLayer(rng, 0.25),    
    Conv1DLayer(rng, (66, 64, 25), (BATCH_SIZE, 64, 240)),
    ActivationLayer(rng, f='elu'),
)

generatorNetwork.load([None, '../models/locomotion/adv/v_4/layer_0.npz',
                                        '../models/locomotion/adv/v_4/layer_1.npz', 
                                        None, None,
                                        None, None, '../models/locomotion/adv/v_4/layer_2.npz', None,
                                        None, None, '../models/locomotion/adv/v_4/layer_3.npz', None,
                                        None, None, '../models/locomotion/adv/v_4/layer_4.npz', None,])

def randomize_uniform_data(n_input):
    return rng.uniform(size=(n_input, 800), 
            low=-np.sqrt(25, dtype=theano.config.floatX), 
            high=np.sqrt(25, dtype=theano.config.floatX)).astype(theano.config.floatX)

gen_rand_input = theano.shared(randomize_uniform_data(50), name = 'z')
generate_sample_motions = theano.function([], generatorNetwork(gen_rand_input))
sample = generate_sample_motions()

result = sample * (std + 1e-10) + mean

new1 = result[25:26]
new2 = result[26:27]
new3 = result[0:1]

animation_plot([new1, new2, new3], filename='gan-locomotion.mp4', interval=15.15)