import os, shutil

folder = ["shared/erp", "shared/wms", "shared/tms"]

for n in folder:
    for f in os.listdir(n):
        p = os.path.join(n, f)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
