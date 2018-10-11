#!/usr/bin/env python

import os, json, cv2, random, argparse
import numpy as np
from scipy import ndimage

DEFAULT_DATASET = "data/dataset.json" # default dataset file (--dataset parameter)
DEFAULT_OUTPUT = "segmented-data"     # default output directory (--output parameter)
DEFAULT_PERTURB = 9                   # default perturbation count (--perturb parameter)

SEGMENT_WIDTH = 32      # segment width
SEGMENT_HEIGHT = 32     # segment height
OVERLAP_THRESHOLD = 0.4 # negative sample overlap threshold
NEGATIVE_SAMPLES = 10   # number of negative samples per input image

ROTATE_STD = 10
SHIFT_STD = 4

class Preprocess:
    dataset = []
    input_dir = None
    output_dir = None
    output_count = 0
    catalog = []

    def __init__(self, ds_file, output_dir, perturb=0):
        self.output_dir = output_dir
        self.input_dir = os.path.dirname(ds_file)
        self.perturb = perturb
        with open(ds_file, "r") as fp:
            self.dataset = json.load(fp)

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        for file_name in self.dataset:
            entry = self.dataset[file_name]
            if len(entry['text']) != 5 or len(entry['bbs']) != 5:
                continue
            print(file_name)
            gif = cv2.VideoCapture(self.input_dir + "/" + file_name)
            _, image_color = gif.read(0)
            height, width = image_color.shape[:2]
            image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)
            for i, bb in enumerate(entry["bbs"]):
                cx = (bb[0] + bb[2]) / 2
                cy = (bb[1] + bb[3]) / 2
                x0 = round(cx - SEGMENT_WIDTH / 2)
                y0 = round(cy - SEGMENT_HEIGHT / 2)
                x1 = round(cx + SEGMENT_WIDTH / 2)
                y1 = round(cy + SEGMENT_HEIGHT / 2)
                if x0 < 0:
                    x0 = 0
                    x1 = SEGMENT_WIDTH
                if y0 < 0:
                    y0 = 0
                    y1 = SEGMENT_HEIGHT
                if x1 >= width:
                    x1 = width - 1
                    x0 = x1 - SEGMENT_WIDTH
                if y1 >= height:
                    y1 = height - 1
                    y0 = y1 - SEGMENT_HEIGHT
                letter = entry['text'][i]
                segment = image_gray[y0:y1, x0:x1]
                self.output_segment(segment, file_name, 1, letter)
                for i in range(0, self.perturb):
                    angle = random.gauss(0, ROTATE_STD)
                    dx = random.gauss(0, SHIFT_STD)
                    dy = random.gauss(0, SHIFT_STD)
                    self.output_segment(segment, file_name, 1, letter, angle=angle, dx=dx, dy=dy)
            negative = []
            while len(negative) < NEGATIVE_SAMPLES:
                x0 = random.randrange(0, width-SEGMENT_WIDTH)
                y0 = random.randrange(0, height-SEGMENT_HEIGHT)
                x1 = x0 + SEGMENT_WIDTH
                y1 = y0 + SEGMENT_HEIGHT
                max_overlap = 0
                for bb in entry["bbs"]:
                    overlap = self.overlap([x0, y0, x1, y1], bb) / (bb[2] - bb[0]) / (bb[3] - bb[1])
                    max_overlap = max(max_overlap, overlap)
                if max_overlap < OVERLAP_THRESHOLD:
                    negative.append([x0, y0, x1, y1])
                    self.output_segment(image_gray[y0:y1, x0:x1], file_name, 0, ' ')
        catalog_file = self.output_dir + "/dataset.json"
        if os.path.exists(catalog_file):
            os.rename(catalog_file, catalog_file + ".orig")
        with open(catalog_file, "w") as fp:
            json.dump(self.catalog, fp, indent=-4)

    def output_segment(self, image, orig_file, label, letter, angle=0, dx=0, dy=0):
        if angle != 0:
            image = ndimage.rotate(image, angle, reshape=False, mode='nearest', cval=0.5)
        if dx != 0 or dy != 0:
            image = ndimage.interpolation.shift(image, [dx, dy], mode='nearest', cval=0.5)
        output_file = "{0:06}.png".format(self.output_count);
        self.output_count += 1
        cv2.imwrite(os.path.join(self.output_dir, output_file), image)
        self.catalog.append({ "file": output_file, "orig": orig_file, "label": label, "letter": letter })

    def overlap(self, bb1, bb2):
        sx = max(bb1[0], bb2[0])
        sy = max(bb1[1], bb2[1])
        ex = min(bb1[2], bb2[2])
        ey = min(bb1[3], bb2[3])
        w = ex - sx
        h = ey - sy
        if w > 0 and h > 0:
            return w * h
        return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mobile Suica Scraper -- Captcha Data Preprocessor')
    parser.add_argument('--dataset', default=DEFAULT_DATASET,
                        help='Captcha image dataset file (default={})'.format(DEFAULT_DATASET))
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help='Training data output directory (default={})'.format(DEFAULT_OUTPUT))
    parser.add_argument('--perturb', default=DEFAULT_PERTURB, type=int,
                        help='Number of perturbed samples to generate (default={})'.format(DEFAULT_PERTURB))
    args = parser.parse_args()

    pp = Preprocess(args.dataset, args.output, args.perturb)
    pp.run()

# end of preprocess.py
