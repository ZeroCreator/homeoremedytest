"""
Модуль для работы с различными типами хранилищ
"""
from .yandex_disk import YandexDiskStorage
from .local_storage import LocalStorage
from .hybrid_storage import HybridStorage, StorageMode

__all__ = ['YandexDiskStorage', 'LocalStorage', 'HybridStorage', 'StorageMode']
