import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

# https://gstreamer.freedesktop.org/documentation/tutorials/basic/hello-world.html?gi-language=c

def tutorial_main():
    Gst.init(None)

    pipeline = Gst.Pipeline()
    source = Gst.ElementFactory.make("videotestsrc", "source")
    vertigo_filter = Gst.ElementFactory.make("vertigotv")
    videoconv = Gst.ElementFactory.make("videoconvert")
    sink = Gst.ElementFactory.make("autovideosink", "sink")

    source.set_property("pattern", 0)
    vertigo_filter.set_property("zoom-speed", 1.5)

    pipeline.add(source)
    pipeline.add(vertigo_filter)
    pipeline.add(videoconv)
    pipeline.add(sink)

    source.link(vertigo_filter)
    vertigo_filter.link(videoconv)
    videoconv.link(sink)
    
    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        print("Unable to set the pipeline to the playing state.")
        

    bus = pipeline.get_bus()
    msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)

    if msg is not None:
        if msg.type == Gst.MessageType.ERROR:
            err, debug_info = msg.parse_error()
            print(f"Error received from element {msg.src.get_name()}: {err.message}")
            print("Debugging information: {}".format(debug_info if debug_info else "none"))
        elif msg.type == Gst.MessageType.EOS:
            print("End-Of-Stream reached.")
        else:
            print("Unexpected message received.")
    pipeline.set_state(Gst.State.NULL)

def main():
    tutorial_main()

if __name__ == '__main__':
    main()
