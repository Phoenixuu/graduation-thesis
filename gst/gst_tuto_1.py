import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

# https://gstreamer.freedesktop.org/documentation/tutorials/basic/hello-world.html?gi-language=c

def tutorial_main():
    # Ligne plus nécéssaire dans les programmes
    # GStreamer
    #GObject.threads_init()
    Gst.init(None)

    # créer une simple pipeline directement (shortcut)
    # on peut mettre plusieurs éléments que le playbin
    # playbin joue le role de source, sink and whole pipeline
    # Laisse tout de même une moins grande granularité
    uri_file_name = Gst.filename_to_uri("../../res/endoscopy.mp4")
    pipeline = Gst.parse_launch(f"playbin uri={uri_file_name}")

    # Chaque element a un état play/pause
    pipeline.set_state(Gst.State.PLAYING)

    bus = pipeline.get_bus()
    msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)

    if msg.type == Gst.MessageType.ERROR:
        error, debug_info = msg.parse_error()
        print(f"Error occurred: {error.message}")
        if debug_info:
            print(f"Debugging information: {debug_info}")

    pipeline.set_state(Gst.State.NULL)

def main():
    tutorial_main()

if __name__ == '__main__':
    main()
