import matplotlib.pyplot as plt
import numpy as np
import theano
import theano.tensor as T
import timeit
import sys

from AdamTrainer import AdamTrainer
from datetime import datetime
from matplotlib import animation
from mpl_toolkits.mplot3d import Axes3D
from theano.tensor.shared_randomstreams import RandomStreams

class AdversarialAdamTrainer(object):
    def __init__(self, rng, batchsize, 
                    gen_cost, disc_cost,
                    epochs=100, 
                    gen_alpha=0.000001, gen_beta1=0.9, gen_beta2=0.999, 
                    disc_alpha=0.000001, disc_beta1=0.9, disc_beta2=0.999, 
                    eps=1e-08, 
                    l1_weight=0.0, l2_weight=0.1, n_hidden_source = 100):

        self.gen_alpha = gen_alpha
        self.gen_beta1 = gen_beta1
        self.gen_beta2 = gen_beta2

        self.disc_alpha = disc_alpha
        self.disc_beta1 = disc_beta1
        self.disc_beta2 = disc_beta2

        self.eps = eps
        self.l1_weight = l1_weight
        self.l2_weight = l2_weight
        self.rng = rng
        self.theano_rng = RandomStreams(rng.randint(2 ** 30))
        self.epochs = epochs
        self.batchsize = batchsize
        self.n_hidden_source = n_hidden_source

        self.generator = lambda network, x: network(x)
        self.discriminator = lambda network, x: network(x)

        self.generator_cost = gen_cost
        self.discriminator_cost = disc_cost

    def randomize_uniform_data(self, n_input):
        return self.rng.uniform(size=(n_input, 100), 
                low=-np.float32(np.sqrt(3)), 
                high=np.float32(np.sqrt(3)))

    def l1_regularization(self, network, target=0.0):
        return sum([T.mean(abs(p - target)) for p in network.params])

    def l2_regularization(self, network, target=0.0):
        return sum([T.mean((p - target)**2) for p in network.params])

    def get_cost_updates(self, gen_network, disc_network, input):

        gen_rand_input = theano.shared(self.randomize_uniform_data(self.batchsize), name = 'z')

        gen_result = self.generator(gen_network, gen_rand_input)
        concat_gen_input = T.concatenate([gen_result, input], axis = 0)
        disc_result = self.discriminator(disc_network, T.concatenate([gen_result, input], axis = 0))

        disc_fake_result = T.nnet.sigmoid(disc_result[:self.batchsize])
        disc_real_result = T.nnet.sigmoid(disc_result[self.batchsize:])

        # generator update
        gen_cost = self.generator_cost(disc_fake_result) #+ self.l1_weight * self.l1_regularization(gen_network) + \
                                                         #   self.l2_weight * self.l2_regularization(gen_network)
        
        gen_gparams = T.grad(gen_cost, self.gen_params)

        gen_m0params = [self.gen_beta1 * m0p + (1-self.gen_beta1) *  gp     for m0p, gp in zip(self.gen_m0params, gen_gparams)]
        gen_m1params = [self.gen_beta2 * m1p + (1-self.gen_beta2) * (gp*gp) for m1p, gp in zip(self.gen_m1params, gen_gparams)]

        gen_params = [p - self.gen_alpha * 
                  ((m0p/(1-(self.gen_beta1**self.gen_t[0]))) /
            (T.sqrt(m1p/(1-(self.gen_beta2**self.gen_t[0]))) + self.eps))
            for p, m0p, m1p in zip(self.gen_params, gen_m0params, gen_m1params)]

        updates = ([( p,  pn) for  p,  pn in zip(self.gen_params, gen_params)] +
                   [(m0, m0n) for m0, m0n in zip(self.gen_m0params, gen_m0params)] +
                   [(m1, m1n) for m1, m1n in zip(self.gen_m1params, gen_m1params)] +
                   [(self.gen_t, self.gen_t+1)])

        # discriminator update
        disc_cost = self.discriminator_cost(disc_fake_result, disc_real_result) # + \
                                                    # self.l1_weight * self.l1_regularization(gen_network) + \
                                                    # self.l2_weight * self.l2_regularization(gen_network)

        disc_gparams = T.grad(disc_cost, self.disc_params)

        disc_m0params = [self.disc_beta1 * m0p + (1-self.disc_beta1) *  gp     for m0p, gp in zip(self.disc_m0params, disc_gparams)]
        disc_m1params = [self.disc_beta2 * m1p + (1-self.disc_beta2) * (gp*gp) for m1p, gp in zip(self.disc_m1params, disc_gparams)]

        disc_params = [p - self.disc_alpha * 
                  ((m0p/(1-(self.disc_beta1**self.disc_t[0]))) /
            (T.sqrt(m1p/(1-(self.disc_beta2**self.disc_t[0]))) + self.eps))
            for p, m0p, m1p in zip(self.disc_params, disc_m0params, disc_m1params)]

        updates += ([( p,  pn) for  p,  pn in zip(self.disc_params, disc_params)] +
                   [(m0, m0n) for m0, m0n in zip(self.disc_m0params, disc_m0params)] +
                   [(m1, m1n) for m1, m1n in zip(self.disc_m1params, disc_m1params)] +
                   [(self.disc_t, self.disc_t+1)])

        return (gen_cost, disc_cost, updates)

    def train(self, gen_network, disc_network, train_input, filename=None):

        """ Conventions: For training examples with labels, pass a one-hot vector, otherwise a numpy array with zero values.
        """
        
        # variables to store parameters
        self.gen_network = gen_network

        input = train_input.type()
        
        # Match batch index
        index = T.lscalar()
        
        self.gen_params = gen_network.params
        self.gen_m0params = [theano.shared(np.zeros(p.shape.eval(), dtype=theano.config.floatX), borrow=True) for p in self.gen_params]
        self.gen_m1params = [theano.shared(np.zeros(p.shape.eval(), dtype=theano.config.floatX), borrow=True) for p in self.gen_params]
        self.gen_t = theano.shared(np.array([1], dtype=theano.config.floatX))

        self.disc_params = disc_network.params
        self.disc_m0params = [theano.shared(np.zeros(p.shape.eval(), dtype=theano.config.floatX), borrow=True) for p in self.disc_params]
        self.disc_m1params = [theano.shared(np.zeros(p.shape.eval(), dtype=theano.config.floatX), borrow=True) for p in self.disc_params]
        self.disc_t = theano.shared(np.array([1], dtype=theano.config.floatX))

        gen_cost, disc_cost, updates = self.get_cost_updates(gen_network, disc_network, input)

        train_func = theano.function(inputs=[index], 
                                     outputs=[gen_cost, disc_cost], 
                                     updates=updates, 
                                     givens={input:train_input[index*self.batchsize:(index+1)*self.batchsize],}, 
                                     allow_input_downcast=True)

        ###############
        # TRAIN MODEL #
        ###############
        print('... training')
        
        best_epoch = 0
        last_tr_mean = 0.

        start_time = timeit.default_timer()

        for epoch in range(self.epochs):
            
            train_batchinds = np.arange(train_input.shape.eval()[0] // self.batchsize)
            self.rng.shuffle(train_batchinds)
            
            sys.stdout.write('\n')
            
            tr_gen_costs  = []
            tr_disc_costs = []
            for bii, bi in enumerate(train_batchinds):
                tr_gen_cost, tr_disc_cost = train_func(bi)

                tr_gen_costs.append(tr_gen_cost)
                if np.isnan(tr_gen_costs[-1]):
                    print "NaN in generator cost."
                    return

                tr_disc_costs.append(tr_disc_cost)
                if np.isnan(tr_disc_costs[-1]):
                    print "NaN in discriminator cost."
                    return

        print "Finished training..."

        self.gen_network.params = self.gen_params
        
        gen_rand_input = theano.shared(self.randomize_uniform_data(100), name = 'z')
        generate_sample_images = theano.function([], self.generator(self.gen_network, gen_rand_input))

        sample = generate_sample_images()

        # the transpose is rowx, rowy, height, width -> rowy, height, rowx, width
        sample = sample.reshape((10,10,28,28)).transpose(1,2,0,3).reshape((10*28, 10*28))
        plt.imshow(sample, cmap = plt.get_cmap('gray'), vmin=0, vmax=1)
        plt.savefig('sampleImages')

        end_time = timeit.default_timer()