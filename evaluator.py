import copy
import numpy as np
from constants import *

from chainer import reporter, dataset, function
import chainer.training.extensions

class Evaluator(chainer.training.extensions.Evaluator):
    trigger = 1, 'epoch'
    default_name = 'validation'
    priority = chainer.training.PRIORITY_WRITER

    def __init__(self, iterator, target, label_names=None, score_thresh=DEFAULT_SCORE_THRESH, device=-1):
        if iterator is None:
            iterator = {}
        super(Evaluator, self).__init__(iterator, target, device=device)
        self.label_names = label_names
        self.score_thresh = score_thresh

    def evaluate(self):
        target = self._targets['main']
        iterator = self._iterators['main']
        xp = target.xp

        if hasattr(iterator, 'reset'):
            iterator.reset()
            it = iterator
        else:
            it = copy.copy(iterator)

        total_count = good_count = 0
        for batch in it:
            batch = dataset.convert.concat_examples(batch, self.device)
            imgs, gt_bboxes, gt_labels = batch
            pred_bboxes, pred_labels, pred_scores = target.predict(imgs)

            for pred_bbox, pred_label, pred_score, gt_label in zip(pred_bboxes, pred_labels, pred_scores, gt_labels):
                total_count += 1
                gt_len = len(gt_label)
                if len(pred_label) < gt_len:
                    continue
                if len(pred_label) > gt_len:
                    indices = xp.argsort(pred_score)[:-gt_len-1:-1]
                    pred_label = pred_label[indices]
                    pred_bbox = pred_bbox[indices]
                indices = xp.argsort(pred_bbox[:, 1])
                pred_label = pred_label[indices]
                if xp.all(pred_label == gt_label):
                    good_count += 1

        report = { 'acc': good_count / total_count }

        observation = {}
        with reporter.report_scope(observation):
            reporter.report(report, target)
        return observation
