#!/usr/bin/env python

import os, json, cv2, random, argparse, glob, re, sys
import numpy as np
from constants import *

import chainer

from ssd import SSD
from extractor import Extractor
from multibox import Multibox

class Solver:
    def __init__(self, dirname=DEFAULT_MODEL_DIR, gpu=-1,
            nms_thresh=DEFAULT_NMS_THRESH, score_thresh=DEFAULT_SCORE_THRESH):
        with open(os.path.join(dirname, "model.json"), 'r') as fp:
            metadata = json.load(fp)

        n_class = metadata['n_class']
        n_channel = metadata['n_channel']
        npz_file = metadata['file']
        self.class_labels = metadata['class_labels']

        self.model = SSD(n_class=n_class, n_channel=n_channel,
            nms_thresh=nms_thresh, score_thresh=score_thresh,
            grids=DEFAULT_GRIDS, aspect_ratios=DEFAULT_ASPECT_RATIOS,
            variance=DEFAULT_VARIANCE)
        chainer.serializers.load_npz(os.path.join(dirname, npz_file), self.model)

        if gpu >= 0:
            chainer.backends.cuda.get_device_from_id(gpu).use()
            self.model.to_gpu(gpu)

    @property
    def xp(self):
        return self.model.xp

    def solve(self, filename):
        xp = self.xp
        gif = cv2.VideoCapture(filename)
        _, color_image = gif.read(0)
        gray_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
        h, w = gray_image.shape[:2]
        img = xp.array(gray_image / 255.0, dtype=xp.float32).reshape(1, 1, h, w)

        output = self.model.predict(img)
        bbox, label, score = output[0][0], output[1][0], output[2][0]
        bbox = chainer.dataset.to_device(-1, bbox)
        label = chainer.dataset.to_device(-1, label)
        score = chainer.dataset.to_device(-1, score)

        if len(label) > NCHARS:
            indices = np.argsort(score)[-1:-NCHARS-1:-1]
            bbox = bbox[indices]
            label = label[indices]
            score = score[indices]
        bbox = np.vectorize(lambda v: int(v + 0.5), otypes=[int])(bbox)

        indices = np.argsort(bbox[:, 1])
        text = ''.join([ self.class_labels[label[i]] for i in indices ])

        return text, bbox[indices], score[indices]

if __name__ == '__main__':

    colors = [(255, 0, 0), (0, 0, 255), (0, 255, 0), (255, 255, 0), (0, 255, 255)]
    scale = 4
    font = cv2.FONT_HERSHEY_PLAIN
    text_color = (255, 0, 255)

    def display(filename, text, bbox, score):
        gif = cv2.VideoCapture(filename)
        _, color_image = gif.read(0)
        gray_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
        image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)

        for i, bb in enumerate(bbox):
            cv2.rectangle(image, (bb[1], bb[0]), (bb[3], bb[2]), colors[i % len(colors)], 1)
        h, w, _ = image.shape
        image = cv2.resize(image, (int(w * scale), int(h * scale)))
        cv2.putText(image, "{}: {}".format(filename, text), (0, h*scale-5), font, 2.5, text_color, thickness=3)
        cv2.imshow("image", image)
        cv2.waitKey(0)
        # end of display()

    def run(solvere, filenames, show, jsonfile):
        results = {}
        for filename in filenames:
            text, bbox, score = solver.solve(filename)
            print("{} {}".format(filename, text))
            if show:
                display(filename, text, bbox, score)
            results[filename] = { 'file': filename, 'text': text, 'bbs': bbox.tolist(), 'score': score.tolist() }
            # end of for
        if jsonfile is not None:
            with open(jsonfile, "w") as fp:
                json.dump(results, fp, indent=2)
        # end of run()

    # main routine starts here

    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='model')
    parser.add_argument('--gpu', type=int, default=-1)
    parser.add_argument('--thresh', type=float, default=DEFAULT_SCORE_THRESH)
    parser.add_argument('--dir', metavar='DIR', type=str, default=None)
    parser.add_argument('--file', metavar='FILE', nargs='+', type=str, default=None)
    parser.add_argument('--json', metavar='FILE', default=None)
    parser.add_argument('--show', action='store_true', default=False)
    args = parser.parse_args()

    if not args.dir and not args.file:
        print('Either --dir or --file must be specified.')
        exit(1)
    if args.dir and args.file:
        print('--dir and --file are exclusive.')
        exit(1)

    solver = Solver(dirname=args.model, gpu=args.gpu, score_thresh=args.thresh)

    if args.dir:
        filenames = sorted(glob.glob(os.path.join(dirname, "*.gif")))
        run(solver, filenames, show=args.show, jsonfile=args.json)
    else:
        run(solver, args.file, show=args.show, jsonfile=args.json)

# solve.py
