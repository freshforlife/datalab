import time
print(time.ctime()) # Current time
start_time = time.time()

from keras.applications.inception_v3 import InceptionV3
#from keras.applications.vgg16 import VGG16
#from keras.applications.resnet50 import ResNet50
from keras.models import Model, load_model
from keras.layers import Flatten, Dense, AveragePooling2D, MaxPooling2D
from keras.layers.normalization import BatchNormalization
from keras.preprocessing import image, sequence
from keras.callbacks import EarlyStopping, CSVLogger, ReduceLROnPlateau, ModelCheckpoint
from keras.optimizers import SGD, RMSprop, Adam
from keras.utils.np_utils import to_categorical
from sklearn.metrics import log_loss, confusion_matrix
from itertools import chain, islice
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import itertools
import os
import os.path as op
import glob
import PIL
from keras import backend as K
K.set_image_dim_ordering('tf')
import ipdb

os.environ["CUDA_VISIBLE_DEVICES"] = "1"
PATH = "../../data/interim/train/devcrop/" 
MODELS = "../../models/"
seed = 7
np.random.seed(seed)

from src.data import DataModel as dm

class InceptionFineTuning(object):
    '''Using keras with pretrained InceptionV3'''
    def __init__(self):
        self.f = dm.ProjFolder()
        self.classes = ['ALB',
                        'BET',
                        'DOL',
                        'LAG',
                        'NoF',
                        'OTHER',
                        'SHARK',
                        'YFT']

    def ProbabilityDistribution(self,df):
        f, ((ax1, ax2, ax3, ax4), (ax5, ax6, ax7, ax8)) = plt.subplots(2, 4, sharex='col', sharey='row')
        ax1.hist(df["ALB"],bins=20)
        ax1.set_title("ALB")
        ax2.hist(df["BET"],bins=20)
        ax2.set_title("BET")
        ax3.hist(df["DOL"],bins=20)
        ax3.set_title("DOL")
        ax3.set_xticks(np.arange(0,1.2,0.2))
        ax3.set_xlim(0, 1)
        ax4.hist(df["LAG"],bins=20)
        ax4.set_title("LAG")
        ax5.hist(df["NoF"],bins=20)
        ax5.set_title("NoF")
        ax6.hist(df["OTHER"],bins=20)
        ax6.set_title("OTHER")
        ax7.hist(df["SHARK"],bins=20)
        ax7.set_title("SHARK")
        ax7.set_xticks(np.arange(0,1.2,0.2))
        ax8.hist(df["YFT"],bins=20)
        ax8.set_title("YFT")
        name=PATH + 'pdInceptionCropSmall.png'
        plt.savefig(name)
        plt.cla()


    def plot_confusion_matrix(self, cm, 
                              normalize=False,
                              title='Confusion matrix',
                              cmap=plt.cm.Blues):
        """
        This function prints and plots the confusion matrix.
        Normalization can be applied by setting `normalize=True`.
        """
        plt.imshow(cm, interpolation='nearest', cmap=cmap)
        plt.title(title)
        plt.colorbar()
        tick_marks = np.arange(len(self.classes))
        plt.xticks(tick_marks, self.classes, rotation=45)
        plt.yticks(tick_marks, self.classes)

        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            print("Normalized confusion matrix")
        else:
            print('Confusion matrix, without normalization')

        print(cm)

        thresh = cm.max() / 2.
        for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
            plt.text(j, i, cm[i, j],
                     horizontalalignment="center",
                     color="white" if cm[i, j] > thresh else "black")

        plt.tight_layout()
        plt.ylabel('True label')
        plt.xlabel('Predicted label')
        return


    def FineTuning(self):
        img_width = 299
        img_height = 299
        batch_size = 32
        learning_rate = 1e-3
        nbr_epoch = 1
        nbr_train_samples = len(glob.glob(PATH + 'train/*/*.jpg'))/batch_size*batch_size
        nbr_val_samples = len(glob.glob(PATH + 'val/*/*.jpg'))/batch_size*batch_size

        print("Parametres: img_width {}, batch_size {}, number of train {}, number of val {}".format(img_width, batch_size, nbr_train_samples, nbr_val_samples))

        # Transformation for train
        train_datagen = image.ImageDataGenerator(rescale=1./255,)
                #shear_range=0.1,
                #zoom_range=0.1,
                #rotation_range=10.,
                #width_shift_range=0.1,
                #height_shift_range=0.1,
                #horizontal_flip=True)

        trn_generator = train_datagen.flow_from_directory(
                PATH + 'train',
                target_size = (img_width, img_height),
                batch_size = batch_size,
                shuffle = False,
                #save_to_dir = PATH + 'TransfTrain/',
                #save_prefix = 'aug',
                #classes = self.classes,
                class_mode = None,
                seed = seed)


        #trn_np =  np.concatenate([trn_generator.next() for i in range(trn_generator.nb_sample)])

        # Transformation for validation set
        val_datagen = image.ImageDataGenerator(rescale=1./255)

        val_generator = val_datagen.flow_from_directory(
            PATH + 'val',
            target_size=(img_width, img_height),
            batch_size=batch_size,
            shuffle = False,
            #save_to_dir = PATH + 'TransfVal/',
            #save_prefix = 'aug',
            #classes = self.classes,
            class_mode = None,
            seed = seed)

        filenames = trn_generator.filenames
        val_filenames = val_generator.filenames

        ### Bounding boxes & multi output
        import ujson as json
        #anno_classes = ['alb', 'bet', 'dol', 'lag', 'shark', 'yft']
        anno_classes = glob.glob(op.join(self.f.data_external_annos, '*.json' ))

        bb_json = {}
        for c in anno_classes:
            j = json.load(open(op.join(c), 'r'))
            for l in j:
                if 'annotations' in l.keys() and len(l['annotations'])>0:
                    bb_json[l['filename'].split('/')[-1]] = sorted(
                        l['annotations'], key=lambda x: x['height']*x['width'])[-1]

        ## Get python raw filenames
        raw_filenames = [f.split('/')[-1] for f in filenames]
        raw_val_filenames = [f.split('/')[-1] for f in val_filenames]

        ## Image that have no annotation, empty bounding box
        empty_bbox = {'height': 0., 'width': 0., 'x': 0., 'y': 0.}

        for f in raw_filenames:
            if not f in bb_json.keys(): bb_json[f] = empty_bbox

        for f in raw_val_filenames:
            if not f in bb_json.keys(): bb_json[f] = empty_bbox
        # 
        ## The sizes of images can be related to ship sizes. Get sizes for raw image
        sizes = [PIL.Image.open(PATH+'train/'+f).size for f in filenames]
        raw_val_sizes = [PIL.Image.open(PATH+'val/'+f).size for f in val_filenames]

        ## Convert dictionary into array
        bb_params = ['height', 'width', 'x', 'y']
        def convert_bb(bb, size):
            bb = [bb[p] for p in bb_params]
            conv_x = (img_width /float(size[0]))
            conv_y = (img_height / float(size[1]))
            bb[0] = max((bb[0]+bb[3])*conv_y, 0)
            bb[1] = max((bb[1]+bb[2])*conv_x, 0)
            bb[2] = max(bb[2]*conv_x, 0)
            bb[3] = max(bb[3]*conv_y, 0)
            #ipdb.set_trace()
            return bb

        ## Tranform box in terms of defined compressed image size (224)
        trn_bbox = np.stack([convert_bb(bb_json[f], s) for f,s in zip(raw_filenames, sizes)],).astype(np.float32)
        val_bbox = np.stack([convert_bb(bb_json[f], s) for f,s in zip(raw_val_filenames, raw_val_sizes)],).astype(np.float32)

        
        print('Loading InceptionV3 Weights ...')
        base_model = InceptionV3(include_top=False, weights='imagenet',
                            input_tensor=None, input_shape=(299, 299, 3))
        # Note that the preprocessing of InceptionV3 is:
        # (x / 255 - 0.5) x 2

        print("--- Adding on top layers %.1f seconds ---" % (time.time() -
                                                             start_time))
        output = base_model.get_layer(index=-1).output  # Shape: (8, 8, 2048)
        output = AveragePooling2D((8, 8), strides=(8, 8),
                                  name='avg_pool')(output)
        output = Flatten(name='flatten')(output)
        output = Dense(4, activation='linear', name='bb')(output)
        # output = Dense(8, activation='softmax', name='predictions')(output)

        model = Model(base_model.input, output)

        optimizer = SGD(lr=learning_rate, momentum=0.9, decay=0.0,
                        nesterov=True)
        model.compile(loss='categorical_crossentropy', optimizer=optimizer,
                      metrics=['accuracy'], loss_weights=[.001])
        #print(model.summary())

        earlistop = EarlyStopping(monitor='val_loss', min_delta=0, patience=0, verbose=1, mode='auto')
        csv_logger = CSVLogger(PATH + 'trainingInceptionCropSmall.log')
        reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.1, patience=1, verbose=1, min_lr=1e-5)
        SaveModelName = MODELS + "InceptionV3.h5"
        best_model = ModelCheckpoint(SaveModelName, monitor='val_acc', verbose = 1, save_best_only = True)
        callbacks_list = [earlistop, csv_logger, reduce_lr, best_model]

        # def generator_labels():
        #    for line in trn_bbox:
        #        # create numpy arrays of input data
        #        # and labels, from each line in the file
        #        y = process_line(line)
        #        yield (line)

        # train_generator = zip(trn_generator, iter(trn_bbox))
        # trn_bbox_generator = (n for n in trn_bbox)

        def batch(iterable, n=1):
            l = len(iterable)
            for ndx in range(0, l, n):
                yield iterable[ndx:min(ndx + n, l)]

        trn_bbox_generator = (n for n in batch(trn_bbox, batch_size))
        val_bbox_generator = (n for n in batch(val_bbox, batch_size))
        train_generator = itertools.izip(trn_generator, trn_bbox_generator)
        validation_generator = itertools.izip(val_generator, val_bbox_generator)

        #ipdb.set_trace()

        # model.fit_generator(
        #        trn_generator,
        #        samples_per_epoch = nbr_train_samples,
        #        nb_epoch = nbr_epoch,
        #        validation_data = val_generator,
        #        nb_val_samples = nbr_val_samples,
        #        callbacks = callbacks_list)

        model.fit_generator(
                train_generator,
                samples_per_epoch=nbr_train_samples,
                nb_epoch=nbr_epoch)
        #validation_data = validation_generator,
        #nb_val_samples = nbr_val_samples)
        #        callbacks = callbacks_list)


        # Use the best model epoch
        print("--- Starting prediction %.1f seconds ---" % (time.time() - start_time))
        InceptionV3_model = load_model(SaveModelName)

        # Data augmentation for prediction 
        nbr_augmentation = 5
        val_datagen = image.ImageDataGenerator(
                rescale=1./255,
                shear_range=0.1,
                zoom_range=0.1,
                width_shift_range=0.1,
                height_shift_range=0.1,
                horizontal_flip=True)
        for idx in range(nbr_augmentation):
            print('{}th augmentation for testing ...'.format(idx))
            random_seed = np.random.random_integers(0, 100000)

            val_generator = val_datagen.flow_from_directory(
                    PATH + 'val',
                    target_size=(img_width, img_height),
                    batch_size=batch_size,
                    shuffle = False, # Important !!!
                    seed = random_seed,
                    classes = None,
                    class_mode = None)

            print('Begin to predict for testing data ...')
            if idx == 0:
                preds = model.predict_generator(val_generator, nbr_val_samples)
            else:
                preds += model.predict_generator(val_generator, nbr_val_samples)

        preds /= nbr_augmentation

        # Get label for max probability 
        pred_labels_one = [ pred.argmax() for pred in preds ]

        # Plot confusion matrix
        cnf_matrix = confusion_matrix(val_generator.classes, pred_labels_one)
        plt.figure()
        self.plot_confusion_matrix(cnf_matrix,
                                   normalize=False,
                                   title='Confusion matrix')
        plt.savefig(PATH + 'cmInceptionCropSmall.png',
                    bbox_inches='tight')

        # Plot probability distribution
        df = pd.DataFrame(preds)
        df.columns = self.classes
        self.ProbabilityDistribution(df)
        print("--- End %.1f seconds ---" % (time.time() - start_time))

if __name__ == '__main__':
    os.chdir(op.dirname(op.abspath(__file__)))
    InceptionFineTuning().FineTuning()
