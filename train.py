#!/usr/bin/env python

import os, argparse, copy, json, glob, re
import numpy as np

import chainer
from chainer import serializers
from chainer import training
from chainer.training import extensions
from chainer.training import triggers
from chainer.datasets import TransformDataset

from ssd import SSD
from dataset import Dataset
from evaluator import Evaluator
from extractor import Extractor
from multibox import Multibox
from constants import *
from multibox_loss import multibox_loss

import cv2
cv2.setNumThreads(0)

class MultiboxTrainChain(chainer.Chain):
    def __init__(self, model, alpha=1, k=3):
        super(MultiboxTrainChain, self).__init__()
        with self.init_scope():
            self.model = model
        self.alpha = alpha
        self.k = k

    def forward(self, imgs, gt_mb_locs, gt_mb_labels):
        mb_locs, mb_confs = self.model(imgs)
        loc_loss, conf_loss = multibox_loss(mb_locs, mb_confs, gt_mb_locs, gt_mb_labels, self.k)
        loss = loc_loss * self.alpha + conf_loss

        chainer.reporter.report(
            {'loss': loss, 'loss/loc': loc_loss, 'loss/conf': conf_loss},
            self)

        return loss

class Transform:
    def __init__(self, coder):
        self.coder = copy.copy(coder)
        self.coder.to_cpu()

    def __call__(self, in_data):
        img, bbox, label = in_data
        mb_loc, mb_label = self.coder.encode(bbox, label)
        return img, mb_loc, mb_label

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', type=int, default=DEFAULT_CHANNEL)
    parser.add_argument('--batchsize', type=int, default=DEFAULT_BATCHSIZE)
    parser.add_argument('--epoch', type=int, default=DEFAULT_EPOCH)
    parser.add_argument('--frequency', type=int, default=DEFAULT_FREQUENCY)
    parser.add_argument('--alpha', type=float, default=DEFAULT_ALPHA)
    parser.add_argument('--opt', choices=('adam', 'adabound', 'amsgrad', 'amsbound'),
        default=DEFAULT_OPTIMIZER)
    parser.add_argument('--gpu', type=int, default=-1)
    parser.add_argument('--model', default='model')
    parser.add_argument('--resume', action='store_true', default=False)
    parser.add_argument('--retrain', action='store_true', default=False)
    args = parser.parse_args()

    if args.resume and args.retrain:
        print('--resume and --retrain are exclusive')
        exit(1)

    dataset = Dataset(DEFAULT_DATASET_DIR)
    n_data = len(dataset)
    thresh = int(n_data * 0.9 + 0.5)
    print("{} records found in the dataset. {} records will be used for training".format(n_data, thresh))

    n_class = dataset.n_class
    class_ids = dataset.class_ids
    class_labels = dataset.class_labels

    model = SSD(n_class=n_class, n_channel=args.channel,
                grids=DEFAULT_GRIDS, aspect_ratios=DEFAULT_ASPECT_RATIOS,
                nms_thresh=DEFAULT_NMS_THRESH, score_thresh=DEFAULT_SCORE_THRESH,
                variance=DEFAULT_VARIANCE)
    train_chain = MultiboxTrainChain(model)
    if args.gpu >= 0:
        chainer.cuda.get_device_from_id(args.gpu).use()
        model.to_gpu()

    train = TransformDataset(dataset[:thresh], Transform(model.coder))
    train_iter = chainer.iterators.SerialIterator(train, args.batchsize)

    test = dataset[thresh:]
    test_iter = chainer.iterators.SerialIterator(test, args.batchsize, repeat=False, shuffle=False)

    # ('adam', 'adabound', 'amsgrad', 'amsbound')
    if args.opt == 'adam':
        adabound = False
        amsgrad = False
    elif args.opt == 'adabound':
        adabound = True
        amsgrad = False
    elif args.opt == 'amsgrad':
        adabound = False
        amsgrad = True
    elif args.opt == 'amsbound':
        adabound = True
        amsgrad = True
    else:
        raise ValueExcept('invalid optimizer')

    optimizer = chainer.optimizers.Adam(alpha=args.alpha, adabound=adabound, amsgrad=amsgrad)
    optimizer.setup(train_chain)

    updater = training.updaters.StandardUpdater(
        train_iter, optimizer, device=args.gpu)
    trainer = training.Trainer(updater, (args.epoch, 'epoch'), args.model)

    log_interval = 1, 'epoch'
    trainer.extend(extensions.LogReport(trigger=log_interval))
    trainer.extend(extensions.observe_lr(), trigger=log_interval)
    trainer.extend(extensions.PrintReport(
        ['epoch', 'iteration', 'lr',
         'main/loss', 'main/loss/loc', 'main/loss/conf',
         'validation/main/acc',
         'elapsed_time']),
        trigger=log_interval)
    trainer.extend(extensions.ProgressBar(update_interval=5))

    trainer.extend(Evaluator(test_iter, model))

    trainer.extend(extensions.snapshot(filename='snapshot_epoch_{.updater.epoch}'),
        trigger=(args.frequency, 'epoch'))

    trainer.extend(extensions.PlotReport(['main/loss', 'main/loss/loc', 'main/loss/conf'],
        x_key='epoch', file_name='loss.png'))

    model_file = os.path.join(args.model, "model.npz")
    if args.retrain:
        if not os.path.isfile(model_file):
            print("{}: not found".format(model_file))
            exit(1)
        print("Loading pretrained model from {}...".format(model_file))
        chainer.serializers.load_npz(model_file, model)
    
    if args.resume:
        maxnum = -1
        for s in glob.glob(os.path.join(args.model, "snapshot_epoch_*")):
            m = re.search('[0-9]+$', s)
            if m:
                maxnum = max(maxnum, int(m.group(0)))
        if maxnum < 0:
            print("No snapshot file found. Ignore --resume option")
        else:
            snapshot_file = os.path.join(args.model, "snapshot_epoch_{}".format(maxnum))
            print("Loading the snapshot data from {}.".format(snapshot_file))
            chainer.serializers.load_npz(snapshot_file, trainer)

    trainer.run()

    print("Saving the model to {}.".format(model_file))
    chainer.serializers.save_npz(model_file, model)

    metadata = { 'file': "model.npz", 'n_channel': args.channel,
        'n_class': n_class, 'class_labels': class_labels }
    with open(os.path.join(args.model, "model.json"), "w") as fp:
        json.dump(metadata, fp, sort_keys=True)

    return

if __name__ == '__main__':
    main()
