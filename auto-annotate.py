#!/usr/bin/env python

import os, json, argparse, glob
import numpy as np
from solve import Solver

DEFAULT_GPU = -1
DEFAULT_MODEL_DIR = "prebuild-model"
DEFAULT_DATA_DIR = "data"

class AutoAnnotator:
    def __init__(self, model_dir=DEFAULT_MODEL_DIR, data_dir=DEFAULT_DATA_DIR, gpu=-1):
        self.data_dir = data_dir
        self.dataset_file = os.path.join(data_dir, "dataset.json")
        self.solver = Solver(dirname=model_dir, gpu=gpu)
        self.dataset = {}
        if os.path.exists(self.dataset_file):
            with open(self.dataset_file, "r") as fp:
                self.dataset = json.load(fp)

    def run(self):
        for giffile in sorted(glob.glob(os.path.join(self.data_dir, "*.gif"))):
            key = os.path.basename(giffile)
            if key in self.dataset:
                entry = self.dataset[key]
                if 'text' in entry and len(entry['text']) != 0:
                    print("{}: annotation already exists. skip.".format(key))
                    continue
            text, bbox, score = self.solver.solve(giffile)
            self.dataset[key] = { 'file': key, 'text': text, 'bbs': bbox.tolist() }
        with open(os.path.join(self.data_dir, "dataset.json"), "w") as fp:
            json.dump(self.dataset, fp, indent=2)

if __name__ == '__main__':    
    parser = argparse.ArgumentParser(description='Mobile Suica Scraper -- Auto-Annotator')
    parser.add_argument('--data', default=DEFAULT_DATA_DIR, metavar='DIR',
                        help='data directory (default={})'.format(DEFAULT_DATA_DIR))
    parser.add_argument('--model', default=DEFAULT_MODEL_DIR, metavar='DIR',
                        help='prebuild model directory (default={})'.format(DEFAULT_MODEL_DIR))
    parser.add_argument('--gpu', default=-1, type=int,
                        help='gpu number (default={})'.format(DEFAULT_GPU))
    args = parser.parse_args()

    aa = AutoAnnotator(model_dir=args.model, data_dir=args.data, gpu=args.gpu)
    aa.run()

# end of auto-annotate.py
