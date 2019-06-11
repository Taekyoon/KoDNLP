from typing import List, Dict
import json
from pathlib import Path

from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader

from configs.constants import INPUT_VOCAB_FILENAME, TAG_VOCAB_FILENAME, CLASS_VOCAB_FILENAME, \
    TRAIN_DATASET_FILENAME, VALIDATION_DATASET_FILENAME, INSTANT_DATASET_FILENAME, RANDOM_SEED

from data.vocab import Vocabulary
from utils import make_dir_if_not_exist, get_filelines
from data.dataset import NERDatasetFromJSONFile, SLUDatasetFromJSONFile


class DatasetBuilder(object):
    @property
    def input_vocab(self):
        return self._input_vocab

    @property
    def tag_vocab(self):
        return self._label_vocab

    @property
    def word_to_idx(self):
        return self._input_vocab.word_to_idx

    @property
    def tag_to_idx(self):
        return self._label_vocab.word_to_idx

    def _split_into_valid_and_train(self, input, label, test_size=0.1, random_state=RANDOM_SEED):
        raise NotImplementedError()

    def _numerize_from_text(self, data: List[str], vocab: Vocabulary):
        splited_data = self._splitify(data)

        return [vocab.to_indices(s_d) for s_d in splited_data]

    def _splitify(self, data: List[str]) -> List[List]:
        return [s.split() for s in data]

    def _load_text(self, path: Path) -> List[str]:
        dataset = list()
        filelines = get_filelines(path)

        with open(path, 'r') as textfile:
            for i in range(filelines):
                textline = ''
                try:
                    textline = textfile.readline().rstrip().replace('\n', '')
                except ValueError() as e:
                    pass

                dataset.append(textline)

        return dataset

    def _save_as_json(self, obj: Dict, json_path: str) -> None:
        with open(json_path, 'w') as jsonfile:
            json.dump(obj, jsonfile, indent=4)

        return

    def _build_dataset_dir(self):
        make_dir_if_not_exist(self._dataset_dir)


class NERDatasetBuilder(DatasetBuilder):
    def __init__(self,
                 input_path: Path,
                 label_path: Path,
                 file_type: str = 'text',
                 input_vocab: Vocabulary = None,
                 label_vocab: Vocabulary = None,
                 dataset_dir: str = Path('./dataset/ner')):
        self._input_path = input_path
        self._label_path = label_path
        self._file_type = file_type

        if file_type == 'text':
            self._raw_input = self._load_text(self._input_path)
            self._raw_label = self._load_text(self._label_path)
        else:
            raise NotImplementedError()

        self._input_vocab = input_vocab
        self._label_vocab = label_vocab

        self._dataset_dir = dataset_dir
        self._train_data_path = list()
        self._valid_data_path = list()

        self._build_dataset_dir()

    def build_vocabulary(self,
                         max_size: int = None,
                         min_freq: int = 1) -> None:
        input_vocab_path = self._dataset_dir / INPUT_VOCAB_FILENAME
        label_vocab_path = self._dataset_dir / TAG_VOCAB_FILENAME

        self._input_vocab = Vocabulary(max_size=max_size, min_freq=min_freq, bos_token=None, eos_token=None)
        self._label_vocab = Vocabulary(unknown_token=None)

        input_data = self._splitify(self._raw_input)
        label_data = self._splitify(self._raw_label)

        self._input_vocab.fit(input_data)
        self._label_vocab.fit(label_data)

        self._input_vocab.to_json(input_vocab_path)
        self._label_vocab.to_json(label_vocab_path)

        return

    def build_trainable_dataset(self,
                                train_data_path: str = None,
                                valid_data_path: str = None) -> None:
        if self._input_vocab is None or self._label_vocab is None:
            raise ValueError()

        train_data = dict()
        train_data_path = self._dataset_dir / TRAIN_DATASET_FILENAME if train_data_path is None else train_data_path

        valid_data = dict()
        valid_data_path = self._dataset_dir / VALIDATION_DATASET_FILENAME if valid_data_path is None else valid_data_path

        train_raw_data, valid_raw_data = self._split_into_valid_and_train(self._raw_input, self._raw_label)

        train_data['inputs'] = self._numerize_from_text(train_raw_data[0], self._input_vocab)
        train_data['entities'] = self._numerize_from_text(train_raw_data[1], self._label_vocab)

        valid_data['inputs'] = self._numerize_from_text(valid_raw_data[0], self._input_vocab)
        valid_data['entities'] = self._numerize_from_text(valid_raw_data[1], self._label_vocab)

        self._save_as_json(train_data, train_data_path)
        self._save_as_json(valid_data, valid_data_path)

        self._train_data_path.append(train_data_path)
        self._valid_data_path.append(valid_data_path)

        return

    def build_data_loader(self, batch_size, limit_pad_len, enable_length=True):
        train_dataset = NERDatasetFromJSONFile(self._train_data_path[0],
                                               limit_pad_len=limit_pad_len,
                                               enable_length=enable_length)

        valid_dataset = NERDatasetFromJSONFile(self._valid_data_path[0])

        train_data_loader = DataLoader(train_dataset,
                                       batch_size=batch_size,
                                       shuffle=True,
                                       num_workers=4,
                                       drop_last=True)

        valid_data_loader = DataLoader(valid_dataset,
                                       batch_size=1)

        return train_data_loader, valid_data_loader

    def _split_into_valid_and_train(self, input, label, test_size=0.1, random_state=RANDOM_SEED):
        input_train, input_test, label_train, label_test = train_test_split(input, label,
                                                                            test_size=test_size,
                                                                            random_state=random_state)

        return (input_train, label_train), (input_test, label_test)


class SLUDatasetBuilder(DatasetBuilder):
    def __init__(self,
                 input_path: Path,
                 label_path: Path,
                 class_path: Path,
                 file_type: str = 'text',
                 input_vocab: Vocabulary = None,
                 label_vocab: Vocabulary = None,
                 class_vocab: Vocabulary = None,
                 dataset_dir: str = Path('./dataset/slu')):
        self._input_path = input_path
        self._label_path = label_path
        self._class_path = class_path
        self._file_type = file_type

        if file_type == 'text':
            self._raw_input = self._load_text(self._input_path)
            self._raw_label = self._load_text(self._label_path)
            self._raw_class = self._load_text(self._class_path)
        else:
            raise NotImplementedError()

        self._input_vocab = input_vocab
        self._label_vocab = label_vocab
        self._class_vocab = class_vocab

        self._dataset_dir = dataset_dir
        self._train_data_path = list()
        self._valid_data_path = list()

        self._build_dataset_dir()

    def build_vocabulary(self,
                         max_size: int = None,
                         min_freq: int = 1) -> None:
        input_vocab_path = self._dataset_dir / INPUT_VOCAB_FILENAME
        label_vocab_path = self._dataset_dir / TAG_VOCAB_FILENAME
        class_vocab_path = self._dataset_dir / CLASS_VOCAB_FILENAME

        self._input_vocab = Vocabulary(max_size=max_size, min_freq=min_freq, bos_token=None, eos_token=None)
        self._label_vocab = Vocabulary(unknown_token=None)
        self._class_vocab = Vocabulary(unknown_token=None, padding_token=None, bos_token=None, eos_token=None)

        input_data = self._splitify(self._raw_input)
        label_data = self._splitify(self._raw_label)
        class_data = self._raw_class

        self._input_vocab.fit(input_data)
        self._label_vocab.fit(label_data)
        self._class_vocab.fit(class_data)

        self._input_vocab.to_json(input_vocab_path)
        self._label_vocab.to_json(label_vocab_path)
        self._class_vocab.to_json(class_vocab_path)

        return

    def build_trainable_dataset(self,
                                train_data_save_path: str = None,
                                valid_data_save_path: str = None) -> None:
        if self._input_vocab is None or self._label_vocab is None:
            raise ValueError()

        train_data = dict()
        train_data_save_path = self._dataset_dir / TRAIN_DATASET_FILENAME if train_data_save_path is None else train_data_save_path

        valid_data = dict()
        valid_data_save_path = self._dataset_dir / VALIDATION_DATASET_FILENAME if valid_data_save_path is None else valid_data_save_path

        train_raw_data, valid_raw_data = self._split_into_valid_and_train(self._raw_input, self._raw_label,
                                                                          self._raw_class)

        train_data['inputs'] = self._numerize_from_text(train_raw_data[0], self._input_vocab)
        train_data['slots'] = self._numerize_from_text(train_raw_data[1], self._label_vocab)
        train_data['intents'] = self._numerize_from_text(train_raw_data[2], self._class_vocab)

        valid_data['inputs'] = self._numerize_from_text(valid_raw_data[0], self._input_vocab)
        valid_data['slots'] = self._numerize_from_text(valid_raw_data[1], self._label_vocab)
        valid_data['intents'] = self._numerize_from_text(valid_raw_data[2], self._class_vocab)

        self._save_as_json(train_data, train_data_save_path)
        self._save_as_json(valid_data, valid_data_save_path)

        self._train_data_path.append(train_data_save_path)
        self._valid_data_path.append(valid_data_save_path)

        return

    def build_instant_data_loader(self, input_path, label_path, class_path, data_path=None):
        instant_data = dict()
        data_path = self._dataset_dir / INSTANT_DATASET_FILENAME if data_path is None else data_path

        input_data = self._load_text(input_path)
        label_data = self._load_text(label_path)
        class_data = self._load_text(class_path)

        instant_data['inputs'] = self._numerize_from_text(input_data, self._input_vocab)
        instant_data['slots'] = self._numerize_from_text(label_data, self._label_vocab)
        instant_data['intents'] = self._numerize_from_text(class_data, self._class_vocab)

        self._save_as_json(instant_data, data_path)

        instant_dataset = SLUDatasetFromJSONFile(data_path)

        instant_data_loader = DataLoader(instant_dataset,
                                         batch_size=1)

        return instant_data_loader

    def build_data_loader(self, batch_size, limit_pad_len, enable_length=True):
        train_dataset = SLUDatasetFromJSONFile(self._train_data_path[0],
                                               limit_pad_len=limit_pad_len,
                                               enable_length=enable_length)

        valid_dataset = SLUDatasetFromJSONFile(self._valid_data_path[0])

        train_data_loader = DataLoader(train_dataset,
                                       batch_size=batch_size,
                                       shuffle=True,
                                       num_workers=4,
                                       drop_last=True)

        valid_data_loader = DataLoader(valid_dataset,
                                       batch_size=1)

        return train_data_loader, valid_data_loader

    @property
    def class_to_idx(self):
        return self._class_vocab.word_to_idx

    def _split_into_valid_and_train(self, input, label, cls, test_size=0.1, random_state=RANDOM_SEED):
        input_train, input_test, label_train, label_test, class_train, class_test = train_test_split(input, label, cls,
                                                                                                     test_size=test_size,
                                                                                                     random_state=random_state)

        return (input_train, label_train, class_train), (input_test, label_test, class_test)
