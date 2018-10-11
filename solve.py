#!/usr/bin/env python

import os, sys, cv2, json, argparse
from PIL import Image
import numpy as np

import chainer
import chainer.links as L
from chainer.dataset import convert

from model import CNN

class Solver:
    stride = [4, 4]

    def __init__(self, param_file, gpu):
        self.gpu = gpu
        self.model_dir = os.path.dirname(param_file);
        with open(param_file, "r") as fp:
            self.param = json.load(fp)
        self.channels = self.param['channels'];
        self.kernels = self.param['kernels'];
        self.unit = self.param['unit'];
        self.segment_size = self.param['dim_x']
        self.domain_y = self.param['domain_y']
        self.n_class = len(self.domain_y)

        self.model = L.Classifier(CNN(self.n_class, channels=self.channels, kernels=self.kernels, unit=self.unit))
        chainer.serializers.load_npz(os.path.join(self.model_dir, self.param['model']), self.model)
        if self.gpu >= 0:
            chainer.cuda.get_device_from_id(self.gpu).use()
            self.model.to_gpu()

    def evaluate(self, image_gray, y0, x0, h, w):
        y1 = y0 + h
        x1 = x0 + w
        image_segment = image_gray[y0:y1, x0:x1]
        x = np.array(image_segment / 255.0, dtype=np.float32).reshape(1, 1, h, w)
        x = convert.to_device(self.gpu, x)
        p = self.model.predictor(x).array.ravel()
        p = convert.to_device(-1, p)
        y = np.argmax(p)
        return self.domain_y[y], float(p[y])

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

    def solve(self, image_gray):
        h, w = image_gray.shape
        sh, sw = self.segment_size
        self.candidate_set = {}
        for x0 in range(0, w-sw, self.stride[1]):
            best_candidate = { 'score': 0 }
            for y0 in  range(0, h-sh, self.stride[0]):
                letter, score = self.evaluate(image_gray, y0, x0, sh, sw)
                if letter != ' ':
                    candidate = { 'bb': [x0, y0, x0+sw, y0+sh], 'letter': letter, 'score': score }
                    if best_candidate['score'] < candidate['score']:
                        best_candidate = candidate
            if best_candidate['score'] > 0:
                self.update_candidate_set(best_candidate)
        detected_list = self.select_candidates()
        prediction = str.join('', map(lambda e: e['letter'], detected_list))
        return prediction

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='captcha solver')
    parser.add_argument('--model', '-m', default='model/parameters.json',
                        help='Parameter file name (default=model/parameters.json)')
    parser.add_argument('--gpu', '-g', type=int, default=-1,
                        help='GPU ID (negative value indicates CPU) (default=-1)')

    args = parser.parse_args()
    solver = Solver(args.model, args.gpu)
    img = np.asarray(Image.open(sys.stdin.buffer))
    captcha_string = solver.solve(img)
    print(captcha_string)
