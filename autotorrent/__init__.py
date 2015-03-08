import sys

if sys.version_info < (3, 0):
    try:
        reload(sys)
        sys.getdefaultencoding('UTF8')
    except:
        pass