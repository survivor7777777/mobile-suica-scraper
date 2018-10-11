#!/usr/bin/env python

import sys, os, json, cv2, random, argparse, glob, re
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
DEFAULT_PARAM = "prebuild-model/parameters.json"
DEFAULT_OUTPUT = "data"

class AutoAnnotator:
    model_dir = None
    output_dir = None
    dataset = {}
    stride = (4, 4)
    segment_size = None
    log = None
    
    def __init__(self, param_file, output_dir, gpu=-1):
        self.param_file = param_file
        self.model_dir = os.path.dirname(self.param_file)
        self.output_dir = output_dir
        self.gpu = gpu
        
        with open(param_file, "r") as fp:
            self.param = json.load(fp)
        self.domain_y = self.param['domain_y']
        self.segment_size = self.param['dim_x']
        self.channels = self.param['channels']
        self.kernels = self.param['kernels']
        self.unit = self.param['unit']

        num_class = len(self.domain_y)
        self.model = L.Classifier(CNN(num_class, channels=self.channels, kernels=self.kernels, unit=self.unit))
        chainer.serializers.load_npz(self.model_dir + "/" + self.param['model'], self.model)
        if self.gpu >= 0:
            chainer.cuda.get_device_from_id(self.gpu).use()
            self.model.to_gpu()

    def run(self):
        self.imageList = glob.glob(os.path.join(self.output_dir, "*.gif"))
        self.imageList.sort()
        if len(self.imageList) == 0:
            print('No *.gif images found in {}'.format(output_dir))
            return

        self.datasetFile = os.path.join(self.output_dir, "dataset.json")
        self.dataset = {}
        if os.path.exists(self.datasetFile):
            os.rename(self.datasetFile, self.datasetFile + ".orig")
        for i, imageFile in enumerate(self.imageList):
            key = os.path.basename(imageFile)
            self.apply(key)

        with open(self.datasetFile, "w") as fp:
            json.dump(self.dataset, fp, indent=1)

    def update_candidate_set(self, candidate):
        letter = candidate['letter']
        if letter not in self.candidate_set:
            self.candidate_set[letter] = candidate
            return
        if self.candidate_set[letter]['score'] < candidate['score']:
            self.candidate_set[letter] = candidate

    def select_candidates(self):
        candidate_list = []
        for letter in self.candidate_set:
            candidate_list.append(self.candidate_set[letter])
        if len(candidate_list) > 5:
            candidate_list.sort(key = lambda e: -e['score'])
            del(candidate_list[5:])
        candidate_list.sort(key = lambda e: e['bb'][0])
        return candidate_list

    def apply(self, image_file):
        print(image_file, flush=True)
        gif = cv2.VideoCapture(os.path.join(self.output_dir, image_file))
        _, image_color = gif.read(0)
        height, width = image_color.shape[:2]
        image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)
        sh, sw = self.segment_size

        self.candidate_set = {}
        self.state = 0
        for x0 in range(0, width-sw, self.stride[1]):
            best_candidate = { 'bb': None, 'letter': None, 'score': 0 }
            for y0 in range(0, height-sh, self.stride[0]):
                letter, score = self.evaluate(image_gray, y0, x0, sh, sw)
                if letter != ' ':
                    candidate = { 'bb': [x0, y0, x0+sw, y0+sh], 'letter': letter, 'score': score }
                    if best_candidate['score'] < candidate['score']:
                        best_candidate = candidate
            if best_candidate['score'] > 0:
                self.update_candidate_set(best_candidate)
        detected_list = self.select_candidates()
        text = str.join('', map(lambda e: e['letter'], detected_list))
        bbs = list(map(lambda e: e['bb'], detected_list))
        record = { 'file': image_file, 'text': text, 'bbs': bbs }
        self.dataset[image_file] = record

    def evaluate(self, image_gray, y0, x0, h, w):
        image_segment = image_gray[y0:y0+h, x0:x0+w]
        x = np.array(image_segment / 255.0, dtype=np.float32).reshape(1, 1, h, w)
        x = convert.to_device(self.gpu, x)
        p = self.model.predictor(x).array.ravel()
        p = convert.to_device(-1, p)
        y = np.argmax(p)
        return self.domain_y[y], float(p[y])

if __name__ == '__main__':    
    parser = argparse.ArgumentParser(description='Mobile Suica Scraper -- Auto-Annotator')
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help='model output directory (default={})'.format(DEFAULT_OUTPUT))
    parser.add_argument('--param', default=DEFAULT_PARAM,
                        help='parameter file of pre-build model (default={})'.format(DEFAULT_PARAM))
    parser.add_argument('--gpu', default=-1, type=int,
                        help='gpu number (default={})'.format(DEFAULT_GPU))
    args = parser.parse_args()

    aa = AutoAnnotator(args.param, args.output, gpu=args.gpu)
    aa.run()

# end of apply.py
