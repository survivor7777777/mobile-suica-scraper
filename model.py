#!/usr/bin/env python

import os, json, cv2, random, argparse, glob, re
import numpy as np

import chainer
import chainer.functions as F
import chainer.links as L
from chainer import Link, Chain, ChainList, datasets, iterators, optimizers, serializers, initializers, reporter, training, Variable
from chainer.training import extensions
from chainer.dataset import convert

class CNN(Chain):
    def __init__(self, num_class, channels=[32, 32, 32, 32], kernels=[4, 4, 4, 4], unit=1024):
        initializer = initializers.HeNormal()
        super().__init__()
        with self.init_scope():
            self.conv1_1 = L.Convolution2D(None, channels[0], ksize=kernels[0], pad=2, initialW=initializer)
            self.conv1_2 = L.Convolution2D(None, channels[1], ksize=kernels[1], pad=2, initialW=initializer)
            self.conv2_1 = L.Convolution2D(None, channels[2], ksize=kernels[2], pad=2, initialW=initializer)
            self.conv2_2 = L.Convolution2D(None, channels[3], ksize=kernels[3], pad=2, initialW=initializer)
            self.fc1 = L.Linear(None, unit, initialW=initializer)
            self.fc2 = L.Linear(None, num_class, initialW=initializer)

    def __call__(self, x):
        conv1_1 = F.relu(self.conv1_1(x))
        conv1_2 = F.relu(self.conv1_2(conv1_1))
        pool1 = F.max_pooling_2d(conv1_2, 2)
        conv2_1 = F.relu(self.conv2_1(pool1))
        conv2_2 = F.relu(self.conv2_2(conv2_1))
        pool2 = F.max_pooling_2d(conv2_2, 2)
        fc1 = F.dropout(F.relu(self.fc1(pool2)))
        fc2 = self.fc2(fc1)
        return fc2

# model.py
