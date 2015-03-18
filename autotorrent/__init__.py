import sys

if sys.version_info < (3, 0):
    try:
        reload(sys)
        sys.setdefaultencoding('UTF8')
    except:
        pass