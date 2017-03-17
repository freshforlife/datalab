import pandas as pd
from PIL import Image
import PIL
import os
from glob import glob
import cv2
from matplotlib import pyplot as plt
import numpy as np

# Paths
RAW_DIR = '../../data/raw/'
PROCESSED = '../../data/processed/'
CROP_TEST_DIR = '../../interim/train/crop/test/'
# Read 
column_name = ['image', 'height', 'width', 'x', 'y', 'sixeX', 'sizeY']
bb_box = pd.read_csv(PROCESSED + 'bbox.csv', names= column_name)

### Bounding boxes & multi output
import ujson as json
anno_classes = ['alb', 'bet', 'dol', 'lag', 'shark', 'yft']

bb_json = {}
for c in anno_classes:
    j = json.load(open('{}{}_labels.json'.format(ANNOS, c), 'r'))
    for l in j:
        if 'annotations' in l.keys() and len(l['annotations'])>0:
            bb_json[l['filename'].split('/')[-1]] = sorted(
                l['annotations'], key=lambda x: x['height']*x['width'])[-1]

# Get python raw filenames (without foldername)
raw_filenames = [f.split('/')[-1] for f in filenames]
raw_test_filenames = [f.split('/')[-1] for f in test_filenames]

# Image that have no annotation, empty bounding box
empty_bbox = {'height': 0., 'width': 0., 'x': 0., 'y': 0.}
for f in raw_filenames:
    if not f in bb_json.keys(): bb_json[f] = empty_bbox
for f in raw_test_filenames:
    if not f in bb_json.keys(): bb_json[f] = empty_bbox
 
# The sizes of images can be related to ship sizes. Get sizes for raw image
sizes = [PIL.Image.open(PATH+'train/'+f).size for f in filenames]
raw_test_sizes = [PIL.Image.open(PATH+'test/'+f).size for f in test_filenames]

# Convert dictionary into array
bb_params = ['height', 'width', 'x', 'y']
Nbins = 20
def convert_bb(bb, size):
    bb = [bb[p] for p in bb_params]
    conv_x = (size[0] / Nbins)
    conv_y = (size[1] / Nbins)
    bb[0] = max(int((bb[0]+bb[3])/conv_y), 0)
    bb[1] = max(int((bb[1]+bb[2])/conv_x), 0)
    bb[2] = max(int(bb[2]/conv_x), 0)
    bb[3] = max(int(bb[3]/conv_y), 0)
    return bb

def create_rect(bb, color='red'):
    p_tails = (bb[3], bb[4])
    p_heads = (bb[2], bb[1])
    #p_heads = (bb[3] + bb[2], bb[4] + bb[1])
    p_middle = ((p_heads[0] + p_tails[0]) / 2, (p_heads[1] + p_tails[1]) / 2)
    dist = np.sqrt((p_heads[0] - p_tails[0]) ** 2 + (p_heads[1] - p_tails[1]) ** 2)
    offset = 3.0 * dist / 4.0
    img_width = bb[5]
    img_height = bb[6]
    x_left = max(0, p_middle[0] - offset)
    x_right = min(img_width - 1, p_middle[0] + offset)
    y_up = max(0, p_middle[1] - offset)
    y_down = min(img_height - 1, p_middle[1] + offset)
    x_left, x_right, y_up, y_down = int(x_left), int(x_right), int(y_up), int(y_down)
    #return plt.Rectangle((bb[3], bb[4]), bb[2], bb[1], color=color, fill=False, lw=3)
    return plt.Rectangle((x_left, y_down), x_right, y_up, color=color, fill=False, lw=3)


os.chdir(RAW_DIR + 'test')
g = glob('*')

if not os.path.isdir(CROP_TEST_DIR):
    os.makedirs(CROP_TEST_DIR)

sizes = [PIL.Image.open(f).size for f in g]

for i,j in enumerate(g):
    bb = bb_box.loc[bb_box['image'] == g[i]].iloc[:,[0,1,2,3,4,5,6]].values
    im = cv2.imread(g[i])
    #im = cv2.resize(im, (224, 224))
    plt.imshow(im)
    ax=plt.gca()
    #if(abs(bb[0,][1] - bb[0,][4]) < 60 or abs(bb[0,][1] - bb[0,][4]) < 60):
    ax.add_patch(create_rect(bb[0,]))
    name=CROP_TEST_DIR + j
    print(name)
    plt.savefig(name)
    plt.cla()
