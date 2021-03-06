import numpy as np
import theano
import theano.tensor as T
import sys
import random
from sklearn.model_selection import train_test_split

sys.setrecursionlimit(10000)

class lstm(object):
    '''
    long short term memory network for classifying human activity 
    from incremental summary statistics
    
    parameters:
      - binary: boolean (default False)
        use True if labels are for ambulatory/non-ambulatory
        use False if labels are for non-ambulatory/walking/running/upstairs/downstairs
        
    methods:
      - train(X_train, y_train)
        train lstm network
        parameters:
          - X_train: 2d numpy array
            training features output by record_fetcher_within_subject.py
          - y_train: 2d numpy array
            training labels output by record_fetcher_within_subject.py
        outputs:
          - training loss at given iteration
      - predict(X_test)
        predict label from test data
        parameters:
          - X_test: 2d numpy array
            testing features output by record_fetcher_within_subject.py
        outputs:
          - predicted labels for test features
    '''
    def __init__(self,binary=False):
    
        #layer 1 - lstm units
        self.input = T.matrix()
        self.Wi = theano.shared(self.ortho_weight(128)[:109,:],borrow=True)
        self.Wf = theano.shared(self.ortho_weight(128)[:109,:],borrow=True)
        self.Wc = theano.shared(self.ortho_weight(128)[:109,:],borrow=True)
        self.Wo = theano.shared(self.ortho_weight(128)[:109,:],borrow=True)
        self.Ui = theano.shared(self.ortho_weight(128),borrow=True)
        self.Uf = theano.shared(self.ortho_weight(128),borrow=True)
        self.Uc = theano.shared(self.ortho_weight(128),borrow=True)
        self.Uo = theano.shared(self.ortho_weight(128),borrow=True)
        self.bi = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.bf = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.bc = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.bo = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.C0 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.h0 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        
        #layer 2 - lstm units
        self.Wi2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.Wf2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.Wc2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.Wo2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.Ui2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.Uf2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.Uc2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.Uo2 = theano.shared(self.ortho_weight(128),borrow=True)
        self.bi2 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.bf2 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.bc2 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.bo2 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.C02 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        self.h02 = theano.shared(np.zeros((128,), dtype=theano.config.floatX),borrow=True)
        
        #layer 3 - softmax
        if binary:
            self.W2 = theano.shared(self.ortho_weight(128)[:,:2],borrow=True)
            self.b2 = theano.shared(np.zeros((2,), dtype=theano.config.floatX),borrow=True)
        
        else:
            self.W2 = theano.shared(self.ortho_weight(128)[:,:5],borrow=True)
            self.b2 = theano.shared(np.zeros((5,), dtype=theano.config.floatX),borrow=True)
        self.target = T.matrix()
        
        #scan operation for lstm layer 1
        self.params1 = [self.Wi,self.Wf,self.Wc,self.Wo,self.Ui,self.Uf,self.Uc,self.Uo,self.bi,self.bf,self.bc,self.bo]
        [self.c1,self.h_output1],_ = theano.scan(fn=self.step,sequences=self.input,outputs_info=[self.C0,self.h0],non_sequences=self.params1)
        
        #scan operation for lstm layer 2
        self.params2 = [self.Wi2,self.Wf2,self.Wc2,self.Wo2,self.Ui2,self.Uf2,self.Uc2,self.Uo2,self.bi2,self.bf2,self.bc2,self.bo2]
        [self.c2,self.h_output2],_ = theano.scan(fn=self.step,sequences=self.h_output1,outputs_info=[self.C02,self.h02],non_sequences=self.params2)
        
        #final softmax, final output is average of output of last 4 timesteps
        self.output = T.nnet.softmax(T.dot(self.h_output2,self.W2)+self.b2)[-4:,:]
        self.output = T.mean(self.output,0,keepdims=True)
        
        #cost, updates, train, and predict
        self.cost = T.nnet.categorical_crossentropy(self.output,self.target).mean()
        self.updates = self.adam(self.cost,self.params1+self.params2+[self.h0,self.C0,self.h02,self.C02,self.W2,self.b2])
        self.train = theano.function([self.input,self.target],self.cost,updates=self.updates,allow_input_downcast=True)
        self.predict = theano.function([self.input],self.output,allow_input_downcast=True)

    def step(self,input,h0,C0,Wi,Wf,Wc,Wo,Ui,Uf,Uc,Uo,bi,bf,bc,bo):
        '''
        step function for lstm unit
        '''
        i = T.nnet.sigmoid(T.dot(input,Wi)+T.dot(h0,Ui)+bi)
        cand = T.tanh(T.dot(input,Wc)+T.dot(h0,Uc)+bc)
        f = T.nnet.sigmoid(T.dot(input,Wf)+T.dot(h0,Uf)+bf)
        c = cand*i+C0*f
        o = T.nnet.sigmoid(T.dot(input,Wo)+T.dot(h0,Uo)+bo)
        h = o*T.tanh(c)
        return c,h

    def ortho_weight(self,ndim):
        '''
        orthogonal weight initialization for lstm layers
        '''
        bound = np.sqrt(1./ndim)
        W = np.random.randn(ndim, ndim)*bound
        u, s, v = np.linalg.svd(W)
        return u.astype(theano.config.floatX)

    def adam(self, cost, params, lr=0.0002, b1=0.1, b2=0.01, e=1e-8):
        '''
        adaptive moment estimation gradient descent
        '''
        updates = []
        grads = T.grad(cost, params)
        self.i = theano.shared(np.float32(0.))
        i_t = self.i + 1.
        fix1 = 1. - (1. - b1)**i_t
        fix2 = 1. - (1. - b2)**i_t
        lr_t = lr * (T.sqrt(fix2) / fix1)
        for p, g in zip(params, grads):
            self.m = theano.shared(p.get_value() * 0.)
            self.v = theano.shared(p.get_value() * 0.)
            m_t = (b1 * g) + ((1. - b1) * self.m)
            v_t = (b2 * T.sqr(g)) + ((1. - b2) * self.v)
            g_t = m_t / (T.sqrt(v_t) + e)
            p_t = p - (lr_t * g_t)
            updates.append((self.m, m_t))
            updates.append((self.v, v_t))
            updates.append((p, p_t))
        updates.append((self.i, i_t))
        return updates

#load data
X = np.load('X.npy')
y = np.load('y.npy')
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1)

# verify the required arguments are given
if (len(sys.argv) < 2):
    print 'Usage: python lstm_within_subject.py <1 for 2-category labels, 0 for 5-category labels>'
    exit(1)

if sys.argv[1] == '1':
    binary = True
elif sys.argv[1] == '0':
    binary = False
else:
    print 'Usage: python lstm_within_subject.py <1 for 2-category labels, 0 for 5-category labels>'
    exit(1)

#separate training data by label
X_train_split = []
y_train_split = []
if binary:
    for i in range(2):
        idx = y_train[:,i] == 1
        X_train_split.append(X_train[idx])
        y_train_split.append(y_train[idx])
else:
    for i in range(5):
        idx = y_train[:,i] == 1
        X_train_split.append(X_train[idx])
        y_train_split.append(y_train[idx])

combined_split = zip(X_train_split,y_train_split)

#train
NN = lstm(binary=binary)

for i in range(1000000):
    #select a random training label
    idx = random.choice(combined_split)
    X_in = idx[0] 
    y_in = idx[1]

    #select random training sample with that label
    idx = np.random.randint(y_in.shape[0])
    X_in = X_in[idx,:,:]
    y_in = np.expand_dims(y_in[idx,:],0)
    
    #train on random sample
    cost = NN.train(X_in,y_in)
    print "step %i training error: %.4f \r" % (i+1, cost),

    #predict every 10000 iterations
    if (i+1) % 10000 == 0:
        correct = 0
        
        #predict each entry in test set
        for j in range(y_test.shape[0]):
            print "predicting %i of %i in test set \r" % (j+1, y_test.shape[0]),
            pred = NN.predict(X_test[j,:,:])
            if np.argmax(pred[0]) == np.argmax(y_test[j,:]):
                correct += 1
        print "step %i test accuracy: %.4f           " % (i+1,float(correct)/y_test.shape[0]*100)