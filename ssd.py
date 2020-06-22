import chainer

from extractor import Extractor
from multibox import Multibox
from multibox_coder import MultiboxCoder

class SSD(chainer.Chain):
    def __init__(self, n_class, n_channel, grids, aspect_ratios, variance, nms_thresh, score_thresh):
        super(SSD, self).__init__()
        n_feature_map = len(grids)
        with self.init_scope():
            self.extractor = Extractor(n_channel=n_channel)
            self.multibox = Multibox(n_class+1, aspect_ratios)
        self.nms_thresh = nms_thresh
        self.score_thresh = score_thresh
        self.coder = MultiboxCoder(grids=grids, aspect_ratios=aspect_ratios)

    @property
    def insize(self):
        return self.extractor.insize

    @property
    def n_class(self):
        return self.multibox.n_class - 1

    def to_cpu(self):
        super(SSD, self).to_cpu()
        self.coder.to_cpu()

    def to_gpu(self, device=None):
        super(SSD, self).to_gpu(device)
        self.coder.to_gpu(device)

    def forward(self, x):
        return self.multibox(self.extractor(x))

    def predict(self, imgs):
        x = [ self.xp.array(img) for img in imgs ]

        with chainer.using_config('train', False), \
          chainer.function.no_backprop_mode():
            x = chainer.Variable(self.xp.stack(x))
            mb_locs, mb_confs = self.forward(x)
            mb_locs, mb_confs = mb_locs.array, mb_confs.array

        bboxes = []
        labels = []
        scores = []
        for mb_loc, mb_conf in zip(mb_locs, mb_confs):
            bbox, label, score = self.coder.decode(
                mb_loc, mb_conf, self.nms_thresh, self.score_thresh)
            bboxes.append(bbox)
            labels.append(label)
            scores.append(score)

        return bboxes, labels, scores
