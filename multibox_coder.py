import itertools
import numpy as np
import chainer
from chainer.backends import cuda
from chainercv import utils
from constants import *

class MultiboxCoder:
    def __init__(self, grids, aspect_ratios, variance=(0.1, 0.1)):
        size = 24
        default_bbox = []
        for k, grid in enumerate(grids):
            vstep = (IMAGE_HEIGHT - size) / (grid[0] - 1)
            hstep = (IMAGE_WIDTH  - size) / (grid[1] - 1)
            for v, u in itertools.product(range(grid[0]), range(grid[1])):
                cy = v * vstep + size / 2
                cx = u * hstep + size / 2
                default_bbox.append((cy, cx, size, size))
                for ar in aspect_ratios[k]:
                    default_bbox.append((cy, cx, size / np.sqrt(ar), size * np.sqrt(ar)))
                    default_bbox.append((cy, cx, size * np.sqrt(ar), size / np.sqrt(ar)))

        self._default_bbox = np.stack(default_bbox)
        self._variance = variance

    @property
    def xp(self):
        return chainer.backends.cuda.get_array_module(self._default_bbox)

    def to_cpu(self):
        self._default_bbox = chainer.backends.cuda.to_cpu(self._default_bbox)

    def to_gpu(self, device=None):
        self._default_bbox = chainer.backends.cuda.to_gpu(self._default_bbox, device=device)

    def encode(self, bbox, label, iou_thresh=0.5):
        xp = self.xp

        if len(bbox) == 0:
            return (
                xp.zeros(self._default_bbox.shape, dtype=np.float32),
                xp.zeros(self._default_bbox.shape[0], dtype=np.int32))

        iou = utils.bbox_iou(
            xp.hstack((
                self._default_bbox[:, :2] - self._default_bbox[:, 2:] / 2,
                self._default_bbox[:, :2] + self._default_bbox[:, 2:] / 2)),
            bbox)

        index = xp.empty(len(self._default_bbox), dtype=int)
        index[:] = -1 # background

        masked_iou = iou.copy()
        while True:
            i, j = xp.unravel_index(masked_iou.argmax(), masked_iou.shape)
            if masked_iou[i, j] < 1e-6:
                break
            index[i] = j
            masked_iou[i, :] = 0
            masked_iou[:, j] = 0

        mask = xp.logical_and(index < 0, iou.max(axis=1) >= iou_thresh)
        index[mask] = iou[mask].argmax(axis=1)

        mb_bbox = bbox[index].copy()
        mb_bbox[:, 2:] -= mb_bbox[:, :2]
        mb_bbox[:, :2] += mb_bbox[:, 2:] / 2

        mb_loc = xp.empty_like(mb_bbox)
        mb_loc[:, :2] = (mb_bbox[:, :2] - self._default_bbox[:, :2]) / \
                (self._variance[0] * self._default_bbox[:, 2:])
        mb_loc[:, 2:] = xp.log(mb_bbox[:, 2:] / self._default_bbox[:, 2:]) / \
                self._variance[1]

        mb_label = label[index] + 1
        mb_label[index < 0] = 0

        return mb_loc.astype(np.float32), mb_label.astype(np.int32)

    def decode(self, mb_loc, mb_conf, nms_thresh, score_thresh):
        xp = self.xp

        mb_bbox = self._default_bbox.copy()
        mb_bbox[:, :2] += mb_loc[:, :2] * self._variance[0] * self._default_bbox[:, 2:]
        mb_bbox[:, 2:] *= xp.exp(mb_loc[:, 2:] * self._variance[1])

        mb_bbox[:, :2] -= mb_bbox[:, 2:] / 2
        mb_bbox[:, 2:] += mb_bbox[:, :2]

        if xp == np:
            mb_conf[mb_conf > 88.72] = 88.72 # avoid overflow
        mb_score = xp.exp(mb_conf)
        mb_score /= mb_score.sum(axis=1, keepdims=True)

        # intra-class non-maximum suppression
        bbox = []
        label = []
        score = []
        for l in range(mb_conf.shape[1] - 1):
            bbox_l = mb_bbox
            score_l = mb_score[:, l + 1]

            mask = score_l >= score_thresh
            bbox_l = bbox_l[mask]
            score_l = score_l[mask]

            indices = utils.non_maximum_suppression(bbox_l, nms_thresh, score_l)
            bbox_l = bbox_l[indices]
            score_l = score_l[indices]

            bbox.append(bbox_l)
            label.append(xp.array((l,) * len(bbox_l)))
            score.append(score_l)

        # inter-class non-maximum suppression
        bbox = xp.vstack(bbox)
        label = xp.hstack(label)
        score = xp.hstack(score)
        indices = utils.non_maximum_suppression(bbox, nms_thresh, score)
        bbox = bbox[indices].astype(np.float32)
        label = label[indices].astype(np.int32)
        score = score[indices].astype(np.float32)

        return bbox, label, score
