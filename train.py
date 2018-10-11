#!/usr/bin/env python

import os, json, cv2, random, argparse, glob, re
import numpy as np

import matplotlib
matplotlib.use('Agg')

import chainer
import chainer.functions as F
import chainer.links as L
from chainer import Link, Chain, ChainList, datasets, iterators, optimizers, serializers, initializers, reporter, training, Variable
from chainer.training import extensions
from chainer.dataset import convert

from model import CNN

DEFAULT_GPU = -1
DEFAULT_EPOCH = 100
DEFAULT_BATCH = 100
DEFAULT_FREQUENCY = 10
DEFAULT_OUTPUT = "model"
DEFAULT_DATASET = "segmented-data/dataset.json"
DEFAULT_CHANNELS = "16:16:16:16"
DEFAULT_KERNELS = "3:3:5:5"
DEFAULT_UNIT = 1280

class TrainingDataSet:
    input_dir = None
    input_file = None
    dataset = None
    data_x = []
    data_y = []
    dim_x = None
    domain_y = None
    output = None
    
    def __init__(self, input_file=None):
        self.input_file = input_file

    def load(self):
        if self.input_file is None:
            return
        self.input_dir = os.path.dirname(self.input_file)
        with open(self.input_file, "r") as fp:
            self.dataset = json.load(fp)
        self.data_x = []
        self.data_y = []
        for entry in self.dataset:
            image_file = entry["file"]
            # image_label = entry["label"]  # when you want to segment
            image_label = entry["letter"] # when you want to read
            image_data = cv2.imread(self.input_dir + "/" + image_file, cv2.IMREAD_GRAYSCALE)
            self.data_x.append(np.array(image_data / 255.0, dtype=np.float32))
            self.data_y.append(image_label)
        self.dim_x = self.data_x[0].shape
        dedup = {}
        for y in self.data_y:
            dedup[y] = 1
        self.domain_y = list(dedup.keys())
        self.domain_y.sort()
        for i, y in enumerate(self.domain_y):
            dedup[y] = i
        for i, y in enumerate(self.data_y):
            self.data_y[i] = dedup[y]

    def size(self):
        return len(self.data_y)

    def split(self, train, test):
        total = train + test
        boundary = round(self.size() * train / total)

        train_ds = TrainingDataSet()
        test_ds  = TrainingDataSet()
        train_ds.dim_x = test_ds.dim_x = self.dim_x
        train_ds.domain_y = test_ds.domain_y = self.domain_y
        train_ds.data_x = self.data_x[0:boundary]
        train_ds.data_y = self.data_y[0:boundary]
        test_ds.data_x = self.data_x[boundary:]
        test_ds.data_y = self.data_y[boundary:]
        return train_ds, test_ds

    def __call__(self):
        if self.output is None:
            self.output = []
            for i, x in enumerate(self.data_x):
                y = self.data_y[i]
                h, w = x.shape
                self.output.append((x.reshape(1, h, w), y))
        return self.output

class Trainer:
    def __init__(self, input_file, output_dir,
                 gpu=DEFAULT_GPU, epoch=DEFAULT_EPOCH, resume=False,
                batch=DEFAULT_BATCH, frequency=DEFAULT_FREQUENCY, unit=DEFAULT_UNIT,
                channels=DEFAULT_CHANNELS, kernels=DEFAULT_KERNELS):
        self.output_dir = output_dir
        self.dataset_file = input_file
        self.gpu = gpu
        self.epoch = epoch
        self.batch = batch
        self.frequency = frequency
        self.resume = resume
        self.channels = list(map(lambda x: int(x), channels.split(':')))
        self.kernels = list(map(lambda x: int(x), kernels.split(':')))
        self.unit = unit
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        ds = TrainingDataSet(self.dataset_file)
        ds.load()
        train_ds, test_ds = ds.split(9, 1)

        print("total size = {}".format(ds.size()))
        print("train size = {}".format(train_ds.size()))
        print("test size = {}".format(test_ds.size()))
        print("gpu = {}".format(self.gpu))
        print("epoch = {}".format(self.epoch))
        print("batch = {}".format(self.batch))
        print("frequency = {}".format(self.frequency))
        print("channels = {}".format(self.channels))
        print("kernels = {}".format(self.kernels))
        print("unit = {}".format(self.unit))

        param = {
            'dim_x': ds.dim_x,
            'domain_y': ds.domain_y,
            'channels': self.channels,
            'kernels': self.kernels,
            'unit': self.unit,
            'model': 'model.npz'
        }
        param_file = os.path.join(self.output_dir, "parameters.json")
        print("Saving the model parameters in {}.".format(param_file))
        with open(param_file, "w") as fp:
            json.dump(param, fp)

        train_iter = iterators.SerialIterator(train_ds(), self.batch)
        test_iter = iterators.SerialIterator(test_ds(), self.batch, repeat=False, shuffle=False)

        num_class = len(ds.domain_y)
        model = L.Classifier(CNN(num_class, channels=self.channels, kernels=self.kernels, unit=self.unit))
        if self.gpu >= 0:
            chainer.cuda.get_device_from_id(self.gpu).use()
            model.to_gpu()
    
        optimizer = optimizers.Adam()
        optimizer.setup(model)
        
        updater = training.StandardUpdater(train_iter, optimizer, device=self.gpu)
        trainer = training.Trainer(updater, (self.epoch, 'epoch'), out=self.output_dir)
        trainer.extend(extensions.Evaluator(test_iter, model, device=self.gpu))
        trainer.extend(extensions.snapshot(), trigger=(self.frequency, 'epoch'))
        trainer.extend(extensions.LogReport())
        trainer.extend(extensions.PlotReport(['main/loss',
                                              'validation/main/loss'],
                                                'epoch', file_name='loss.png'))
        trainer.extend(extensions.PlotReport(['main/accuracy',
                                              'validation/main/accuracy'],
                                                'epoch', file_name='accuracy.png'))
        trainer.extend(extensions.PrintReport(['epoch', 'main/loss', 'validation/main/loss',
                                               'main/accuracy', 'validation/main/accuracy', 'elapsed_time']))
        trainer.extend(extensions.dump_graph(root_name="main/loss", out_name="cg.dot"))

        if self.resume:
            maxnum = 0
            for s in glob.glob(os.path.join(self.output_dir, "snapshot_iter_*")):
                m = re.search('[0-9]+$', s)
                maxnum = max(maxnum, int(m.group(0)))
            if maxnum == 0:
                print("No snapshot file found. Ignore --resume option")
            else:
                snapshot_file = os.path.join(self.output_dir, "snapshot_iter_" + str(maxnum))
                print("Loading the snapshot data from {}.".format(snapshot_file))
                chainer.serializers.load_npz(snapshot_file, trainer)
                
        trainer.run()
        
        model_file = os.path.join(self.output_dir, "model.npz")
        print("Saving the model to {}.".format(model_file))
        chainer.serializers.save_npz(model_file, model)
    
if __name__ == '__main__':    
    parser = argparse.ArgumentParser(description='Mobile Suica Scraper -- Captcha Solving Model Trainer')
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help='model output directory (default={})'.format(DEFAULT_OUTPUT))
    parser.add_argument('--dataset', default=DEFAULT_DATASET,
                        help='segmentation model directory (default={})'.format(DEFAULT_DATASET))
    parser.add_argument('--gpu', default=-1, type=int,
                        help='gpu number (default={})'.format(DEFAULT_GPU))
    parser.add_argument('--epoch', default=DEFAULT_EPOCH, type=int,
                        help='training epoch (default={})'.format(DEFAULT_GPU))
    parser.add_argument('--batch', default=DEFAULT_BATCH, type=int,
                        help='mini-batch size (default={})'.format(DEFAULT_BATCH))
    parser.add_argument('--frequency', default=DEFAULT_FREQUENCY, type=int,
                        help='snapshot frequency (default={})'.format(DEFAULT_FREQUENCY))
    parser.add_argument('--resume', default=False, action='store_true',
                        help='Resume training from a snapshot (default=False)')
    parser.add_argument('--channels', default=DEFAULT_CHANNELS,
                        help='Numbers of channels (default={})'.format(DEFAULT_CHANNELS))
    parser.add_argument('--kernels', default=DEFAULT_KERNELS,
                        help='Sizes of kernels (default={})'.format(DEFAULT_KERNELS))
    parser.add_argument('--unit', default=DEFAULT_UNIT, type=int,
                        help='Number of FC units (default={})'.format(DEFAULT_UNIT))
    args = parser.parse_args()

    trainer = Trainer(args.dataset, args.output, gpu=args.gpu, epoch=args.epoch,
                      batch=args.batch, frequency=args.frequency, resume=args.resume,
                      channels=args.channels, kernels=args.kernels, unit=args.unit)
    trainer.run()

# end of train.py
