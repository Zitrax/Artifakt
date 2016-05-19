import os


def count_files(path):
    x = 0
    for root, dirs, files in os.walk(path):
        x += len(files)
    return x
