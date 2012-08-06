import logging

class TGLogger(object):
  @staticmethod
  def set_logger(name, log_dir='/tmp/'):
    logger = logging.getLogger(name)
    hdlr = logging.FileHandler("/tmp/%s.log" % name)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)
    return(logger)
