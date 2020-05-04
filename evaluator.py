import copy
import numpy as np
from constants import *

from chainer import reporter
import chainer.training.extensions
from chainercv.utils import apply_to_iterator

class Evaluator(chainer.training.extensions.Evaluator):
    trigger = 1, 'epoch'
    default_name = 'validation'
    priority = chainer.training.PRIORITY_WRITER

    def __init__(self, iterator, target, label_names=None, score_thresh=DEFAULT_SCORE_THRESH):
        if iterator is None:
            iterator = {}
        super(Evaluator, self).__init__(iterator, target)
        self.label_names = label_names
        self.score_thresh = score_thresh

    def evaluate(self):
        target = self._targets['main']
        iterator = self._iterators['main']

        if hasattr(iterator, 'reset'):
            iterator.reset()
            it = iterator
        else:
            it = copy.copy(iterator)

        in_values, out_values, rest_values = apply_to_iterator(target.predict, it)
        del in_values

        pred_bboxes, pred_labels, pred_scores = out_values
        gt_bboxes, gt_labels = rest_values

        total_count = good_count = 0
        for pred_bbox, pred_label, pred_score, gt_label in zip(pred_bboxes, pred_labels, pred_scores, gt_labels):
            total_count += 1
            gt_len = len(gt_label)
            if len(pred_label) < gt_len:
                continue
            if len(pred_label) > gt_len:
                indices = np.argsort(pred_score)[:-gt_len-1:-1]
                pred_label = pred_label[indices]
                pred_bbox = pred_bbox[indices]
            indices = np.argsort(pred_bbox[:, 1])
            pred_label = pred_label[indices]
            if np.all(pred_label == gt_label):
                good_count += 1

        report = { 'acc': good_count / total_count }

        observation = {}
        with reporter.report_scope(observation):
            reporter.report(report, target)
        return observation
