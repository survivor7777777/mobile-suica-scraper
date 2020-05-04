import chainer
import chainer.functions as F
from chainer import initializers
import chainer.links as L

class Multibox(chainer.Chain):
    def __init__(
            self, n_class, aspect_ratios,
            initialW=initializers.LeCunUniform(), initial_bias=initializers.Zero()):
        self.n_class = n_class

        super(Multibox, self).__init__()
        with self.init_scope():
            self.loc = chainer.ChainList()
            self.conf = chainer.ChainList()

        init = {'initialW': initialW, 'initial_bias': initial_bias}
        for ar in aspect_ratios:
            n = len(ar) * 2 + 1
            self.loc.add_link(L.Convolution2D(n * 4, 3, pad=1, **init))
            self.conf.add_link(L.Convolution2D(n * self.n_class, 3, pad=1, **init))

    def forward(self, xs):
        mb_locs = []
        mb_confs = []
        for i, x in enumerate(xs):
            mb_loc = self.loc[i](x)
            mb_loc = F.transpose(mb_loc, (0, 2, 3, 1))
            mb_loc = F.reshape(mb_loc, (mb_loc.shape[0], -1, 4))
            mb_locs.append(mb_loc)

            mb_conf = self.conf[i](x)
            mb_conf = F.transpose(mb_conf, (0, 2, 3, 1))
            mb_conf = F.reshape(mb_conf, (mb_conf.shape[0], -1, self.n_class))
            mb_confs.append(mb_conf)

        mb_locs = F.concat(mb_locs, axis=1)
        mb_confs = F.concat(mb_confs, axis=1)

        return mb_locs, mb_confs
