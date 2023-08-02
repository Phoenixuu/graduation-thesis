import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

video_queue = None
pipeline = None

def pad_add(src_pad, sink_pad):
    if sink_pad.is_linked():
        print("Error, sink_pad is already linked to another pad")
        return

    connection_result:Gst.PadLinkReturn = src_pad.link(sink_pad)
    if not connection_result:
        print("Error while trying to link pad")
        return

    print("Successful connection between source pad and sink pad of audio convertor")

def pad_added_handler(source, new_pad):
    new_pad_name = new_pad.get_current_caps().get_structure(0).get_name()
    if new_pad_name.startswith("video/x-h264"):
        pad_add(new_pad, video_queue.get_static_pad("sink"))
    else:
        print(f"Bad pad request name: {new_pad_name}")

def on_message(bus, message):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("Fin de la lecture du fichier")
        pipeline.set_state(Gst.State.NULL)
        sys.exit(0)
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("Erreur du pipeline :", err)
        print("Debug information :", debug)
        pipeline.set_state(Gst.State.NULL)
        sys.exit(1)

if __name__ == '__main__':
    Gst.init(None)

    #pipeline = Gst.parse_launch("""
    #    filesrc location=./res/endoscopy.mp4 ! 
    #    qtdemux name=demux demux.video_0 ! 
    #    queue ! 
    #    h264parse ! 
    #    nvv4l2decoder ! 
    #    m.sink_0 nvstreammux name=m batch-size=1 width=1280 height=1024 ! 
    #    nvvideoconvert ! 
    #    nvdsosd ! 
    #    nvegltransform ! 
    #    nveglglessink
    #""")
    
    pipeline = Gst.Pipeline()
    pipeline.set_state(Gst.State.NULL)

    filesrc = Gst.ElementFactory.make("filesrc", "file-source")
    filesrc.set_property("location", "../res/endoscopy.mp4")

    qtdemux = Gst.ElementFactory.make("qtdemux", "demux")
    # Ajout d'un signal pour détecter un élément
    qtdemux.connect("pad-added", pad_added_handler)


    video_queue = Gst.ElementFactory.make("queue", "video-queue")

    h264parse = Gst.ElementFactory.make("h264parse", "h264-parser")

    nvv4l2decoder = Gst.ElementFactory.make("nvv4l2decoder", "decoder")


    nvstreammux = Gst.ElementFactory.make("nvstreammux", "stream-muxer")
    nvstreammux.set_property("batch-size", 1)
    nvstreammux.set_property("width", 1280)
    nvstreammux.set_property("height", 1024)

    #nvinfer = Gst.ElementFactory.make("nvinfer", "inferencer")
    #nvinfer.set_property("config-file-path", "./endoscopy_pgie_config.txt")

    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "video-converter")

    nvdsosd = Gst.ElementFactory.make("nvdsosd", "osd")

    nvegltransform = Gst.ElementFactory.make("nvegltransform", "egl-transform")

    nveglglessink = Gst.ElementFactory.make("nveglglessink", "egl-sink")

    pipeline.add(filesrc)
    pipeline.add(qtdemux)
    pipeline.add(video_queue)
    pipeline.add(h264parse)
    pipeline.add(nvv4l2decoder)
    pipeline.add(nvstreammux)
    #pipeline.add(nvinfer)
    pipeline.add(nvvideoconvert)
    pipeline.add(nvdsosd)
    pipeline.add(nvegltransform)
    pipeline.add(nveglglessink)

    
    filesrc.link(qtdemux)

    
    video_queue.link(h264parse)
    h264parse.link(nvv4l2decoder)
    sinkpad = nvstreammux.get_request_pad("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of streammux \n")
    srcpad = nvv4l2decoder.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of caps_vidconvsrc \n")
    srcpad.link(sinkpad)
    nvstreammux.link(nvvideoconvert)
    #nvstreammux.link(nvinfer)
    #nvinfer.link(nvvideoconvert)
    nvvideoconvert.link(nvdsosd)
    nvdsosd.link(nvegltransform)
    nvegltransform.link(nveglglessink)


    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)

    loop = GLib.MainLoop()
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
