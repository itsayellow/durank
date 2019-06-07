#!/usr/bin/env python3
# https://stackoverflow.com/questions/2493172/determine-cluster-size-of-file-system-in-python

import ctypes

sectorsPerCluster = ctypes.c_ulonglong(0)
bytesPerSector = ctypes.c_ulonglong(0)
rootPathName = ctypes.c_wchar_p(u"C:\\")

ctypes.windll.kernel32.GetDiskFreeSpaceW(rootPathName,
    ctypes.pointer(sectorsPerCluster),
    ctypes.pointer(bytesPerSector),
    None,
    None,
)

print("sectors per cluster: %d"%sectorsPerCluster.value)
print("bytes per sector: %d"%bytesPerSector.value)
