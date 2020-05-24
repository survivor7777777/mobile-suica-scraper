import os, json, cv2
from chainer.datasets.tuple_dataset import TupleDataset
import numpy as np

from constants import *
from multibox_coder import MultiboxCoder

class Dataset(TupleDataset):
    def __init__(self, dataset_dir):
        dataset_file = os.path.join(dataset_dir, "dataset.json")
        with open(dataset_file, 'r') as fp:
            metadata = json.load(fp)

        class_ids = {}
        for entry in metadata.values():
            for letter in entry['text']:
                class_ids[letter] = 1
        for i, letter in enumerate(sorted(class_ids.keys())):
            class_ids[letter] = i

        img_data = []
        bbs_data = []
        lbs_data = []
        count = 0
        for entry in metadata.values():
            image_file = entry['file']
            bbs = entry['bbs']
            text = entry['text']
            if bbs is None or len(bbs) != NCHARS or len(text) != NCHARS:
                continue
            count += 1
            gif = cv2.VideoCapture(os.path.join(dataset_dir, image_file))
            _, color_image = gif.read(0)
            gray_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
            h, w = gray_image.shape[:2]
            img = np.array(gray_image / 255.0, dtype=np.float32).reshape(1, h, w)
            img_data.append(img)

            bbs = np.array(bbs, dtype=np.float32)
            bbs_data.append(bbs)

            lbs = np.array(list(map(lambda e: class_ids[e], text)), dtype=np.int32)
            lbs_data.append(lbs)

        self._count = count
        self._n_class = len(class_ids)
        self._class_ids = class_ids
        self._class_labels = [ l for l in sorted(class_ids.keys(), key=lambda x: class_ids[x]) ]
        self._img_data = img_data
        self._bbs_data = bbs_data
        self._lbs_data = lbs_data

    def __len__(self):
        return self._count

    @property
    def n_class(self):
        return self._n_class

    @property
    def class_ids(self):
        return self._class_ids

    @property
    def class_labels(self):
        return self._class_labels

    def __getitem__(self, index):
        if isinstance(index, slice):
            current, stop, step = index.indices(len(self))
            return [ self.get_example(i) for i in range(current, stop, step) ]
        elif isinstance(index, list):
            return [ self.get_example(i) for i in index ]
        else:
            return self.get_example(index)

    def get_example(self, i):
        return self._img_data[i], self._bbs_data[i], self._lbs_data[i]
