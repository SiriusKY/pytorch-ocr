import json
import pandas as pd
from pathlib import Path
from itertools import repeat
from collections import OrderedDict
from torchvision import transforms
from PIL import Image
from data_loader.datasets import get_label_dict
from .prefix_beam_search import decode


def ensure_dir(dirname):
    dirname = Path(dirname)
    if not dirname.is_dir():
        dirname.mkdir(parents=True, exist_ok=False)


def read_json(fname):
    fname = Path(fname)
    with fname.open('rt') as handle:
        return json.load(handle, object_hook=OrderedDict)


def write_json(content, fname):
    fname = Path(fname)
    with fname.open('wt') as handle:
        json.dump(content, handle, indent=4, sort_keys=False)


def inf_loop(data_loader):
    ''' wrapper function for endless data loader. '''
    for loader in repeat(data_loader):
        yield from loader


def recognize(image_path, model, label_dict, device):
    img = Image.open(image_path).convert("RGB")
    tgt_height = 64

    width, height = img.size
    reshape_width = tgt_height * (width / height)
    img = img.resize([int(reshape_width), int(tgt_height)])
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
    ])
    img = transform(img).unsqueeze(0).to(device)
    output = model(img)

    output = output.squeeze(1).cpu().detach().numpy()
    _, ind2ch = get_label_dict(label_dict)
    labels, score = decode(output, beam_size=20, blank=98)
    pred = ''
    for ch in labels:
        ch = ind2ch[ch]
        if ch not in ['UNK', 'SOS', 'EOS', 'SPACE', 'BLANK']:
            pred += ch
    return pred


def contain_chinese(word):
    for ch in word:
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False


class MetricTracker:
    def __init__(self, *keys, writer=None):
        self.writer = writer
        self._data = pd.DataFrame(index=keys, columns=['total', 'counts', 'average'])
        self.reset()

    def reset(self):
        for col in self._data.columns:
            self._data[col].values[:] = 0

    def update(self, key, value, n=1):
        if self.writer is not None:
            self.writer.add_scalar(key, value)
        self._data.total[key] += value * n
        self._data.counts[key] += n
        self._data.average[key] = self._data.total[key] / self._data.counts[key]

    def avg(self, key):
        return self._data.average[key]

    def result(self):
        return dict(self._data.average)
