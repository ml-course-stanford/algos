#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

from __future__ import division
import sys, os, logging, re, email, argparse, stat, tempfile, math, time
import numpy as np

from email.parser import Parser
from collections import defaultdict, OrderedDict
from operator import itemgetter

from sklearn.feature_selection import SelectKBest, f_classif

from timber_exceptions import NaturesError
from patterns_factory import MetaPattern

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(levelname)s: %(filename)s: %(funcName)s: %(message)s')
#ch = logging.StreamHandler(sys.stdout)
#ch.setLevel(logging.DEBUG)
#ch.setFormatter(formatter)
#fh = logging.FileHandler(os.path.join(tempfile.gettempdir(), time.strftime("%d%m%y_%H%M%S", time.gmtime())+'.log'), mode = 'w')
#fh.setLevel(logging.DEBUG)
##fh.setFormatter(formatter)
#logger.addHandler(fh)
#logger.addHandler(ch)


class Vectorize(object):
    '''
    Build matrix MxN matrix :
        N - count of samples in collection dir ;
        M - count of features, provided by rules
            from appropriate pattern ;

    Appropriate pattern - instance of Spam/Ham/Info/NetsPattern classes :
        passed class name (label) define pattern, => features set ;

    Supported patterns are : spam, ham, nets, info
    '''

    SUPPORTED_CLASSES = ['spam', 'ham', 'nets', 'info']

    SETS_NAMES = ['X_train', 'Y_train', 'X_test', 'Y_test']

    def __init__(self, train_dir, label, score):

        if label not in self.SUPPORTED_CLASSES:
            raise NaturesError('Don\'t have any module with rules for '+\
                                label.upper()+' class\nSupported classes : '+\
                                ', '.join(self.SUPPORTED_CLASSES))

        self.train_dir = train_dir
        self.label = label
        self.penalty = score
        self.features_dict = dict()

        [ self.__setattr__(name, list()) for name in self.SETS_NAMES ]

        for path in [ os.path.join(self.train_dir, subdir) for subdir in self.SUPPORTED_CLASSES+['test'] ]:

            logger.debug('  Subdir : '+path+'\n')
            pathes_gen = self.__get_path(path)
            expected_len = None
            msg_path = ''
            comp_ratios = list()
            entropies = list()

            while(True):

                try:
                    msg_path = next(pathes_gen)

                    x_labeled_vector = self.__vectorize(msg_path)

                    # todo: collect ratio and entropy, just to observe consequences for these two metrics

                    if len(self.features_dict) == 0:
                        self.features_dict = dict(enumerate(map(itemgetter(0), x_labeled_vector)))

                    x_vector = tuple(map(itemgetter(1), x_labeled_vector))
                    #logger.debug('\n\tx_vector ===> '.upper()+str(x_vector)+'\n')

                    if expected_len is None:
                        expected_len = len(x_vector)

                    elif expected_len != len(x_vector):
                        #logger.error('expected length: '+str(expected_len))
                        #logger.error('vector length : '+str(len(x_vector)))
                        #logger.error('path: '+msg_path)
                        raise Exception('X_vectors from one collection have different dimentions !')


                    y_vector = None

                    if os.path.basename(path) == 'test':

                        self.X_test.append(x_vector)

                        y_vector = os.path.basename(msg_path)

                        self.Y_test.append(y_vector)

                    else:

                        self.X_train.append(x_vector)

                        if self.label == os.path.basename(path):
                            y_vector = 1.0

                        else:
                            y_vector = 0.0

                        self.Y_train.append(y_vector)

                    logger.debug('\n\ty_vector ===> '.upper()+str(y_vector)+'\n')

                except StopIteration as err:
                    break

                except Exception as err:
                    logger.debug('Can\'t extract features from "'+msg_path+'", so it will be skipped !')
                    logger.debug(str(err))
                    pass

        [ self.__setattr__(name, tuple(self.__getattribute__(name))) for name in self.SETS_NAMES ]

        logger.info('  Successfully built train and test datasets with parameters: \n')
        logger.info('\tPath to collections => '+str(self.train_dir).upper())
        logger.info('\tClass => '+str(self.label).upper())
        logger.info('\tPenalty score => '+str(self.penalty)+'\n')

    def __get_path(self, path):
        '''
        :return: generator with pathes to emails
        -- checks collections dirs
        -- constructs pathes to emails,
        keep them in generator object
        '''
        checks = {
                    stat.S_IFREG : lambda fd: os.stat(fd).st_size,
                    stat.S_IFDIR : lambda d: os.listdir(d)
        }

        mode = filter(lambda key: os.stat(path).st_mode & key, checks.keys())
        f = checks.get(*mode)
        if not f(path):
            logger.error('Collection dir : "'+path + '" is empty !')
            sys.exit(1)

        msg_path = path
        if mode[0] == stat.S_IFREG:
            logger.debug(msg_path)
            yield msg_path

        elif mode[0] == stat.S_IFDIR:
            for p, subdir, docs in os.walk(path):
                for d in docs:
                    msg_path = os.path.join(p,d)
                    yield msg_path

    def __vectorize(self, doc_path):
        '''
        :param doc_path: path to email
        :return: vector of this email
        '''

        parser = Parser()
        with open(doc_path, 'rb') as f:
            M = parser.parse(f)

        pattern_cls = MetaPattern.New(self.label)
        logger.debug('\n\temail to vectorize ==> '.upper() +doc_path)
        logger.debug('\n\tpattern class ==> '+self.label+'\n')

        pattern_instance = pattern_cls(msg=M, score=self.penalty)
        vector = pattern_instance.__dict__

        vector.pop('penalty_score'.upper())

        if self.label == 'spam':

            if float((os.stat(doc_path).st_size)/1024) < 4.0:
                vector['small_size'] = 1
            else:
                vector['small_size'] = 0

        logger.debug('\tsuccessfully created vector with :\n')
        logger.debug("\t\tlength : ".upper()+str(len(vector)))

        non_zero = [v for k,v in vector.iteritems() if float(v) !=0.0 ]
        logger.debug("\t\tnon_zero features count : ".upper()+str(len(non_zero)))

        vector = tuple(sorted([(k.upper(),value) for k,value in vector.items()],key=itemgetter(0)))
        logger.debug('\n\tx_vector :\n'.upper())
        for k,v in vector :
            logger.debug('\t\t{0:33} {1:4} {2:10}'.format(k, '===>', str(round(v,5))))

        #self.features_dict = dict(enumerate(map(itemgetter(0),vector)))
        #msg_vector = tuple(map(itemgetter(1),vector))
        #logger.debug('\nvector ===> '+str(msg_vector)+'\n')

        return vector

    #def __normalize(self):
        #pass

    def load_data(self):
        '''
        :return: matrixes for train and test collections
        '''

        check_list = [ (name, self.__getattribute__(name)) \
                       for name in self.SETS_NAMES if len(self.__getattribute__(name))==0 ]
        if check_list:
            empty = map(itemgetter(0), check_list)
            raise NaturesError('Found empty datasets : '+', '.join(empty)+', please, check log for any ideas.')

        return self.X_train, self.Y_train, self.X_test, self.Y_test

    def transform(self, k_best=20):
        '''
        use SelectKBest selector class with ANOVA F-value
        regressors set to choose k-best features
        :return: reduced matrixes of X_vectors and Y_vectors
        '''
        self.selector = SelectKBest(score_func=f_classif, k=k_best)

        X = self.selector.fit_transform(self.X_train, self.Y_train)
        x = self.selector.transform(self.X_test)

        return X, self.Y_train, x, self.Y_test

    def support(self):
        '''
        :return: numpy array with indices of k_best features
        '''

        if not hasattr(self, 'selector'):
            raise AttributeError('Selector class wasn\'t initialized, \
                                    try call vectorizer.transform(X, k_best) method first !')

        indices = self.selector.get_support(indices=True)
        features_dict = dict([ (index,name) for index,name in self.features_dict.items() if index in indices ])

        return features_dict

    def dump_dataset(self, to_file=None):
        '''
        :param to_file: flag, which triggered whether or not
                        to dump datasets on disk ;
        :return: copy datasets and transforms them in np.matrixes
        '''

        datasets = ( np.array(x) for x in (self.__getattribute__(name) for name in self.SETS_NAMES) )
        #logger.debug(type(self.X_train))
        if to_file is not None:

            try:
                timestamp = time.strftime("%d%m%y_%H%M%S", time.gmtime())
                dump_path = os.path.join(self.train_dir, name+'_'+self.label+'_features_'+timestamp+'.txt')
                [ dataset.tofile(dump_path, sep=",", format="%s") for dataset, name in zip(tuple(datasets), names) ]
            except Exception as err:
                logger.error('Can\'t dump datasets to '+path+' !')
                logger.error(str(err))
                pass

        return datasets
