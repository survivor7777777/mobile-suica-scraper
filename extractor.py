#!/usr/bin/env python

import chainer
import chainer.functions as F
import chainer.links as L
from chainer import initializers

class Extractor(chainer.Chain):
    grids = ((6, 20))

    def __init__(self, n_channel):
        super(Extractor, self).__init__()
        init = {
            'initialW': initializers.LeCunUniform(),
            'initial_bias': initializers.Zero(),
        }
        with self.init_scope():
            self.conv1_1 = L.Convolution2D(n_channel, 3, pad=1, **init)
            self.conv1_2 = L.Convolution2D(n_channel, 3, pad=1, **init)

            self.conv2_1 = L.Convolution2D(n_channel*2, 3, pad=1, **init)
            self.conv2_2 = L.Convolution2D(n_channel*2, 3, pad=1, **init)

            self.conv3_1 = L.DilatedConvolution2D(n_channel*4, 3, pad=1, dilate=2, **init)
            self.conv3_2 = L.DilatedConvolution2D(n_channel*4, 3, pad=1, dilate=2, **init)

            self.conv4_1 = L.Convolution2D(n_channel*8, 3, pad=1, **init)
            self.conv4_2 = L.Convolution2D(n_channel*8, 3, pad=1, **init)

    def forward(self, x):
        ys = []
        h = F.relu(self.conv1_1(x))
        h = F.relu(self.conv1_2(h))
        h = F.max_pooling_2d(h, 2)

        h = F.relu(self.conv2_1(h))
        h = F.relu(self.conv2_2(h))
        h = F.max_pooling_2d(h, 2)

        h = F.relu(self.conv3_1(h))
        h = F.relu(self.conv3_2(h))
        h = F.max_pooling_2d(h, 2)

        h = F.relu(self.conv4_1(h))
        h = F.relu(self.conv4_2(h))
        ys.append(h)

        return ys
