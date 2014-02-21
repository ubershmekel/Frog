##################################################################################################
# Copyright (c) 2012 Brett Dixon
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in 
# the Software without restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the 
# Software, and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS 
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR 
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION 
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
##################################################################################################


import logging
import re
import time
import subprocess
from threading import Thread

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from path import path as Path

TIMEOUT = 1
ROOT = Path(settings.MEDIA_ROOT.replace('\\', '/'))
logger = logging.getLogger('frog')

try:
    FROG_FFMPEG = getattr(settings, 'FROG_FFMPEG')
except AttributeError:
    raise ImproperlyConfigured, 'FROG_FFMPEG is required'

FROG_SCRUB_DURATION = getattr(settings, 'FROG_SCRUB_DURATION', 60)
FROG_FFMPEG_ARGS = getattr(settings, 'FROG_FFMPEG_ARGS', '-vcodec libx264 -b:v 2500k -acodec libvo_aacenc -b:a 56k -ac 2 -y')
FROG_SCRUB_FFMPEG_ARGS = getattr(settings, 'FROG_SCRUB_FFMPEG_ARGS', '-vcodec libx264 -b:v 2500k -x264opts keyint=1:min-keyint=8 -acodec libvo_aacenc -b:a 56k -ac 2 -y')
FROG_FFMPEG_FORMAT_ARGS = getattr(settings, 'FROG_FFMPEG_FORMAT_ARGS', '-vcodec libx264 -b:v 2500k -maxrate 2500k -bufsize 2500k -pix_fmt yuv420p -acodec libvo_aacenc -b:a 128k -ac 2 -y')

VIDEO_PROCESSING = 'frog/i/processing.mp4'
VIDEO_QUEUED = 'frog/i/queued.mp4'

class VideoThread(Thread):
    def __init__(self, queue, *args, **kwargs):
        super(VideoThread, self).__init__(*args, **kwargs)
        self.queue = queue
        self.daemon = True

    def run(self):
        while True:
            if self.queue.qsize():
                try:
                    isH264 = False
                    ## -- Get the video object to work on
                    item = self.queue.get()
                    ## -- Set the video to processing
                    logger.info('Processing video: %s' % item.guid)
                    item.video = VIDEO_PROCESSING
                    item.save()
                    ## -- Set the status of the queue item
                    item.queue.setStatus(item.queue.PROCESSING)
                    item.queue.setMessage('Processing video...')
                    
                    infile = "%s%s" % (ROOT, item.source.name)
                    cmd = '%s -i "%s"' % (FROG_FFMPEG, infile)
                    sourcepath = ROOT / item.source.name

                    ## -- Get the video information
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
                    infoString = proc.stdout.readlines()
                    videodata = parseInfo(infoString)
                    
                    logger.info('video data gathered:')
                    for vd in videodata:
                        logger.info('%s : %s' % (vd,videodata[vd]))
                    
                    #isH264 = videodata['video'][0]['codec'].lower().find('h264') != -1 and sourcepath.ext == '.mp4'
                    #m, s = divmod(FROG_SCRUB_DURATION, 60)
                    #h, m = divmod(m, 60)
                    #scrubstr = "%02d:%02d:%02d" % (h, m, s)
                    #scrub = videodata['duration'] <= scrubstr

                    cur_pix_fmt = videodata['video'][0]['pixel_format']
                    frogArgs = FROG_FFMPEG_ARGS
                    #if scrub:
                    #    frogArgs = FROG_SCRUB_FFMPEG_ARGS
                    if cur_pix_fmt in ["bgr24","yuv444p"] or len(cur_pix_fmt.split("(")) > 1:
                        frogArgs = FROG_FFMPEG_FORMAT_ARGS

                    outfile = sourcepath.parent / ("_%s.mp4" % item.hash)

                    ## -- Further processing is needed if not h264 or needs to be scrubbable
                    #if not isH264 or scrub:
                    
                    # nah, lets just process everything
                    if True:
                        item.queue.setMessage('Converting to MP4...')
                        
                        cmd = '{exe} -i "{infile}" {args} "{outfile}"'.format(
                            exe=FROG_FFMPEG,
                            infile=infile,
                            args=frogArgs,
                            outfile=outfile,
                        )
                        try:
                            subprocess.call(cmd, shell=True)
                        except subprocess.CalledProcessError:
                            logger.error('Failed to convert video: %s' % item.guid)
                            item.queue.setStatus(item.queue.ERROR)
                            continue
                        
                        item.video = outfile.replace('\\', '/').replace(ROOT, '')
                    else:
                        ## -- No further processing
                        item.video = item.source.name

                    ## -- Set the video to the result
                    logger.info('Finished processing video: %s' % item.guid)
                    item.queue.setStatus(item.queue.COMPLETED)
                    item.save()
                except Exception, e:
                    logger.error(str(e))

                time.sleep(TIMEOUT)

def dictFromStream(line,avType):
    dic = {}
    parts = line.split(',')
    dic['index'] = ":".join(parts[0].split('#')[-1].split(':')[:2])
    dic['type'] = parts[0].split('#')[-1].split(':')[2].strip()
    dic['codec'] = parts[0].split('#')[-1].split(':')[3].strip()
    if avType == 'Video':
        if len(parts[3].split('x'))>1:
            dic['pixel_format'] = ','.join([parts[1],parts[2]]).strip()
            info = parts[3].split(' ')[1].split('x')
            dic['width'] = info[0]
            dic['height'] = info[1]
        else:
            dic['pixel_format'] = parts[1].strip()
            info = parts[2].split(' ')[1].split('x')
            dic['width'] = info[0]
            dic['height'] = info[1]
    else:
        dic['hertz'] = parts[1].strip().split(" ")[0].strip()
        dic['bitrate'] = parts[4].strip().split(" ")[0].strip()
        
    return dic    
            

def parseInfo(strings):
    data = {}
    stream_video = re.compile("""Stream #\d[:.](?P<index>\d+).*: (?P<type>\w+): (?P<codec>.*), (?P<pixel_format>\w+), (?P<width>\d+)x(?P<height>\d+)""")
    stream_audio = re.compile("""Stream #\d[:.](?P<index>\d+).*: (?P<type>\w+): (?P<codec>.*), (?P<hertz>\d+) Hz, .*, .*, (?P<bitrate>\d+) kb/s$""")
    duration = re.compile("""Duration: (?P<duration>\d+:\d+:\d+.\d+), start: (?P<start>\d+.\d+), bitrate: (?P<bitrate>\d+) kb/s$""")

    for n in strings:
        n = n.strip()
        if n.startswith('Duration'):
            r = duration.search(n)
            data.update(r.groupdict())
        elif n.startswith('Stream'):
            if n.find('Video') != -1:
                data.setdefault('video', [])
                n = n.replace('(eng)','')
                data['video'].append(dictFromStream(n,'Video'))
                #r = stream_video.search(n)
                #data['video'].append(r.groupdict())
            elif n.find('Audio') != -1:
                data.setdefault('audio', [])
                n = n.replace(' (default)','')
                data['audio'].append(dictFromStream(n,'Audio'))
                #r = stream_audio.search(n)
                #data['audio'].append(r.groupdict())

    return data